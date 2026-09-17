from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    LibraryBookAccessDeniedException,
    LibraryBookNotFoundException,
)
from app.models.enums import BookReadingStatus
from app.models.library_book import LibraryBook
from app.models.reading_session import ReadingSession
from app.schemas.reading_session import (
    BookReadingSessionListResponse,
    CreateReadingSessionRequest,
    ReadingSessionResponse,
)


class ReadingSessionService:
    @staticmethod
    async def create_session(
        db: AsyncSession,
        member_id: UUID,
        req: CreateReadingSessionRequest,
        book_id_override: int | None = None,
    ) -> ReadingSessionResponse:
        book_title: str | None = None
        updated_current_page: int | None = None
        book_reading_status: BookReadingStatus | None = None
        progress: float | None = None
        actual_start_page: int | None = req.start_page
        actual_end_page: int | None = req.end_page

        target_book_id = (
            book_id_override if book_id_override is not None else req.book_id
        )

        # 1. 대상 도서가 지정된 경우 도서 검증 및 진도율 동기화
        if target_book_id is not None:
            stmt = select(LibraryBook).where(
                LibraryBook.id == target_book_id,
                LibraryBook.deleted_at.is_(None),
            )
            result = await db.execute(stmt)
            book = result.scalar_one_or_none()
            if not book:
                raise LibraryBookNotFoundException()
            if book.member_id != member_id:
                raise LibraryBookAccessDeniedException(
                    "해당 도서에 대한 접근 권한이 없습니다."
                )

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
            if book.total_pages and book.total_pages > 0:
                progress = round((book.current_page / book.total_pages) * 100, 1)

        # 시간/초 환산 보정
        duration_sec = req.duration_seconds
        duration_min = req.duration_minutes
        if duration_sec is None and duration_min is not None:
            duration_sec = duration_min * 60
        elif duration_sec is not None and duration_min is None:
            duration_min = duration_sec // 60
        elif duration_sec is None and duration_min is None:
            duration_sec = 0
            duration_min = 0

        # 2. ReadingSession 생성 및 저장
        session = ReadingSession(
            member_id=member_id,
            book_id=target_book_id,
            duration_seconds=duration_sec,
            duration_minutes=duration_min,
            start_time=req.start_time,
            end_time=req.end_time or datetime.now(UTC),
            start_page=actual_start_page,
            end_page=actual_end_page,
            memo=req.memo,
            weather=req.weather,
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)

        return ReadingSessionResponse(
            id=session.id,
            member_id=session.member_id,
            book_id=session.book_id,
            duration_seconds=session.duration_seconds,
            duration_minutes=session.duration_minutes,
            start_time=session.start_time,
            end_time=session.end_time,
            start_page=session.start_page,
            end_page=session.end_page,
            memo=session.memo,
            weather=session.weather,
            created_at=session.created_at,
            updated_at=session.updated_at,
            book_title=book_title,
            updated_current_page=updated_current_page,
            progress=progress,
            book_reading_status=book_reading_status,
        )

    @staticmethod
    async def get_book_sessions(
        db: AsyncSession,
        member_id: UUID,
        book_id: int,
    ) -> BookReadingSessionListResponse:
        # 도서 검증 및 접근 권한 확인
        stmt = select(LibraryBook).where(
            LibraryBook.id == book_id,
            LibraryBook.deleted_at.is_(None),
        )
        result = await db.execute(stmt)
        book = result.scalar_one_or_none()
        if not book:
            raise LibraryBookNotFoundException()
        if book.member_id != member_id:
            raise LibraryBookAccessDeniedException(
                "해당 도서에 대한 접근 권한이 없습니다."
            )

        # 해당 도서의 세션 목록 조회 (최신순)
        sessions_stmt = (
            select(ReadingSession)
            .where(
                ReadingSession.member_id == member_id,
                ReadingSession.book_id == book_id,
            )
            .order_by(desc(ReadingSession.created_at), desc(ReadingSession.id))
        )
        sessions_res = await db.execute(sessions_stmt)
        sessions = sessions_res.scalars().all()

        total_sec = sum(
            s.duration_seconds or (s.duration_minutes * 60) for s in sessions
        )
        total_min = sum(
            s.duration_minutes or ((s.duration_seconds or 0) // 60) for s in sessions
        )

        progress: float | None = None
        if book.total_pages and book.total_pages > 0:
            progress = round((book.current_page / book.total_pages) * 100, 1)

        items = [
            ReadingSessionResponse(
                id=s.id,
                member_id=s.member_id,
                book_id=s.book_id,
                duration_seconds=s.duration_seconds or (s.duration_minutes * 60),
                duration_minutes=s.duration_minutes
                or ((s.duration_seconds or 0) // 60),
                start_time=s.start_time,
                end_time=s.end_time,
                start_page=s.start_page,
                end_page=s.end_page,
                memo=s.memo,
                weather=s.weather,
                created_at=s.created_at,
                updated_at=s.updated_at,
                book_title=book.title,
                updated_current_page=book.current_page,
                progress=progress,
                book_reading_status=book.reading_status,
            )
            for s in sessions
        ]

        return BookReadingSessionListResponse(
            book_id=book_id,
            total_duration_seconds=total_sec,
            total_duration_minutes=total_min,
            session_count=len(sessions),
            sessions=items,
        )
