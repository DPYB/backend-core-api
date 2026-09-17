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
