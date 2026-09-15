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


@pytest.mark.asyncio
async def test_national_library_cache_hit():
    from unittest.mock import MagicMock

    from app.services.national_library import NationalLibraryClient

    client = NationalLibraryClient(cert_key="test-key")
    client.clear_cache()

    mock_resp_data = {
        "TOTAL_COUNT": "1",
        "docs": [
            {
                "TITLE": "캐시 테스트 도서",
                "AUTHOR": "저자",
                "EA_ISBN": "9791100000001",
                "KDC": "810",
                "PAGE": "300",
            }
        ],
    }

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_resp_data

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        # 첫 번째 조회 (캐시 미스 -> HTTP 호출)
        book1 = await client.lookup_by_isbn("9791100000001")
        assert book1 is not None
        assert book1.title == "캐시 테스트 도서"
        assert mock_get.call_count == 1

        # 두 번째 조회 (캐시 히트 -> HTTP 호출 없음)
        book2 = await client.lookup_by_isbn("9791100000001")
        assert book2 is not None
        assert book2.title == "캐시 테스트 도서"
        assert mock_get.call_count == 1  # 여전히 1회


@pytest.mark.asyncio
async def test_national_library_cache_expiration():
    import time
    from unittest.mock import MagicMock

    from app.services.national_library import NationalLibraryClient

    client = NationalLibraryClient(cert_key="test-key")
    client.clear_cache()

    mock_resp_data = {
        "TOTAL_COUNT": "1",
        "docs": [
            {
                "TITLE": "만료 테스트 도서",
                "AUTHOR": "저자",
                "EA_ISBN": "9791100000002",
                "KDC": "810",
            }
        ],
    }
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_resp_data

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        # 1. 첫 번째 조회
        await client.lookup_by_isbn("9791100000002")
        assert mock_get.call_count == 1

        # 2. 캐시 만료 시각을 과거로 조작
        client._cache["9791100000002"] = (
            client._cache["9791100000002"][0],
            time.time() - 10,
        )

        # 3. 재조회 시 만료로 인해 새로운 HTTP 호출 발생
        await client.lookup_by_isbn("9791100000002")
        assert mock_get.call_count == 2


@pytest.mark.asyncio
async def test_national_library_timeout_graceful_fallback(client: AsyncClient):
    import httpx

    from app.services.national_library import NationalLibraryClient

    nl_client = NationalLibraryClient(cert_key="test-key")
    nl_client.clear_cache()

    with patch(
        "httpx.AsyncClient.get",
        side_effect=httpx.ReadTimeout("외부 API 응답 시간 초과"),
    ):
        # 1. 클라이언트 레벨 graceful fallback (예외 없이 None 반환)
        res = await nl_client.lookup_by_isbn("9791100000003")
        assert res is None

    # 2. 검색 API 엔드포인트 레벨 통합 검증: 국립중앙도서관 타임아웃 발생 시에도 500 대신 200 OK와 book: None 반환
    with patch(
        "app.routers.search.client.lookup_by_isbn",
        side_effect=httpx.ReadTimeout("외부 도서관 타임아웃"),
    ):
        api_resp = await client.get("/api/v1/books/search?isbn=9791100000003")
        assert api_resp.status_code == 200
        data = api_resp.json()
        assert data["alreadyRegistered"] is False
        assert data["book"] is None


@pytest.mark.asyncio
async def test_national_library_kyobo_cdn_fallback():
    from unittest.mock import MagicMock

    from app.services.national_library import (
        NationalLibraryClient,
        get_verified_cover_url,
    )

    # 1. get_verified_cover_url 단위 테스트
    official = "https://www.nl.go.kr/image/sample.jpg"
    assert get_verified_cover_url(official, "9791190090018") == official
    assert (
        get_verified_cover_url("", "9791190090018")
        == "https://contents.kyobobook.co.kr/sih/fit-in/458x0/pdt/9791190090018.jpg"
    )
    assert (
        get_verified_cover_url(None, "979-11-90090-01-8")
        == "https://contents.kyobobook.co.kr/sih/fit-in/458x0/pdt/9791190090018.jpg"
    )
    assert get_verified_cover_url(None, None) is None

    # 2. lookup_by_isbn 통합 시 표지 누락 도서에 교보 CDN 자동 주입 테스트
    client = NationalLibraryClient(cert_key="test-key")
    client.clear_cache()

    mock_resp_data = {
        "TOTAL_COUNT": "1",
        "docs": [
            {
                "TITLE": "우리가 빛의 속도로 갈 수 없다면",
                "AUTHOR": "김초엽",
                "EA_ISBN": "9791190090018",
                "KDC": "813.7",
                "TITLE_URL": "",  # 도서관 표지 누락 상황
            }
        ],
    }

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_resp_data

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        book = await client.lookup_by_isbn("9791190090018")
        assert book is not None
        assert "kyobobook.co.kr" in book.cover_url
        assert book.subject == "SF/과학소설"
        assert book.display_genre == "SF/과학소설"
        assert book.genre == GenreType.LITERATURE
        assert book.genre_name == "문학"
