from datetime import UTC, datetime, timedelta, timezone
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
from app.models.record import Record
from app.models.scrap import Scrap
from app.schemas.reading_session import (
    BookReadingSessionListResponse,
    CreateReadingSessionRequest,
    ReadingCalendarActivityItem,
    ReadingCalendarResponse,
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

    @staticmethod
    async def get_monthly_calendar(
        db: AsyncSession,
        member_id: UUID,
        year: int,
        month: int,
    ) -> ReadingCalendarResponse:
        # 1. KST(UTC+9) 기준 월 시작/종료 일시 계산 (경계선 오차 방지)
        kst = timezone(timedelta(hours=9))
        start_dt_kst = datetime(year, month, 1, 0, 0, 0, tzinfo=kst)
        if month == 12:
            end_dt_kst = datetime(year + 1, 1, 1, 0, 0, 0, tzinfo=kst)
        else:
            end_dt_kst = datetime(year, month + 1, 1, 0, 0, 0, tzinfo=kst)

        # DB 저장이 UTC 기준이므로 UTC 시각 범위로 변환
        start_dt_utc = start_dt_kst.astimezone(UTC)
        end_dt_utc = end_dt_kst.astimezone(UTC)

        def to_kst_date_str(dt: datetime | None) -> str:
            if not dt:
                return f"{year}-{str(month).zfill(2)}-01"
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return dt.astimezone(kst).strftime("%Y-%m-%d")

        # 2. 관련 도서 사전 일괄 로딩을 위한 Set
        referenced_book_ids: set[int] = set()

        # 2-1. 독서 세션 (record.reading_sessions)
        sessions_stmt = (
            select(ReadingSession)
            .where(
                ReadingSession.member_id == member_id,
                ReadingSession.created_at >= start_dt_utc,
                ReadingSession.created_at < end_dt_utc,
            )
            .order_by(desc(ReadingSession.created_at))
        )
        sessions_res = await db.execute(sessions_stmt)
        sessions = sessions_res.scalars().all()
        for s in sessions:
            if s.book_id:
                referenced_book_ids.add(s.book_id)

        # 2-2. 문장 스크랩 (core.scrap) - 회원의 활성 도서와 JOIN
        scraps_stmt = (
            select(Scrap, LibraryBook)
            .join(LibraryBook, Scrap.book_id == LibraryBook.id)
            .where(
                LibraryBook.member_id == member_id,
                LibraryBook.deleted_at.is_(None),
                Scrap.created_at >= start_dt_utc,
                Scrap.created_at < end_dt_utc,
                Scrap.deleted_at.is_(None),
            )
            .order_by(desc(Scrap.created_at))
        )
        scraps_res = await db.execute(scraps_stmt)
        scraps_with_books = scraps_res.all()
        for scrap, book in scraps_with_books:
            referenced_book_ids.add(book.id)

        # 2-3. 독서 감상문 (record.records)
        records_stmt = (
            select(Record)
            .where(
                Record.member_id == member_id,
                Record.created_at >= start_dt_utc,
                Record.created_at < end_dt_utc,
                Record.deleted_at.is_(None),
            )
            .order_by(desc(Record.created_at))
        )
        records_res = await db.execute(records_stmt)
        records = records_res.scalars().all()
        for r in records:
            if r.book_id:
                referenced_book_ids.add(r.book_id)

        # 2-4. 해당 월에 등록된 도서 (core.library_book)
        registered_books_stmt = (
            select(LibraryBook)
            .where(
                LibraryBook.member_id == member_id,
                LibraryBook.created_at >= start_dt_utc,
                LibraryBook.created_at < end_dt_utc,
                LibraryBook.deleted_at.is_(None),
            )
            .order_by(desc(LibraryBook.created_at))
        )
        registered_books_res = await db.execute(registered_books_stmt)
        registered_books = registered_books_res.scalars().all()
        for b in registered_books:
            referenced_book_ids.add(b.id)

        # 3. 도서 정보(title, cover_url 등) 배치 조회로 N+1 방지
        books_map: dict[int, LibraryBook] = {}
        if referenced_book_ids:
            books_batch_stmt = select(LibraryBook).where(
                LibraryBook.id.in_(referenced_book_ids)
            )
            books_batch_res = await db.execute(books_batch_stmt)
            for b in books_batch_res.scalars().all():
                books_map[b.id] = b

        # 4. 통합 활동 목록 구성
        activities: list[ReadingCalendarActivityItem] = []

        # (1) 독서 세션 항목
        for s in sessions:
            bk = books_map.get(s.book_id) if s.book_id else None
            dur_sec = s.duration_seconds or (s.duration_minutes * 60)
            dur_min = s.duration_minutes or (dur_sec // 60)
            time_label = f"{dur_min}분" if dur_min > 0 else f"{dur_sec}초"
            book_t = bk.title if bk else (s.memo or "독서 세션")
            title = f"{book_t} — {time_label} 독서" if bk else f"{time_label} 집중 독서"
            desc_text = s.memo or f"{time_label} 집중 독서 기록"

            activities.append(
                ReadingCalendarActivityItem(
                    id=f"session-{s.id}",
                    date=to_kst_date_str(s.created_at),
                    type="TIMER_SESSION",
                    title=title,
                    desc=desc_text,
                    memo=s.memo,
                    book_id=s.book_id,
                    book_title=bk.title if bk else None,
                    book_cover_url=bk.cover_url if bk else None,
                    duration_seconds=dur_sec,
                    page_number=s.end_page,
                    weather=s.weather,
                    created_at=s.created_at,
                )
            )

        # (2) 문장 스크랩 항목
        for scrap, bk in scraps_with_books:
            sentence_preview = scrap.sentence.strip()
            if len(sentence_preview) > 40:
                short_sentence = f"{sentence_preview[:40]}..."
            else:
                short_sentence = sentence_preview

            activities.append(
                ReadingCalendarActivityItem(
                    id=f"scrap-{scrap.id}",
                    date=to_kst_date_str(scrap.created_at),
                    type="SENTENCE_SCRAP",
                    title=f"문장 수집: “{short_sentence}”",
                    desc=scrap.sentence,
                    memo=scrap.memo,
                    book_id=bk.id,
                    book_title=bk.title,
                    book_cover_url=bk.cover_url,
                    duration_seconds=None,
                    page_number=scrap.page_number,
                    weather=None,
                    created_at=scrap.created_at,
                )
            )

        # (3) 독서 감상문 항목
        for r in records:
            bk = books_map.get(r.book_id)
            title = r.title or (f"{bk.title} 감상 기록" if bk else "독서 감상 기록")
            activities.append(
                ReadingCalendarActivityItem(
                    id=f"record-{r.id}",
                    date=to_kst_date_str(r.created_at),
                    type="READING_RECORD",
                    title=title,
                    desc=r.content,
                    memo=None,
                    book_id=r.book_id,
                    book_title=bk.title if bk else None,
                    book_cover_url=bk.cover_url if bk else None,
                    duration_seconds=None,
                    page_number=None,
                    weather=r.weather,
                    created_at=r.created_at,
                )
            )

        # (4) 도서 등록 항목
        for b in registered_books:
            activities.append(
                ReadingCalendarActivityItem(
                    id=f"book-{b.id}",
                    date=to_kst_date_str(b.created_at),
                    type="BOOK_REGISTERED",
                    title=f"도서 등록: {b.title}",
                    desc=f"{b.author or '저자 미입력'} | {b.publisher or '출판사 미입력'}",
                    memo=None,
                    book_id=b.id,
                    book_title=b.title,
                    book_cover_url=b.cover_url,
                    duration_seconds=None,
                    page_number=b.current_page,
                    weather=None,
                    created_at=b.created_at,
                )
            )

        # 5. 시간 역순 (최신순) 정렬
        activities.sort(key=lambda x: x.created_at, reverse=True)

        return ReadingCalendarResponse(
            year=year,
            month=month,
            activities=activities,
        )
