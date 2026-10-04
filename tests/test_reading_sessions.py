from datetime import UTC

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import BookReadingStatus, GenreType
from app.models.library_book import LibraryBook
from app.models.shelf import Shelf
from tests.conftest import OTHER_MEMBER_ID, TEST_MEMBER_ID


@pytest.mark.asyncio
async def test_create_reading_session_free_reading(client: AsyncClient):
    """도서 미지정 (자유 독서) 세션 기록 성공 검증"""
    payload = {
        "durationMinutes": 45,
        "weather": "rainy",
    }
    resp = await client.post("/api/v1/reading-sessions", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["durationMinutes"] == 45
    assert data["durationSeconds"] == 2700
    assert data["weather"] == "rainy"
    assert data["bookId"] is None
    assert data["bookTitle"] is None
    assert data["updatedCurrentPage"] is None


@pytest.mark.asyncio
async def test_create_reading_session_with_book_progress(
    client: AsyncClient, db_session: AsyncSession
):
    """도서 지정 독서 세션 기록 및 진도율/상태 자동 갱신 검증"""
    # 1. 기본 책장 및 도서 준비
    shelf = Shelf(
        member_id=TEST_MEMBER_ID,
        name="기본 책장",
        is_default=True,
    )
    db_session.add(shelf)
    await db_session.flush()

    book = LibraryBook(
        member_id=TEST_MEMBER_ID,
        shelf_id=shelf.id,
        shelf_rank="0|hzzzzz:",
        title="데미안",
        author="헤르만 헤세",
        genre=GenreType.LITERATURE,
        total_pages=280,
        current_page=0,
        reading_status=BookReadingStatus.PLANNED,
    )
    db_session.add(book)
    await db_session.commit()
    await db_session.refresh(book)

    # 2. 독서 세션 저장 (0p -> 50p 독서)
    payload = {
        "bookId": book.id,
        "durationMinutes": 30,
        "endPage": 50,
        "weather": "clear",
    }
    resp = await client.post("/api/v1/reading-sessions", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["durationMinutes"] == 30
    assert data["durationSeconds"] == 1800
    assert data["bookId"] == book.id
    assert data["bookTitle"] == "데미안"
    assert data["startPage"] == 0
    assert data["endPage"] == 50
    assert data["updatedCurrentPage"] == 50
    assert data["progress"] == 17.9
    assert data["bookReadingStatus"] == "READING"

    # DB 도서 상태 확인
    await db_session.refresh(book)
    assert book.current_page == 50
    assert book.reading_status == BookReadingStatus.READING


@pytest.mark.asyncio
async def test_create_book_reading_session_and_list(
    client: AsyncClient, db_session: AsyncSession
):
    """POST /api/v1/books/{id}/reading-sessions 및 GET /api/v1/books/{id}/reading-sessions 전수 검증"""
    shelf = Shelf(
        member_id=TEST_MEMBER_ID,
        name="기본 책장",
        is_default=True,
    )
    db_session.add(shelf)
    await db_session.flush()

    book = LibraryBook(
        member_id=TEST_MEMBER_ID,
        shelf_id=shelf.id,
        shelf_rank="0|hzzzzz:",
        title="클린 코드",
        author="로버트 C. 마틴",
        genre=GenreType.TECHNOLOGY,
        total_pages=400,
        current_page=20,
        reading_status=BookReadingStatus.READING,
    )
    db_session.add(book)
    await db_session.commit()
    await db_session.refresh(book)

    # 1. 1차 세션 등록 (durationSeconds + memo + startPage/endPage)
    session1_payload = {
        "durationSeconds": 1680,
        "startTime": "2026-09-17T13:30:00Z",
        "endTime": "2026-09-17T13:58:00Z",
        "startPage": 20,
        "endPage": 60,
        "memo": "점심 시간 짬내서 집중 독서",
        "weather": "clear",
    }
    resp1 = await client.post(
        f"/api/v1/books/{book.id}/reading-sessions", json=session1_payload
    )
    assert resp1.status_code == 201
    d1 = resp1.json()
    assert d1["durationSeconds"] == 1680
    assert d1["durationMinutes"] == 28
    assert d1["memo"] == "점심 시간 짬내서 집중 독서"
    assert d1["updatedCurrentPage"] == 60
    assert d1["progress"] == 15.0
    assert d1["bookReadingStatus"] == "READING"

    # 2. 2차 세션 등록 (duration + pageNumber 호환)
    session2_payload = {
        "duration": 1200,
        "pageNumber": 100,
        "memo": "퇴근 후 카페 독서",
    }
    resp2 = await client.post(
        f"/api/v1/books/{book.id}/reading-sessions", json=session2_payload
    )
    assert resp2.status_code == 201
    d2 = resp2.json()
    assert d2["durationSeconds"] == 1200
    assert d2["durationMinutes"] == 20
    assert d2["endPage"] == 100
    assert d2["updatedCurrentPage"] == 100
    assert d2["progress"] == 25.0

    # 3. 3차 세션 등록 (13초 독서 -> 0분 13초 정확 보존 검증)
    session3_payload = {
        "durationSeconds": 13,
        "pageNumber": 105,
        "memo": "짧은 13초 독서",
    }
    resp3 = await client.post(
        f"/api/v1/books/{book.id}/reading-sessions", json=session3_payload
    )
    assert resp3.status_code == 201
    d3 = resp3.json()
    assert d3["durationSeconds"] == 13
    assert d3["durationMinutes"] == 0  # 1분 올림 왜곡 없이 정확히 0분
    assert d3["endPage"] == 105
    assert d3["pageNumber"] == 105
    assert d3["page"] == 105
    assert d3["updatedCurrentPage"] == 105

    # 4. 도서 세션 목록 조회 (GET /api/v1/books/{id}/reading-sessions)
    list_resp = await client.get(f"/api/v1/books/{book.id}/reading-sessions")
    assert list_resp.status_code == 200
    list_data = list_resp.json()
    assert list_data["bookId"] == book.id
    assert list_data["sessionCount"] == 3
    assert list_data["totalDurationSeconds"] == 2893  # 1680 + 1200 + 13
    assert list_data["totalDurationMinutes"] == 48  # 28 + 20 + 0
    assert len(list_data["sessions"]) == 3
    # 최신순 확인 (session3가 가장 먼저)
    assert list_data["sessions"][0]["id"] == d3["id"]
    assert list_data["sessions"][1]["id"] == d2["id"]
    assert list_data["sessions"][2]["id"] == d1["id"]

    # 5. 도서 상태 확인
    await db_session.refresh(book)
    assert book.current_page == 105


@pytest.mark.asyncio
async def test_create_reading_session_reaches_completion(
    client: AsyncClient, db_session: AsyncSession
):
    """진도율 100% 도달 시 COMPLETED 자동 전이 및 completed_at 기록 검증"""
    shelf = Shelf(
        member_id=TEST_MEMBER_ID,
        name="기본 책장",
        is_default=True,
    )
    db_session.add(shelf)
    await db_session.flush()

    book = LibraryBook(
        member_id=TEST_MEMBER_ID,
        shelf_id=shelf.id,
        shelf_rank="0|hzzzzz:",
        title="어린 왕자",
        author="생텍쥐페리",
        genre=GenreType.LITERATURE,
        total_pages=150,
        current_page=120,
        reading_status=BookReadingStatus.READING,
    )
    db_session.add(book)
    await db_session.commit()

    # 150p 완독 세션 저장
    payload = {
        "durationMinutes": 40,
        "startPage": 120,
        "endPage": 150,
    }
    resp = await client.post(f"/api/v1/books/{book.id}/reading-sessions", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["bookReadingStatus"] == "COMPLETED"
    assert data["updatedCurrentPage"] == 150
    assert data["progress"] == 100.0

    await db_session.refresh(book)
    assert book.reading_status == BookReadingStatus.COMPLETED
    assert book.completed_at is not None


@pytest.mark.asyncio
async def test_create_reading_session_book_not_found(client: AsyncClient):
    """존재하지 않는 도서 ID 지정 시 404 에러 검증"""
    payload = {
        "durationSeconds": 1200,
    }
    resp = await client.post("/api/v1/books/999999/reading-sessions", json=payload)
    assert resp.status_code == 404
    assert resp.json()["code"] == "LIBRARY_BOOK_NOT_FOUND"


@pytest.mark.asyncio
async def test_create_reading_session_other_member_book(
    client: AsyncClient, db_session: AsyncSession
):
    """타인의 도서 ID 지정 시 403 (접근 권한 없음) 검증"""
    shelf = Shelf(
        member_id=OTHER_MEMBER_ID,
        name="타인의 책장",
        is_default=True,
    )
    db_session.add(shelf)
    await db_session.flush()

    book = LibraryBook(
        member_id=OTHER_MEMBER_ID,
        shelf_id=shelf.id,
        shelf_rank="0|hzzzzz:",
        title="타인의 책",
        author="저자",
        genre=GenreType.LITERATURE,
    )
    db_session.add(book)
    await db_session.commit()

    payload = {
        "durationSeconds": 1500,
    }
    resp = await client.post(f"/api/v1/books/{book.id}/reading-sessions", json=payload)
    assert resp.status_code == 403
    assert resp.json()["code"] == "LIBRARY_BOOK_ACCESS_DENIED"

    # GET 요청 시에도 403 검증
    get_resp = await client.get(f"/api/v1/books/{book.id}/reading-sessions")
    assert get_resp.status_code == 403
    assert get_resp.json()["code"] == "LIBRARY_BOOK_ACCESS_DENIED"


@pytest.mark.asyncio
async def test_get_reading_calendar_monthly_activities(
    client: AsyncClient, db_session: AsyncSession
):
    """GET /api/v1/reading-sessions/calendar: 세션, 스크랩, 감상문, 도서등록 통합 조회 검증"""
    from datetime import datetime

    from app.models.reading_session import ReadingSession
    from app.models.record import Record
    from app.models.scrap import Scrap

    # 1. 2026-10월에 등록된 책 및 과거 책 준비
    shelf = Shelf(
        member_id=TEST_MEMBER_ID,
        name="기본 책장",
        is_default=True,
    )
    db_session.add(shelf)
    await db_session.flush()

    # 10월 등록 도서 (KST 10월 4일 10:00 -> UTC 10월 4일 01:00)
    oct_book = LibraryBook(
        member_id=TEST_MEMBER_ID,
        shelf_id=shelf.id,
        shelf_rank="0|hzzzzz:",
        title="소년이 온다",
        author="한강",
        genre=GenreType.LITERATURE,
        cover_url="https://example.com/cover1.jpg",
        total_pages=216,
        current_page=120,
        reading_status=BookReadingStatus.READING,
        created_at=datetime(2026, 10, 4, 1, 0, 0, tzinfo=UTC),
    )
    db_session.add(oct_book)
    await db_session.flush()

    # 2. 독서 세션 (10월 4일)
    session = ReadingSession(
        member_id=TEST_MEMBER_ID,
        book_id=oct_book.id,
        duration_seconds=2100,
        duration_minutes=35,
        start_page=80,
        end_page=120,
        memo="35분 집중 독서 기록",
        weather="clear",
        created_at=datetime(2026, 10, 4, 6, 30, 0, tzinfo=UTC),  # KST 15:30
    )
    db_session.add(session)

    # 3. 문장 스크랩 (10월 4일)
    scrap = Scrap(
        book_id=oct_book.id,
        sentence="네가 죽은 뒤 장례식을 치르지 못해...",
        page_number=120,
        scrap_image_url="https://example.com/scrap1.jpg",
        memo="인상적인 도입부",
        created_at=datetime(2026, 10, 4, 7, 0, 0, tzinfo=UTC),  # KST 16:00
    )
    db_session.add(scrap)

    # 4. 감상 기록 (10월 5일)
    record = Record(
        member_id=TEST_MEMBER_ID,
        book_id=oct_book.id,
        title="소년이 온다 감상문",
        content="마음이 먹먹해지는 이야기였습니다.",
        rating=5,
        weather="clear",
        created_at=datetime(2026, 10, 5, 2, 0, 0, tzinfo=UTC),  # KST 11:00
    )
    db_session.add(record)

    # 5. 다른 월 (9월) 활동 추가 (10월 조회 시 필터링되어야 함)
    sep_session = ReadingSession(
        member_id=TEST_MEMBER_ID,
        book_id=oct_book.id,
        duration_seconds=1800,
        duration_minutes=30,
        created_at=datetime(2026, 9, 20, 5, 0, 0, tzinfo=UTC),
    )
    db_session.add(sep_session)

    # 6. 타인의 활동 추가 (조회되지 않아야 함)
    other_session = ReadingSession(
        member_id=OTHER_MEMBER_ID,
        book_id=None,
        duration_seconds=1200,
        duration_minutes=20,
        created_at=datetime(2026, 10, 4, 6, 0, 0, tzinfo=UTC),
    )
    db_session.add(other_session)

    await db_session.commit()

    # 7. 2026년 10월 캘린더 조회
    resp = await client.get("/api/v1/reading-sessions/calendar?year=2026&month=10")
    assert resp.status_code == 200
    data = resp.json()

    assert data["year"] == 2026
    assert data["month"] == 10
    activities = data["activities"]

    # 10월 활동 4건 (감상문, 스크랩, 세션, 도서등록)
    assert len(activities) == 4

    types = [a["type"] for a in activities]
    assert "READING_RECORD" in types
    assert "SENTENCE_SCRAP" in types
    assert "TIMER_SESSION" in types
    assert "BOOK_REGISTERED" in types

    # 세션 검증
    session_item = next(a for a in activities if a["type"] == "TIMER_SESSION")
    assert session_item["id"] == f"session-{session.id}"
    assert session_item["date"] == "2026-10-04"
    assert session_item["bookId"] == oct_book.id
    assert session_item["bookTitle"] == "소년이 온다"
    assert session_item["bookCoverUrl"] == "https://example.com/cover1.jpg"
    assert session_item["durationSeconds"] == 2100
    assert session_item["weather"] == "clear"

    # 스크랩 검증
    scrap_item = next(a for a in activities if a["type"] == "SENTENCE_SCRAP")
    assert scrap_item["id"] == f"scrap-{scrap.id}"
    assert scrap_item["date"] == "2026-10-04"
    assert scrap_item["desc"] == "네가 죽은 뒤 장례식을 치르지 못해..."
    assert scrap_item["memo"] == "인상적인 도입부"
    assert scrap_item["bookTitle"] == "소년이 온다"

    # 9월 캘린더 조회 검증 (9월 세션 1건만 존재)
    sep_resp = await client.get("/api/v1/reading-sessions/calendar?year=2026&month=9")
    assert sep_resp.status_code == 200
    sep_data = sep_resp.json()
    assert sep_data["year"] == 2026
    assert sep_data["month"] == 9
    assert len(sep_data["activities"]) == 1
    assert sep_data["activities"][0]["type"] == "TIMER_SESSION"
