import math
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import (
    DemoQuotaExceededException,
    LibraryBookAccessDeniedException,
    LibraryBookNotFoundException,
    ScrapAccessDeniedException,
    ScrapNotFoundException,
)
from app.models.library_book import LibraryBook
from app.models.scrap import Scrap
from app.schemas.common import PaginatedResponse
from app.schemas.scrap import (
    CreateScrapRequest,
    CreateScrapResponse,
    ScrapDetailResponse,
    ScrapResponse,
    UpdateScrapRequest,
    UpdateScrapResponse,
)


class ScrapService:
    @staticmethod
    async def create_scrap(
        db: AsyncSession, member_id: uuid.UUID, book_id: int, req: CreateScrapRequest
    ) -> CreateScrapResponse:
        # 도서 확인 및 소유권 검증
        book_stmt = select(LibraryBook).where(
            LibraryBook.id == book_id,
            LibraryBook.deleted_at.is_(None),
        )
        book = (await db.execute(book_stmt)).scalars().first()
        if not book:
            raise LibraryBookNotFoundException("도서를 찾을 수 없습니다.")
        if book.member_id != member_id:
            raise LibraryBookAccessDeniedException(
                "해당 도서에 대한 접근 권한이 없습니다."
            )

        # 데모 계정 도서당 스크랩 쿼터(상한) 검증
        if str(member_id) == settings.DEMO_MEMBER_ID:
            active_scraps_count_stmt = select(func.count(Scrap.id)).where(
                Scrap.book_id == book_id,
                Scrap.deleted_at.is_(None),
            )
            active_scraps_count = (
                await db.execute(active_scraps_count_stmt)
            ).scalar() or 0
            if active_scraps_count >= settings.DEMO_MAX_SCRAPS_PER_BOOK:
                raise DemoQuotaExceededException(
                    f"데모 계정의 도서당 최대 스크랩 수({settings.DEMO_MAX_SCRAPS_PER_BOOK}개)를 초과할 수 없습니다."
                )

        scrap = Scrap(
            book_id=book_id,
            sentence=req.sentence,
            page_number=req.page_number,
            scrap_image_url=req.scrap_image_url,
            memo=req.memo.strip() if req.memo else None,
        )
        db.add(scrap)
        await db.commit()
        await db.refresh(scrap)

        return CreateScrapResponse(
            scrap_id=scrap.id,
            book_id=scrap.book_id,
            sentence=scrap.sentence,
            page_number=scrap.page_number,
            scrap_image_url=scrap.scrap_image_url,
            memo=scrap.memo,
            created_at=scrap.created_at,
        )

    @staticmethod
    async def get_book_scraps(
        db: AsyncSession,
        member_id: uuid.UUID,
        book_id: int,
        page: int = 0,
        size: int = 20,
    ) -> PaginatedResponse[ScrapResponse]:
        # 도서 확인 및 소유권 검증
        book_stmt = select(LibraryBook).where(
            LibraryBook.id == book_id,
            LibraryBook.deleted_at.is_(None),
        )
        book = (await db.execute(book_stmt)).scalars().first()
        if not book:
            raise LibraryBookNotFoundException("도서를 찾을 수 없습니다.")
        if book.member_id != member_id:
            raise LibraryBookAccessDeniedException(
                "해당 도서에 대한 접근 권한이 없습니다."
            )

        count_stmt = select(func.count(Scrap.id)).where(
            Scrap.book_id == book_id,
            Scrap.deleted_at.is_(None),
        )
        total_elements = (await db.execute(count_stmt)).scalar() or 0
        total_pages = math.ceil(total_elements / size) if total_elements > 0 else 0

        scraps_stmt = (
            select(Scrap)
            .where(
                Scrap.book_id == book_id,
                Scrap.deleted_at.is_(None),
            )
            .order_by(Scrap.created_at.asc())
            .offset(page * size)
            .limit(size)
        )
        scraps = (await db.execute(scraps_stmt)).scalars().all()

        items = [
            ScrapResponse(
                scrap_id=s.id,
                book_id=s.book_id,
                sentence=s.sentence,
                page_number=s.page_number,
                scrap_image_url=s.scrap_image_url,
                memo=s.memo,
                created_at=s.created_at,
            )
            for s in scraps
        ]

        return PaginatedResponse[ScrapResponse](
            items=items,
            page=page,
            size=size,
            total_elements=total_elements,
            total_pages=total_pages,
            has_previous=page > 0,
            has_next=page < (total_pages - 1),
        )

    @staticmethod
    async def get_scrap_detail(
        db: AsyncSession, member_id: uuid.UUID, scrap_id: int
    ) -> ScrapDetailResponse:
        stmt = (
            select(Scrap, LibraryBook)
            .join(LibraryBook, Scrap.book_id == LibraryBook.id)
            .where(
                Scrap.id == scrap_id,
                Scrap.deleted_at.is_(None),
            )
        )
        result = (await db.execute(stmt)).first()
        if not result:
            raise ScrapNotFoundException("스크랩을 찾을 수 없습니다.")
        scrap, book = result
        if book.member_id != member_id:
            raise ScrapAccessDeniedException("해당 스크랩에 대한 접근 권한이 없습니다.")

        return ScrapDetailResponse(
            scrap_id=scrap.id,
            book_id=scrap.book_id,
            sentence=scrap.sentence,
            page_number=scrap.page_number,
            scrap_image_url=scrap.scrap_image_url,
            memo=scrap.memo,
            created_at=scrap.created_at,
            updated_at=scrap.updated_at,
        )

    @staticmethod
    async def update_scrap(
        db: AsyncSession, member_id: uuid.UUID, scrap_id: int, req: UpdateScrapRequest
    ) -> UpdateScrapResponse:
        stmt = (
            select(Scrap, LibraryBook)
            .join(LibraryBook, Scrap.book_id == LibraryBook.id)
            .where(
                Scrap.id == scrap_id,
                Scrap.deleted_at.is_(None),
            )
        )
        result = (await db.execute(stmt)).first()
        if not result:
            raise ScrapNotFoundException("스크랩을 찾을 수 없습니다.")
        scrap, book = result
        if book.member_id != member_id:
            raise ScrapAccessDeniedException("해당 스크랩에 대한 접근 권한이 없습니다.")

        scrap.sentence = req.sentence
        scrap.page_number = req.page_number
        scrap.scrap_image_url = req.scrap_image_url
        scrap.memo = req.memo.strip() if req.memo else None

        await db.commit()
        await db.refresh(scrap)

        return UpdateScrapResponse(
            scrap_id=scrap.id,
            book_id=scrap.book_id,
            sentence=scrap.sentence,
            page_number=scrap.page_number,
            scrap_image_url=scrap.scrap_image_url,
            memo=scrap.memo,
            updated_at=scrap.updated_at,
        )

    @staticmethod
    async def delete_scrap(
        db: AsyncSession, member_id: uuid.UUID, scrap_id: int
    ) -> None:
        stmt = (
            select(Scrap, LibraryBook)
            .join(LibraryBook, Scrap.book_id == LibraryBook.id)
            .where(
                Scrap.id == scrap_id,
                Scrap.deleted_at.is_(None),
            )
        )
        result = (await db.execute(stmt)).first()
        if not result:
            raise ScrapNotFoundException("스크랩을 찾을 수 없습니다.")
        scrap, book = result
        if book.member_id != member_id:
            raise ScrapAccessDeniedException("해당 스크랩에 대한 접근 권한이 없습니다.")

        scrap.deleted_at = datetime.now(UTC)
        await db.commit()
