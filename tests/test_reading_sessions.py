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
    assert data["bookId"] == book.id
    assert data["bookTitle"] == "데미안"
    assert data["startPage"] == 0
    assert data["endPage"] == 50
    assert data["updatedCurrentPage"] == 50
    assert data["bookReadingStatus"] == "READING"

    # DB 도서 상태 확인
    await db_session.refresh(book)
    assert book.current_page == 50
    assert book.reading_status == BookReadingStatus.READING


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
        "bookId": book.id,
        "durationMinutes": 40,
        "startPage": 120,
        "endPage": 150,
    }
    resp = await client.post("/api/v1/reading-sessions", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["bookReadingStatus"] == "COMPLETED"
    assert data["updatedCurrentPage"] == 150

    await db_session.refresh(book)
    assert book.reading_status == BookReadingStatus.COMPLETED
    assert book.completed_at is not None


@pytest.mark.asyncio
async def test_create_reading_session_book_not_found(client: AsyncClient):
    """존재하지 않는 도서 ID 지정 시 404 에러 검증"""
    payload = {
        "bookId": 999999,
        "durationMinutes": 20,
    }
    resp = await client.post("/api/v1/reading-sessions", json=payload)
    assert resp.status_code == 404
    assert resp.json()["code"] == "LIBRARY_BOOK_NOT_FOUND"


@pytest.mark.asyncio
async def test_create_reading_session_other_member_book(
    client: AsyncClient, db_session: AsyncSession
):
    """타인의 도서 ID 지정 시 404 (접근 불가) 검증"""
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
        "bookId": book.id,
        "durationMinutes": 25,
    }
    resp = await client.post("/api/v1/reading-sessions", json=payload)
    assert resp.status_code == 404
    assert resp.json()["code"] == "LIBRARY_BOOK_NOT_FOUND"
