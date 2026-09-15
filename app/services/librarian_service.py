import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    LibrarianAccessDeniedException,
    LibrarianAlreadyOwnedException,
    LibrarianNotFoundException,
    RepresentativeLibrarianNotSelectedException,
)
from app.models.enums import DEFAULT_LIBRARIAN_NAMES, LIBRARIAN_METADATA, LibrarianType
from app.models.librarian import Librarian
from app.models.librarian_level import LibrarianLevel
from app.models.librarian_type_info import LibrarianTypeInfo
from app.schemas.librarian import (
    AcquireLibrarianRequest,
    AcquireLibrarianResponse,
    LibrarianResponse,
    LibrarianTypeItemResponse,
    LibrarianTypeListResponse,
    RenameLibrarianResponse,
    RepresentativeLibrarianResponse,
)

DEFAULT_LIBRARIAN_TYPES = [
    {
        "type": LibrarianType.CAT,
        "image_url": "https://example.com/librarians/cat.png",
        "clicked_image_url": "https://example.com/librarians/cat-clicked.png",
    },
    {
        "type": LibrarianType.SHOEBILL,
        "image_url": "https://example.com/librarians/shoebill.png",
        "clicked_image_url": "https://example.com/librarians/shoebill-clicked.png",
    },
    {
        "type": LibrarianType.SEA_SLUG,
        "image_url": "https://example.com/librarians/sea-slug.png",
        "clicked_image_url": "https://example.com/librarians/sea-slug-clicked.png",
    },
    {
        "type": LibrarianType.GECKO,
        "image_url": "https://example.com/librarians/gecko.png",
        "clicked_image_url": "https://example.com/librarians/gecko-clicked.png",
    },
]


class LibrarianService:
    @staticmethod
    async def ensure_seed_data(db: AsyncSession) -> None:
        """사서 마스터 타입 및 초기 레벨 데이터 보장"""
        stmt = select(LibrarianTypeInfo)
        existing_types = (await db.execute(stmt)).scalars().all()
        if not existing_types:
            for item in DEFAULT_LIBRARIAN_TYPES:
                db.add(
                    LibrarianTypeInfo(
                        type=item["type"],
                        image_url=item["image_url"],
                        clicked_image_url=item["clicked_image_url"],
                    )
                )
            level_stmt = select(LibrarianLevel).where(LibrarianLevel.level == 1)
            level_1 = (await db.execute(level_stmt)).scalars().first()
            if not level_1:
                db.add(LibrarianLevel(level=1, required_experience=0))
            await db.commit()

    @staticmethod
    async def get_librarian_types(db: AsyncSession) -> LibrarianTypeListResponse:
        await LibrarianService.ensure_seed_data(db)
        stmt = select(LibrarianTypeInfo).order_by(LibrarianTypeInfo.type.asc())
        types = (await db.execute(stmt)).scalars().all()

        items = []
        for t in types:
            meta = LIBRARIAN_METADATA.get(t.type, {})
            items.append(
                LibrarianTypeItemResponse(
                    type=t.type,
                    default_name=meta.get("default_name", str(t.type)),
                    species=meta.get("species", "알 수 없음"),
                    mbti=meta.get("mbti", "INTJ"),
                    genres=meta.get("genres", []),
                    description=meta.get("description", ""),
                    ending_style=meta.get("ending_style", ""),
                    image_url=t.image_url,
                    clicked_image_url=t.clicked_image_url,
                )
            )
        return LibrarianTypeListResponse(types=items)

    @staticmethod
    async def acquire_librarian(
        db: AsyncSession, member_id: uuid.UUID, req: AcquireLibrarianRequest
    ) -> AcquireLibrarianResponse:
        await LibrarianService.ensure_seed_data(db)

        # 1. 중복 소유 확인
        dup_stmt = select(Librarian).where(
            Librarian.member_id == member_id,
            Librarian.type == req.type,
            Librarian.deleted_at.is_(None),
        )
        dup = (await db.execute(dup_stmt)).scalars().first()
        if dup:
            raise LibrarianAlreadyOwnedException("이미 보유하고 있는 사서 종류입니다.")

        # 이름이 생략되거나 공백일 경우 기본 표시명 자동 지정
        chosen_name = (
            req.name.strip()
            if (req.name and req.name.strip())
            else DEFAULT_LIBRARIAN_NAMES.get(req.type, "사서")
        )

        # 2. 사서 인스턴스 생성 (초기 레벨 1, 경험치 0)
        librarian = Librarian(
            member_id=member_id,
            type=req.type,
            name=chosen_name,
            level=1,
            experience=0,
            is_representative=False,
        )
        db.add(librarian)
        await db.commit()
        await db.refresh(librarian)

        return AcquireLibrarianResponse(
            librarian_id=librarian.id,
            type=librarian.type,
            name=librarian.name,
            level=librarian.level,
            experience=librarian.experience,
            is_representative=librarian.is_representative,
            created_at=librarian.created_at,
        )

    @staticmethod
    async def get_my_librarians(
        db: AsyncSession, member_id: uuid.UUID
    ) -> list[LibrarianResponse]:
        stmt = (
            select(Librarian, LibrarianTypeInfo)
            .outerjoin(LibrarianTypeInfo, Librarian.type == LibrarianTypeInfo.type)
            .where(
                Librarian.member_id == member_id,
                Librarian.deleted_at.is_(None),
            )
            .order_by(Librarian.is_representative.desc(), Librarian.id.asc())
        )
        results = (await db.execute(stmt)).all()

        items = []
        for lib, info in results:
            meta = LIBRARIAN_METADATA.get(lib.type, {})
            items.append(
                LibrarianResponse(
                    librarian_id=lib.id,
                    type=lib.type,
                    name=lib.name,
                    default_name=meta.get("default_name"),
                    species=meta.get("species"),
                    level=lib.level,
                    experience=lib.experience,
                    is_representative=lib.is_representative,
                    image_url=info.image_url if info else None,
                    clicked_image_url=info.clicked_image_url if info else None,
                    created_at=lib.created_at,
                )
            )
        return items

    @staticmethod
    async def rename_librarian(
        db: AsyncSession, member_id: uuid.UUID, librarian_id: int, new_name: str
    ) -> RenameLibrarianResponse:
        stmt = select(Librarian).where(
            Librarian.id == librarian_id,
            Librarian.deleted_at.is_(None),
        )
        librarian = (await db.execute(stmt)).scalars().first()
        if not librarian:
            raise LibrarianNotFoundException("사서를 찾을 수 없습니다.")
        if librarian.member_id != member_id:
            raise LibrarianAccessDeniedException(
                "해당 사서에 대한 접근 권한이 없습니다."
            )

        librarian.name = new_name.strip()
        await db.commit()
        await db.refresh(librarian)

        return RenameLibrarianResponse(
            librarian_id=librarian.id,
            name=librarian.name,
            updated_at=librarian.updated_at,
        )

    @staticmethod
    async def delete_librarian(
        db: AsyncSession, member_id: uuid.UUID, librarian_id: int
    ) -> None:
        stmt = select(Librarian).where(
            Librarian.id == librarian_id,
            Librarian.deleted_at.is_(None),
        )
        librarian = (await db.execute(stmt)).scalars().first()
        if not librarian:
            raise LibrarianNotFoundException("사서를 찾을 수 없습니다.")
        if librarian.member_id != member_id:
            raise LibrarianAccessDeniedException(
                "해당 사서에 대한 접근 권한이 없습니다."
            )

        librarian.deleted_at = datetime.now(UTC)
        await db.commit()

    @staticmethod
    async def set_representative_librarian(
        db: AsyncSession, member_id: uuid.UUID, librarian_id: int
    ) -> RepresentativeLibrarianResponse:
        stmt = select(Librarian).where(
            Librarian.id == librarian_id,
            Librarian.deleted_at.is_(None),
        )
        librarian = (await db.execute(stmt)).scalars().first()
        if not librarian:
            raise LibrarianNotFoundException("사서를 찾을 수 없습니다.")
        if librarian.member_id != member_id:
            raise LibrarianAccessDeniedException(
                "해당 사서에 대한 접근 권한이 없습니다."
            )

        # 1. 기존 대표 사서 해제
        reset_stmt = (
            update(Librarian)
            .where(
                Librarian.member_id == member_id,
                Librarian.is_representative.is_(True),
                Librarian.deleted_at.is_(None),
            )
            .values(is_representative=False)
        )
        await db.execute(reset_stmt)

        # 2. 지정 사서 대표 설정
        librarian.is_representative = True
        await db.commit()
        await db.refresh(librarian)

        # 마스터 이미지 조회
        type_info_stmt = select(LibrarianTypeInfo).where(
            LibrarianTypeInfo.type == librarian.type
        )
        type_info = (await db.execute(type_info_stmt)).scalars().first()
        meta = LIBRARIAN_METADATA.get(librarian.type, {})

        return RepresentativeLibrarianResponse(
            librarian_id=librarian.id,
            type=librarian.type,
            name=librarian.name,
            default_name=meta.get("default_name"),
            species=meta.get("species"),
            mbti=meta.get("mbti"),
            genres=meta.get("genres", []),
            description=meta.get("description"),
            ending_style=meta.get("ending_style"),
            level=librarian.level,
            experience=librarian.experience,
            is_representative=librarian.is_representative,
            image_url=type_info.image_url if type_info else None,
            clicked_image_url=type_info.clicked_image_url if type_info else None,
            updated_at=librarian.updated_at,
        )

    @staticmethod
    async def get_representative_librarian(
        db: AsyncSession, member_id: uuid.UUID
    ) -> RepresentativeLibrarianResponse:
        stmt = (
            select(Librarian, LibrarianTypeInfo)
            .outerjoin(LibrarianTypeInfo, Librarian.type == LibrarianTypeInfo.type)
            .where(
                Librarian.member_id == member_id,
                Librarian.is_representative.is_(True),
                Librarian.deleted_at.is_(None),
            )
        )
        result = (await db.execute(stmt)).first()
        if not result:
            raise RepresentativeLibrarianNotSelectedException(
                "대표 사서가 아직 지정되지 않았습니다."
            )

        librarian, type_info = result
        meta = LIBRARIAN_METADATA.get(librarian.type, {})

        return RepresentativeLibrarianResponse(
            librarian_id=librarian.id,
            type=librarian.type,
            name=librarian.name,
            default_name=meta.get("default_name"),
            species=meta.get("species"),
            mbti=meta.get("mbti"),
            genres=meta.get("genres", []),
            description=meta.get("description"),
            ending_style=meta.get("ending_style"),
            level=librarian.level,
            experience=librarian.experience,
            is_representative=librarian.is_representative,
            image_url=type_info.image_url if type_info else None,
            clicked_image_url=type_info.clicked_image_url if type_info else None,
            updated_at=librarian.updated_at,
        )
