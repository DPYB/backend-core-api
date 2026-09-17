from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import BookReadingStatus, GenreType, LibrarianType
from app.models.librarian import Librarian
from app.models.library_book import LibraryBook
from app.models.reading_session import ReadingSession
from app.models.record import Record, RecordScrap
from app.models.shelf import Shelf
from tests.conftest import TEST_MEMBER_ID


@pytest.mark.asyncio
async def test_monthly_report_empty_data(client: AsyncClient):
    """활동 내역이 없는 회원의 월간 리포트 기본 응답 검증"""
    resp = await client.get("/api/v1/reports/monthly-stats?year=2026&month=9")
    assert resp.status_code == 200
    data = resp.json()

    assert data["year"] == 2026
    assert data["month"] == 9
    assert data["librarian"]["name"] == "블루"
    assert data["librarian"]["reportTitle"] == "블루 사서의 월간 독서 리포트"

    # Overview
    assert data["overview"]["completedBooksCount"] == 0
    assert data["overview"]["totalPagesRead"] == 0
    assert data["overview"]["totalDurationMinutes"] == 0
    assert data["overview"]["goalAchievementRate"] == 0.0

    # Habits
    assert data["habits"]["totalSessionCount"] == 0
    assert data["habits"]["avgSessionDurationMinutes"] == 0.0
    assert data["habits"]["longestStreakDays"] == 0
    assert data["habits"]["avgCompletionDays"] is None
    assert "MON" in data["habits"]["weekdayDistribution"]
    assert "dawn" in data["habits"]["timeDistribution"]

    # Balance
    assert data["balance"]["diversityScore"] == 0
    assert len(data["balance"]["unreadGenres"]) == 10

    # Traces
    assert data["traces"]["mostScrappedBooks"] == []
    assert data["traces"]["featuredRecords"] == []
    assert data["traces"]["completedBooks"] == []
    assert data["traces"]["readingBooks"] == []


@pytest.mark.asyncio
async def test_monthly_report_full_aggregation(
    client: AsyncClient, db_session: AsyncSession
):
    """완독, 세션, 스크랩, 감상문이 모두 포함된 9월 종합 통계 검증"""
    # 1. 대표 사서 생성
    librarian = Librarian(
        member_id=TEST_MEMBER_ID,
        type=LibrarianType.CAT,
        name="냥이",
        level=2,
        is_representative=True,
    )
    db_session.add(librarian)

    # 2. 책장 생성
    shelf = Shelf(
        member_id=TEST_MEMBER_ID,
        name="나의 서재",
        is_default=True,
    )
    db_session.add(shelf)
    await db_session.flush()

    # 3. 도서 생성 (완독 2권, 읽는 중 1권)
    book_completed_1 = LibraryBook(
        member_id=TEST_MEMBER_ID,
        shelf_id=shelf.id,
        shelf_rank="0|hzzzzz:",
        title="데미안",
        author="헤르만 헤세",
        genre=GenreType.LITERATURE,
        subject="소설/문학",
        total_pages=280,
        current_page=280,
        reading_status=BookReadingStatus.COMPLETED,
        created_at=datetime(2026, 9, 1, 10, 0, 0, tzinfo=UTC),
        completed_at=datetime(2026, 9, 5, 15, 0, 0, tzinfo=UTC),
    )
    book_completed_2 = LibraryBook(
        member_id=TEST_MEMBER_ID,
        shelf_id=shelf.id,
        shelf_rank="0|hzzzza:",
        title="총 균 쇠",
        author="재레드 다이아몬드",
        genre=GenreType.HISTORY,
        subject="인류학/역사",
        total_pages=500,
        current_page=500,
        reading_status=BookReadingStatus.COMPLETED,
        created_at=datetime(2026, 9, 2, 10, 0, 0, tzinfo=UTC),
        completed_at=datetime(2026, 9, 10, 15, 0, 0, tzinfo=UTC),
    )
    book_reading = LibraryBook(
        member_id=TEST_MEMBER_ID,
        shelf_id=shelf.id,
        shelf_rank="0|hzzzzb:",
        title="코스모스",
        author="칼 세이건",
        genre=GenreType.NATURAL_SCIENCE,
        subject="천문학/과학",
        total_pages=600,
        current_page=120,
        reading_status=BookReadingStatus.READING,
    )
    db_session.add_all([book_completed_1, book_completed_2, book_reading])
    await db_session.flush()

    # 4. 독서 세션 생성 (9월 3건: 40분, 30분, 20분 -> 총 90분)
    session_1 = ReadingSession(
        member_id=TEST_MEMBER_ID,
        book_id=book_completed_1.id,
        duration_minutes=40,
        start_page=0,
        end_page=100,
        weather="clear",
        created_at=datetime(2026, 9, 2, 14, 0, 0, tzinfo=UTC),
    )
    session_2 = ReadingSession(
        member_id=TEST_MEMBER_ID,
        book_id=book_completed_1.id,
        duration_minutes=30,
        start_page=100,
        end_page=200,
        weather="rainy",
        created_at=datetime(2026, 9, 3, 20, 0, 0, tzinfo=UTC),
    )
    session_3 = ReadingSession(
        member_id=TEST_MEMBER_ID,
        book_id=book_completed_2.id,
        duration_minutes=20,
        start_page=0,
        end_page=50,
        weather="rainy",
        created_at=datetime(2026, 9, 4, 23, 0, 0, tzinfo=UTC),
    )
    db_session.add_all([session_1, session_2, session_3])

    # 5. 독서 기록 및 스크랩 생성
    record = Record(
        member_id=TEST_MEMBER_ID,
        book_id=book_completed_1.id,
        title="데미안을 읽고",
        content="새는 알을 깨고 나온다. 알은 세계이다. 태어나려는 자는 하나의 세계를 파괴해야 한다.",
        rating=5,
        weather="clear",
        created_at=datetime(2026, 9, 5, 16, 0, 0, tzinfo=UTC),
    )
    db_session.add(record)
    await db_session.flush()

    scrap_1 = RecordScrap(
        record_id=record.id,
        member_id=TEST_MEMBER_ID,
        book_id=book_completed_1.id,
        sentence="내 속에서 솟아 나오려는 것, 바로 그것을 나는 살아보려 했다.",
        page_number=12,
        created_at=datetime(2026, 9, 3, 11, 0, 0, tzinfo=UTC),
    )
    scrap_2 = RecordScrap(
        record_id=record.id,
        member_id=TEST_MEMBER_ID,
        book_id=book_completed_1.id,
        sentence="새는 신에게로 날아간다. 그 신의 이름은 아브락사스다.",
        page_number=145,
        created_at=datetime(2026, 9, 4, 11, 0, 0, tzinfo=UTC),
    )
    db_session.add_all([scrap_1, scrap_2])
    await db_session.commit()

    # 6. 월간 통계 조회 API 호출
    resp = await client.get("/api/v1/reports/monthly-stats?year=2026&month=9")
    assert resp.status_code == 200
    data = resp.json()

    # 사서
    assert data["librarian"]["name"] == "냥이"
    assert data["librarian"]["reportTitle"] == "냥이 사서의 월간 독서 리포트"

    # 01. Overview
    assert data["overview"]["completedBooksCount"] == 2
    assert data["overview"]["totalDurationMinutes"] == 90
    assert data["overview"]["totalPagesRead"] == 250  # 100 + 100 + 50
    assert data["overview"]["goalAchievementRate"] == 66.7

    # 02. Habits
    assert data["habits"]["totalSessionCount"] == 3
    assert data["habits"]["avgSessionDurationMinutes"] == 30.0  # (40 + 30 + 20) / 3
    assert data["habits"]["weatherDistribution"]["rainy"] == 2
    assert data["habits"]["weatherDistribution"]["clear"] == 2  # session 1 + record 1
    assert data["habits"]["longestStreakDays"] == 4  # 9/2, 9/3, 9/4, 9/5 연속 4일!
    assert data["habits"]["avgCompletionDays"] is not None

    # 03. Preferences
    genre_names = [g["genreName"] for g in data["preferences"]["topGenres"]]
    assert "문학" in genre_names
    assert "역사" in genre_names
    assert len(data["preferences"]["weatherPreferences"]) > 0

    # 04. Balance
    assert data["balance"]["diversityScore"] >= 20
    assert "철학" in data["balance"]["unreadGenres"]

    # 05. Traces
    assert len(data["traces"]["completedBooks"]) == 2
    assert len(data["traces"]["readingBooks"]) == 1
    assert data["traces"]["readingBooks"][0]["title"] == "코스모스"
    assert len(data["traces"]["mostScrappedBooks"]) == 1
    assert data["traces"]["mostScrappedBooks"][0]["title"] == "데미안"
    assert data["traces"]["mostScrappedBooks"][0]["scrapCount"] == 2
    assert len(data["traces"]["featuredRecords"]) == 1
    assert data["traces"]["featuredRecords"][0]["rating"] == 5
