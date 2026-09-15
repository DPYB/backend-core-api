from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import LibraryBookNotFoundException
from app.models.enums import BookReadingStatus
from app.models.library_book import LibraryBook
from app.models.reading_session import ReadingSession
from app.schemas.reading_session import (
    CreateReadingSessionRequest,
    ReadingSessionResponse,
)


class ReadingSessionService:
    @staticmethod
    async def create_session(
        db: AsyncSession,
        member_id: UUID,
        req: CreateReadingSessionRequest,
    ) -> ReadingSessionResponse:
        book_title: str | None = None
        updated_current_page: int | None = None
        book_reading_status: BookReadingStatus | None = None
        actual_start_page: int | None = req.start_page
        actual_end_page: int | None = req.end_page

        # 1. 대상 도서가 지정된 경우 도서 검증 및 진도율 동기화
        if req.book_id is not None:
            stmt = select(LibraryBook).where(
                LibraryBook.id == req.book_id,
                LibraryBook.member_id == member_id,
                LibraryBook.deleted_at.is_(None),
            )
            result = await db.execute(stmt)
            book = result.scalar_one_or_none()
            if not book:
                raise LibraryBookNotFoundException()

            book_title = book.title

            # start_page 미입력 시 도서의 직전 현재 페이지로 자동 채움
            if actual_start_page is None:
                actual_start_page = book.current_page

            # end_page가 주어진 경우 진도율 및 상태 업데이트
            if actual_end_page is not None:
                if actual_end_page > book.current_page:
                    book.current_page = actual_end_page

                # 완독 판정
                if book.total_pages and book.current_page >= book.total_pages:
                    book.reading_status = BookReadingStatus.COMPLETED
                    if not book.completed_at:
                        book.completed_at = datetime.now(UTC)
                elif (
                    book.current_page > 0
                    and book.reading_status == BookReadingStatus.PLANNED
                ):
                    book.reading_status = BookReadingStatus.READING

            updated_current_page = book.current_page
            book_reading_status = book.reading_status

        # 2. ReadingSession 생성 및 저장
        session = ReadingSession(
            member_id=member_id,
            book_id=req.book_id,
            duration_minutes=req.duration_minutes,
            start_page=actual_start_page,
            end_page=actual_end_page,
            weather=req.weather,
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)

        return ReadingSessionResponse(
            id=session.id,
            member_id=session.member_id,
            book_id=session.book_id,
            duration_minutes=session.duration_minutes,
            start_page=session.start_page,
            end_page=session.end_page,
            weather=session.weather,
            created_at=session.created_at,
            book_title=book_title,
            updated_current_page=updated_current_page,
            book_reading_status=book_reading_status,
        )
