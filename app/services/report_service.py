from collections import Counter
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import BookReadingStatus, GenreType, LibrarianType
from app.models.librarian import Librarian
from app.models.library_book import LibraryBook
from app.models.reading_session import ReadingSession
from app.models.record import Record, RecordScrap
from app.schemas.report import (
    FeaturedRecordItem,
    GenreBalanceItem,
    GenrePreferenceItem,
    LibrarianReportInfo,
    MonthlyOverview,
    MonthlyReportStatsResponse,
    ReadingBalance,
    ReadingHabits,
    ReadingPreferences,
    ReadingTraces,
    ReportBookSummary,
    ScrappedBookItem,
    WeatherPreferenceItem,
)

GENRE_NAMES: dict[GenreType, str] = {
    GenreType.NONE: "기타",
    GenreType.GENERAL: "총류",
    GenreType.PHILOSOPHY: "철학",
    GenreType.RELIGION: "종교",
    GenreType.SOCIAL_SCIENCE: "사회과학",
    GenreType.NATURAL_SCIENCE: "자연과학",
    GenreType.TECHNOLOGY: "기술과학",
    GenreType.ARTS: "예술",
    GenreType.LANGUAGE: "언어",
    GenreType.LITERATURE: "문학",
    GenreType.HISTORY: "역사",
}

KDC_10_GENRES: list[GenreType] = [
    GenreType.GENERAL,
    GenreType.PHILOSOPHY,
    GenreType.RELIGION,
    GenreType.SOCIAL_SCIENCE,
    GenreType.NATURAL_SCIENCE,
    GenreType.TECHNOLOGY,
    GenreType.ARTS,
    GenreType.LANGUAGE,
    GenreType.LITERATURE,
    GenreType.HISTORY,
]


class ReportService:
    @staticmethod
    async def get_monthly_stats(
        db: AsyncSession,
        member_id: UUID,
        year: int,
        month: int,
    ) -> MonthlyReportStatsResponse:
        # 1. 대상 기간 계산 (UTC 기준 월 범위)
        start_dt = datetime(year, month, 1, 0, 0, 0, tzinfo=UTC)
        if month == 12:
            end_dt = datetime(year + 1, 1, 1, 0, 0, 0, tzinfo=UTC)
        else:
            end_dt = datetime(year, month + 1, 1, 0, 0, 0, tzinfo=UTC)

        # 2. 대표 사서 정보 조회
        lib_stmt = (
            select(Librarian)
            .where(
                Librarian.member_id == member_id,
                Librarian.deleted_at.is_(None),
            )
            .order_by(desc(Librarian.is_representative), Librarian.id)
        )
        librarian_res = (await db.execute(lib_stmt)).scalars().first()
        if librarian_res:
            lib_info = LibrarianReportInfo(
                type=librarian_res.type,
                name=librarian_res.name,
                level=librarian_res.level,
                report_title=f"{librarian_res.name} 사서의 월간 독서 리포트",
            )
        else:
            lib_info = LibrarianReportInfo(
                type=LibrarianType.CAT,
                name="블루",
                level=1,
                report_title="블루 사서의 월간 독서 리포트",
            )

        # 3. 해당 월 독서 세션 조회
        sessions_stmt = select(ReadingSession).where(
            ReadingSession.member_id == member_id,
            ReadingSession.created_at >= start_dt,
            ReadingSession.created_at < end_dt,
        )
        sessions = (await db.execute(sessions_stmt)).scalars().all()

        # 4. 해당 월 완독 도서 조회
        completed_stmt = select(LibraryBook).where(
            LibraryBook.member_id == member_id,
            LibraryBook.reading_status == BookReadingStatus.COMPLETED,
            LibraryBook.completed_at >= start_dt,
            LibraryBook.completed_at < end_dt,
            LibraryBook.deleted_at.is_(None),
        )
        completed_books = (await db.execute(completed_stmt)).scalars().all()

        # 5. 현재 읽는 중인 도서 조회
        reading_stmt = select(LibraryBook).where(
            LibraryBook.member_id == member_id,
            LibraryBook.reading_status == BookReadingStatus.READING,
            LibraryBook.deleted_at.is_(None),
        )
        reading_books = (await db.execute(reading_stmt)).scalars().all()

        # 6. 해당 월 독서 감상 기록 조회
        records_stmt = (
            select(Record)
            .where(
                Record.member_id == member_id,
                Record.created_at >= start_dt,
                Record.created_at < end_dt,
                Record.deleted_at.is_(None),
            )
            .order_by(desc(Record.rating), desc(Record.created_at))
        )
        records = (await db.execute(records_stmt)).scalars().all()

        # 7. 해당 월 스크랩 조회
        scraps_stmt = select(RecordScrap).where(
            RecordScrap.member_id == member_id,
            RecordScrap.created_at >= start_dt,
            RecordScrap.created_at < end_dt,
            RecordScrap.deleted_at.is_(None),
        )
        scraps = (await db.execute(scraps_stmt)).scalars().all()

        # --- 01. 이번 달 한눈에 보기 (Overview) ---
        completed_count = len(completed_books)

        # 누적 독서 페이지: 세션들의 읽은 페이지 합계 (또는 완독 도서 페이지 폴백)
        session_pages = 0
        for s in sessions:
            if (
                s.end_page is not None
                and s.start_page is not None
                and s.end_page >= s.start_page
            ):
                session_pages += s.end_page - s.start_page
            elif s.end_page is not None:
                session_pages += s.end_page

        if session_pages > 0:
            total_pages_read = session_pages
        else:
            total_pages_read = sum(
                b.current_page or b.total_pages or 0 for b in completed_books
            )

        total_duration = sum(s.duration_minutes for s in sessions)
        goal_books = 3
        goal_rate = (
            min(100.0, round((completed_count / goal_books) * 100, 1))
            if goal_books > 0
            else 0.0
        )

        overview = MonthlyOverview(
            completed_books_count=completed_count,
            total_pages_read=total_pages_read,
            total_duration_minutes=total_duration,
            goal_books_count=goal_books,
            goal_achievement_rate=goal_rate,
        )

        # --- 02. 나의 독서 습관/리듬 (Habits) ---
        weekday_counts = {
            "MON": 0,
            "TUE": 0,
            "WED": 0,
            "THU": 0,
            "FRI": 0,
            "SAT": 0,
            "SUN": 0,
        }
        weekday_map = {
            0: "MON",
            1: "TUE",
            2: "WED",
            3: "THU",
            4: "FRI",
            5: "SAT",
            6: "SUN",
        }
        time_counts = {"dawn": 0, "day": 0, "evening": 0, "night": 0}
        weather_counts: Counter[str] = Counter()
        active_dates: set[str] = set()

        # 세션 기반 집계
        for s in sessions:
            active_dates.add(s.created_at.strftime("%Y-%m-%d"))
            weekday_counts[weekday_map[s.created_at.weekday()]] += 1
            hour = s.created_at.hour
            if 0 <= hour < 6:
                time_counts["dawn"] += 1
            elif 6 <= hour < 18:
                time_counts["day"] += 1
            elif 18 <= hour < 22:
                time_counts["evening"] += 1
            else:
                time_counts["night"] += 1

            if s.weather:
                weather_counts[s.weather] += 1

        # 감상 기록 기반 보강
        for r in records:
            active_dates.add(r.created_at.strftime("%Y-%m-%d"))
            if not sessions:
                weekday_counts[weekday_map[r.created_at.weekday()]] += 1
                hour = r.created_at.hour
                if 0 <= hour < 6:
                    time_counts["dawn"] += 1
                elif 6 <= hour < 18:
                    time_counts["day"] += 1
                elif 18 <= hour < 22:
                    time_counts["evening"] += 1
                else:
                    time_counts["night"] += 1

            if r.weather:
                weather_counts[r.weather] += 1

        # 완독 도서 평균 완독 소요 기간
        completion_days_list: list[float] = []
        for b in completed_books:
            if b.completed_at and b.created_at:
                diff_days = max(
                    1.0, (b.completed_at - b.created_at).total_seconds() / 86400.0
                )
                completion_days_list.append(diff_days)

        avg_completion = (
            round(sum(completion_days_list) / len(completion_days_list), 1)
            if completion_days_list
            else None
        )

        # 최장 Streak 계산
        sorted_dates = sorted(active_dates)
        longest_streak = 0
        current_streak = 0
        prev_date = None
        for d_str in sorted_dates:
            curr_date = datetime.strptime(d_str, "%Y-%m-%d").date()
            if prev_date is None:
                current_streak = 1
            elif (curr_date - prev_date).days == 1:
                current_streak += 1
            else:
                current_streak = 1
            prev_date = curr_date
            if current_streak > longest_streak:
                longest_streak = current_streak

        habits = ReadingHabits(
            weekday_distribution=weekday_counts,
            time_distribution=time_counts,
            weather_distribution=dict(weather_counts),
            avg_completion_days=avg_completion,
            longest_streak_days=longest_streak,
        )

        # --- 03. 나의 독서 취향 & 04. 독서 밸런스 ---
        # 이번 달 회원이 접한 도서들의 ID 집합 (완독 도서 + 세션 도서 + 감상 기록 도서)
        encountered_book_ids: set[int] = {b.id for b in completed_books}
        for s in sessions:
            if s.book_id:
                encountered_book_ids.add(s.book_id)
        for r in records:
            encountered_book_ids.add(r.book_id)

        all_encountered_books: list[LibraryBook] = []
        if encountered_book_ids:
            books_stmt = select(LibraryBook).where(
                LibraryBook.id.in_(encountered_book_ids),
                LibraryBook.deleted_at.is_(None),
            )
            all_encountered_books = list((await db.execute(books_stmt)).scalars().all())

        # 책 ID -> 도서 객체 맵
        book_map: dict[int, LibraryBook] = {b.id: b for b in all_encountered_books}

        # 장르별 / 세부 주제별 카운트
        genre_counter: Counter[GenreType] = Counter()
        subject_counter: Counter[str] = Counter()

        for b in all_encountered_books:
            genre_counter[b.genre] += 1
            if b.subject:
                subject_counter[b.subject] += 1

        total_genre_books = sum(genre_counter.values())

        # 선호 장르 리스트
        top_genres: list[GenrePreferenceItem] = []
        for g, cnt in genre_counter.most_common(5):
            pct = (
                round((cnt / total_genre_books) * 100, 1)
                if total_genre_books > 0
                else 0.0
            )
            top_genres.append(
                GenrePreferenceItem(
                    genre=g,
                    genre_name=GENRE_NAMES.get(g, "기타"),
                    count=cnt,
                    percentage=pct,
                )
            )

        top_subjects = [s for s, _ in subject_counter.most_common(5)]

        # 날씨별 선호 장르 및 도서
        weather_book_counter: dict[str, Counter[int]] = {}
        weather_genre_counter: dict[str, Counter[GenreType]] = {}
        for s in sessions:
            if s.weather and s.book_id and s.book_id in book_map:
                w = s.weather
                if w not in weather_book_counter:
                    weather_book_counter[w] = Counter()
                    weather_genre_counter[w] = Counter()
                weather_book_counter[w][s.book_id] += 1
                weather_genre_counter[w][book_map[s.book_id].genre] += 1

        weather_preferences: list[WeatherPreferenceItem] = []
        for w, b_counts in weather_book_counter.items():
            top_b_id = b_counts.most_common(1)[0][0]
            top_b = book_map.get(top_b_id)
            top_g = weather_genre_counter[w].most_common(1)[0][0]
            weather_preferences.append(
                WeatherPreferenceItem(
                    weather=w,
                    session_count=sum(b_counts.values()),
                    top_genre=top_g,
                    top_genre_name=GENRE_NAMES.get(top_g, "기타"),
                    preferred_book_title=top_b.title if top_b else None,
                )
            )

        preferences = ReadingPreferences(
            top_genres=top_genres,
            top_subjects=top_subjects,
            weather_preferences=weather_preferences,
        )

        # 04. 독서 밸런스 분석 (KDC 10대 장르)
        genre_breakdown: list[GenreBalanceItem] = []
        read_kdc_count = 0
        unread_genres: list[str] = []
        dominant_genre_name: str | None = None
        max_pct = 0.0

        for kdc_g in KDC_10_GENRES:
            cnt = genre_counter.get(kdc_g, 0)
            pct = (
                round((cnt / total_genre_books) * 100, 1)
                if total_genre_books > 0
                else 0.0
            )
            g_name = GENRE_NAMES[kdc_g]
            genre_breakdown.append(
                GenreBalanceItem(
                    genre=kdc_g,
                    genre_name=g_name,
                    count=cnt,
                    percentage=pct,
                )
            )
            if cnt > 0:
                read_kdc_count += 1
                if pct > max_pct:
                    max_pct = pct
                    dominant_genre_name = g_name
            else:
                unread_genres.append(g_name)

        # 다양성 점수: KDC 10대 장르 중 읽은 장르 수 * 10
        diversity_score = read_kdc_count * 10
        is_biased = max_pct >= 60.0 and total_genre_books >= 2

        balance = ReadingBalance(
            genre_breakdown=genre_breakdown,
            dominant_genre=dominant_genre_name,
            is_biased=is_biased,
            diversity_score=diversity_score,
            unread_genres=unread_genres,
        )

        # --- 05. 내가 남긴 독서 흔적 (Traces) ---
        # 스크랩이 가장 많은 책 Top 3
        scrap_book_counter = Counter(s.book_id for s in scraps)
        most_scrapped: list[ScrappedBookItem] = []
        for b_id, s_cnt in scrap_book_counter.most_common(3):
            # book_map에 없으면 조회
            target_b = book_map.get(b_id)
            if not target_b:
                target_b = (
                    await db.execute(select(LibraryBook).where(LibraryBook.id == b_id))
                ).scalar_one_or_none()
            if target_b:
                most_scrapped.append(
                    ScrappedBookItem(
                        book_id=target_b.id,
                        title=target_b.title,
                        author=target_b.author,
                        cover_url=target_b.cover_url,
                        display_genre=target_b.subject
                        or GENRE_NAMES.get(target_b.genre),
                        scrap_count=s_cnt,
                    )
                )

        # 인상 깊은 감상평 (별점 높은 순 상위 3건)
        featured_records: list[FeaturedRecordItem] = []
        for r in records[:3]:
            snippet = r.content[:80] + "..." if len(r.content) > 80 else r.content
            featured_records.append(
                FeaturedRecordItem(
                    record_id=r.id,
                    book_id=r.book_id,
                    title=r.title,
                    content_snippet=snippet,
                    rating=r.rating,
                    weather=r.weather,
                    created_at=r.created_at,
                )
            )

        completed_summaries = [
            ReportBookSummary(
                book_id=b.id,
                title=b.title,
                author=b.author,
                cover_url=b.cover_url,
                display_genre=b.subject or GENRE_NAMES.get(b.genre),
                current_page=b.current_page,
                total_pages=b.total_pages,
                completed_at=b.completed_at,
            )
            for b in completed_books
        ]

        reading_summaries = [
            ReportBookSummary(
                book_id=b.id,
                title=b.title,
                author=b.author,
                cover_url=b.cover_url,
                display_genre=b.subject or GENRE_NAMES.get(b.genre),
                current_page=b.current_page,
                total_pages=b.total_pages,
                completed_at=b.completed_at,
            )
            for b in reading_books
        ]

        traces = ReadingTraces(
            most_scrapped_books=most_scrapped,
            featured_records=featured_records,
            completed_books=completed_summaries,
            reading_books=reading_summaries,
        )

        return MonthlyReportStatsResponse(
            year=year,
            month=month,
            member_id=member_id,
            librarian=lib_info,
            overview=overview,
            habits=habits,
            preferences=preferences,
            balance=balance,
            traces=traces,
        )
