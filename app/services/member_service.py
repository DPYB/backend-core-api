import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.models.enums import DEFAULT_LIBRARIAN_NAMES
from app.models.librarian import Librarian
from app.models.library_book import LibraryBook
from app.models.member import Member
from app.models.record import Record, RecordScrap
from app.models.scrap import Scrap
from app.models.shelf import Shelf
from app.models.terms import MemberAgreement
from app.schemas.member import MemberProfileResponse, UpdateProfileRequest
from app.services.shelf_service import ShelfService
from app.services.social_auth_service import SocialUserInfo


class MemberService:
    @staticmethod
    async def get_or_create_social_member(
        db: AsyncSession,
        social_info: SocialUserInfo,
        agreed_terms_ids: list[int] | None = None,
    ) -> tuple[Member, bool]:
        """
        소셜 로그인 정보로 회원을 조회하거나, 없으면 신규 가입(Get-or-Create) 처리합니다.
        신규 가입 시 기본 책장 생성 및 약관 동의 이력을 저장합니다.
        반환: (Member, is_new_member: bool)
        """
        # 1. provider + provider_id 로 기존 활성 회원 조회
        stmt = select(Member).where(
            Member.provider == social_info.provider,
            Member.provider_id == social_info.provider_id,
            Member.deleted_at.is_(None),
        )
        res = await db.execute(stmt)
        member = res.scalars().first()

        # 2. 없으면 이메일로도 조회 (소셜 연동 호환)
        if not member:
            stmt_email = select(Member).where(
                Member.email == social_info.email,
                Member.deleted_at.is_(None),
            )
            res_email = await db.execute(stmt_email)
            member = res_email.scalars().first()

        if member:
            # 프로필 이미지 변경 시 업데이트
            if (
                social_info.profile_image_url
                and member.profile_image_url != social_info.profile_image_url
            ):
                member.profile_image_url = social_info.profile_image_url
                await db.commit()
                await db.refresh(member)
            return member, False

        # 3. 신규 회원 생성
        new_member_id = uuid.uuid4()
        new_member = Member(
            member_id=new_member_id,
            email=social_info.email,
            nickname=social_info.nickname,
            profile_image_url=social_info.profile_image_url,
            status="ACTIVE",
            provider=social_info.provider,
            provider_id=social_info.provider_id,
        )
        db.add(new_member)
        await db.flush()

        # 기본 책장 자동 생성 보장
        await ShelfService.get_or_create_default_shelf(db, new_member_id)

        # 기본 대표 사서(CAT) 자동 지급
        await MemberService._ensure_default_cat_librarian(db, new_member_id)

        # 전달받은 약관 동의 목록 등록
        if agreed_terms_ids:
            for tid in agreed_terms_ids:
                agreement = MemberAgreement(
                    member_id=new_member_id,
                    terms_id=tid,
                    action="AGREE",
                )
                db.add(agreement)

        await db.commit()
        await db.refresh(new_member)
        return new_member, True

    @staticmethod
    async def get_or_create_dev_member(
        db: AsyncSession,
        email: str,
    ) -> tuple[Member, bool]:
        """
        로컬 개발 및 프론트 연동용 테스트 회원을 조회하거나, 없으면 신규 가입(Get-or-Create)합니다.
        신규 가입 시 기본 책장 및 기본 대표 고양이 사서(CAT)를 자동 생성/지급합니다.
        반환: (Member, is_new: bool)
        """
        clean_email = email.strip().lower()
        stmt = select(Member).where(
            Member.email == clean_email,
            Member.deleted_at.is_(None),
        )
        res = await db.execute(stmt)
        member = res.scalars().first()

        if member:
            return member, False

        # 신규 회원 생성
        nickname = clean_email.split("@")[0][:50] or "reader"
        new_member_id = uuid.uuid4()
        new_member = Member(
            member_id=new_member_id,
            email=clean_email,
            nickname=nickname,
            profile_image_url=None,
            status="ACTIVE",
            provider="LOCAL",
            provider_id=clean_email,
        )
        db.add(new_member)
        await db.flush()

        # 기본 책장 자동 생성
        await ShelfService.get_or_create_default_shelf(db, new_member_id)

        # 기본 대표 사서(CAT) 자동 생성
        await MemberService._ensure_default_cat_librarian(db, new_member_id)

        await db.commit()
        await db.refresh(new_member)
        return new_member, True

    @staticmethod
    async def _ensure_default_cat_librarian(
        db: AsyncSession, member_id: uuid.UUID
    ) -> None:
        """신규 회원에게 기본 대표 고양이 사서(CAT)를 지급합니다."""
        from app.models.enums import LibrarianType
        from app.services.librarian_service import LibrarianService

        await LibrarianService.ensure_seed_data(db)
        lib_stmt = select(Librarian).where(
            Librarian.member_id == member_id,
            Librarian.deleted_at.is_(None),
        )
        existing = (await db.execute(lib_stmt)).scalars().first()
        if not existing:
            cat = Librarian(
                member_id=member_id,
                type=LibrarianType.CAT,
                name="블루",
                level=1,
                experience=0,
                is_representative=True,
            )
            db.add(cat)

    @staticmethod
    async def get_member_by_id(db: AsyncSession, member_id: uuid.UUID) -> Member:
        """회원 ID로 활성 회원을 조회합니다."""
        stmt = select(Member).where(
            Member.member_id == member_id,
            Member.deleted_at.is_(None),
        )
        res = await db.execute(stmt)
        member = res.scalars().first()
        if not member:
            raise AppException(
                404, "MEMBER_NOT_FOUND", "존재하지 않거나 탈퇴한 회원입니다."
            )
        return member

    @staticmethod
    def to_profile_response(
        member: Member, librarian: Librarian | None = None
    ) -> MemberProfileResponse:
        """Member 모델을 MemberProfileResponse DTO로 변환합니다."""
        lib_type = librarian.type if librarian else None
        lib_name = librarian.name if librarian else None
        lib_default_name = DEFAULT_LIBRARIAN_NAMES.get(lib_type) if lib_type else None

        return MemberProfileResponse(
            member_id=str(member.member_id),
            email=member.email,
            nickname=member.nickname,
            profile_image_url=member.profile_image_url,
            birth_date=member.birth_date,
            gender=member.gender,
            status=member.status,
            provider=member.provider,
            librarian_type=lib_type,
            librarian_name=lib_name or lib_default_name,
            librarian_default_name=lib_default_name,
            created_at=member.created_at,
        )

    @staticmethod
    async def get_profile(
        db: AsyncSession, member_id: uuid.UUID
    ) -> MemberProfileResponse:
        """회원 본인 프로필을 조회합니다."""
        member = await MemberService.get_member_by_id(db, member_id)

        # 대표 사서 조회 (없을 경우 첫 번째 활성 사서)
        lib_stmt = (
            select(Librarian)
            .where(
                Librarian.member_id == member_id,
                Librarian.deleted_at.is_(None),
            )
            .order_by(Librarian.is_representative.desc(), Librarian.id.asc())
        )
        librarian = (await db.execute(lib_stmt)).scalars().first()

        return MemberService.to_profile_response(member, librarian)

    @staticmethod
    async def update_profile(
        db: AsyncSession, member_id: uuid.UUID, req: UpdateProfileRequest
    ) -> MemberProfileResponse:
        """회원 프로필을 수정합니다."""
        member = await MemberService.get_member_by_id(db, member_id)

        if req.nickname is not None and req.nickname.strip():
            new_nickname = req.nickname.strip()
            # 닉네임 중복 확인 (본인 제외)
            stmt = select(Member).where(
                Member.nickname == new_nickname,
                Member.member_id != member_id,
                Member.deleted_at.is_(None),
            )
            res = await db.execute(stmt)
            if res.scalars().first():
                raise AppException(
                    409, "DUPLICATE_NICKNAME", "이미 사용 중인 닉네임입니다."
                )
            member.nickname = new_nickname

        if req.profile_image_url is not None:
            member.profile_image_url = req.profile_image_url
        if req.birth_date is not None:
            member.birth_date = req.birth_date
        if req.gender is not None:
            member.gender = req.gender

        await db.commit()
        await db.refresh(member)
        return await MemberService.get_profile(db, member_id)

    @staticmethod
    async def withdraw_member(db: AsyncSession, member_id: uuid.UUID) -> None:
        """
        회원 탈퇴 및 소속된 모든 데이터(서재, 도서, 스크랩, 독서기록, 사서)를 일괄 소프트 삭제합니다.
        """
        member = await MemberService.get_member_by_id(db, member_id)
        now = datetime.now(UTC)

        # 1. 회원 상태 변경 및 소프트 삭제
        member.status = "WITHDRAWN"
        member.deleted_at = now

        # 2. 서재 및 책장 도서, 스크랩 소프트 삭제
        book_ids_stmt = select(LibraryBook.id).where(LibraryBook.member_id == member_id)
        await db.execute(
            update(Scrap)
            .where(Scrap.book_id.in_(book_ids_stmt), Scrap.deleted_at.is_(None))
            .values(deleted_at=now)
        )
        await db.execute(
            update(LibraryBook)
            .where(LibraryBook.member_id == member_id, LibraryBook.deleted_at.is_(None))
            .values(deleted_at=now)
        )
        await db.execute(
            update(Shelf)
            .where(Shelf.member_id == member_id, Shelf.deleted_at.is_(None))
            .values(deleted_at=now)
        )

        # 3. 독서 감상 기록 및 스크랩 소프트 삭제
        await db.execute(
            update(RecordScrap)
            .where(RecordScrap.member_id == member_id, RecordScrap.deleted_at.is_(None))
            .values(deleted_at=now)
        )
        await db.execute(
            update(Record)
            .where(Record.member_id == member_id, Record.deleted_at.is_(None))
            .values(deleted_at=now)
        )

        # 4. 보유 사서 소프트 삭제
        await db.execute(
            update(Librarian)
            .where(Librarian.member_id == member_id, Librarian.deleted_at.is_(None))
            .values(deleted_at=now)
        )

        await db.commit()

    @staticmethod
    async def check_availability(
        db: AsyncSession, field: str, value: str
    ) -> tuple[bool, str]:
        """이메일 또는 닉네임의 사용 가능 여부를 확인합니다."""
        val = value.strip()
        if not val:
            return False, "값을 입력해주세요."

        if field == "email":
            stmt = select(func.count(Member.id)).where(
                Member.email == val,
                Member.deleted_at.is_(None),
            )
            res = await db.execute(stmt)
            count = res.scalar_one()
            if count > 0:
                return False, "이미 사용 중인 이메일입니다."
            return True, "사용 가능한 이메일입니다."

        if field == "nickname":
            stmt = select(func.count(Member.id)).where(
                Member.nickname == val,
                Member.deleted_at.is_(None),
            )
            res = await db.execute(stmt)
            count = res.scalar_one()
            if count > 0:
                return False, "이미 사용 중인 닉네임입니다."
            return True, "사용 가능한 닉네임입니다."

        raise AppException(400, "INVALID_FIELD", f"지원하지 않는 필드입니다: {field}")
