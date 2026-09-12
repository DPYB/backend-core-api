from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import BookReadingStatus, GenreType
from app.models.library_book import LibraryBook
from app.models.shelf import Shelf
from app.schemas.search import ExternalBook
from tests.conftest import TEST_MEMBER_ID


@pytest.mark.asyncio
async def test_search_invalid_isbn(client: AsyncClient):
    # 9자리 숫자 (잘못됨)
    resp = await client.get("/api/v1/books/search?isbn=123456789")
    assert resp.status_code == 400
    data = resp.json()
    assert data["code"] == "INVALID_SEARCH_PARAMETER"


@pytest.mark.asyncio
async def test_search_already_registered_book(
    client: AsyncClient, db_session: AsyncSession
):
    # 1. 서재에 도서 등록
    shelf = Shelf(member_id=TEST_MEMBER_ID, name="기본 책장", is_default=True)
    db_session.add(shelf)
    await db_session.flush()

    book = LibraryBook(
        member_id=TEST_MEMBER_ID,
        shelf_id=shelf.id,
        shelf_rank="V",
        title="클린 코드",
        author="로버트 C. 마틴",
        isbn="9788966260959",
        genre=GenreType.TECHNOLOGY,
        kdc="005.133",
        subject="컴퓨터 프로그래밍",
        publisher="인사이트",
        reading_status=BookReadingStatus.READING,
        total_pages=584,
        current_page=120,
    )
    db_session.add(book)
    await db_session.commit()

    # 2. 검색 요청
    resp = await client.get("/api/v1/books/search?isbn=9788966260959")
    assert resp.status_code == 200
    data = resp.json()
    assert data["alreadyRegistered"] is True
    assert data["book"] is None
    assert data["libraryBook"] is not None
    assert data["libraryBook"]["title"] == "클린 코드"
    assert data["libraryBook"]["genre"] == "TECHNOLOGY"
    assert data["libraryBook"]["genreName"] == "기술과학"
    assert data["libraryBook"]["progress"] == 20.5


@pytest.mark.asyncio
async def test_search_unregistered_book_found(client: AsyncClient):
    mock_book = ExternalBook(
        title="리팩터링 2판",
        author="마틴 파울러",
        isbn="9791162242742",
        genre=GenreType.TECHNOLOGY,
        kdc="005.133",
        subject="소프트웨어 리팩터링",
        publisher="한빛미디어",
        total_pages=500,
    )

    with patch(
        "app.routers.search.client.lookup_by_isbn", new_callable=AsyncMock
    ) as mock_lookup:
        mock_lookup.return_value = mock_book
        resp = await client.get("/api/v1/books/search?isbn=9791162242742")
        assert resp.status_code == 200
        data = resp.json()
        assert data["alreadyRegistered"] is False
        assert data["libraryBook"] is None
        assert data["book"] is not None
        assert data["book"]["title"] == "리팩터링 2판"
        assert data["book"]["genreName"] == "기술과학"


@pytest.mark.asyncio
async def test_search_unregistered_book_not_found(client: AsyncClient):
    with patch(
        "app.routers.search.client.lookup_by_isbn", new_callable=AsyncMock
    ) as mock_lookup:
        mock_lookup.return_value = None
        resp = await client.get("/api/v1/books/search?isbn=9999999999999")
        assert resp.status_code == 200
        data = resp.json()
        assert data["alreadyRegistered"] is False
        assert data["libraryBook"] is None
        assert data["book"] is None
