import time
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.enums import BookReadingStatus, GenreType
from app.models.library_book import LibraryBook
from app.models.shelf import Shelf
from app.schemas.search import BookSearchItem, ExternalBook
from app.services.google_books import GoogleBooksClient
from tests.conftest import TEST_MEMBER_ID

# =====================================================================
# 1. GoogleBooksClient 단위 테스트
# =====================================================================


def test_google_books_parse_volume_success():
    client = GoogleBooksClient(api_key="test-api-key")
    raw_volume = {
        "volumeInfo": {
            "title": "Clean Architecture",
            "authors": ["Robert C. Martin"],
            "publisher": "Prentice Hall",
            "publishedDate": "2017-09-20",
            "description": "<p>A Craftsman's Guide to <b>Software Structure</b></p>",
            "industryIdentifiers": [
                {"type": "ISBN_10", "identifier": "0134494164"},
                {"type": "ISBN_13", "identifier": "978-0134494166"},
            ],
            "pageCount": 432,
            "imageLinks": {
                "smallThumbnail": "http://books.google.com/books/content?id=test&edge=curl&source=gbs_api",
                "thumbnail": "http://books.google.com/books/content?id=test&edge=curl&source=gbs_api",
            },
            "language": "en",
            "infoLink": "https://play.google.com/store/books/details?id=test",
            "averageRating": 4.5,
        }
    }

    item = client._parse_volume(raw_volume)
    assert item is not None
    assert item.title == "Clean Architecture"
    assert item.author == "Robert C. Martin"
    assert item.isbn == "9780134494166"  # ISBN-13 우선 매핑
    assert item.publisher == "Prentice Hall"
    assert item.published_date == "2017-09-20"
    assert item.total_pages == 432
    assert (
        item.description == "A Craftsman's Guide to Software Structure"
    )  # HTML 태그 정제
    assert item.cover_url is not None
    assert item.cover_url.startswith("https://")  # HTTPS 변환
    assert item.star_score == 4.5
    assert item.data_source == "GOOGLE"
    assert item.genre_source == "GOOGLE"


def test_google_books_missing_isbn_dropped():
    client = GoogleBooksClient(api_key="test-api-key")
    raw_volume_no_id = {
        "volumeInfo": {
            "title": "Book Without ISBN",
            "authors": ["Unknown"],
        }
    }
    assert client._parse_volume(raw_volume_no_id) is None

    raw_volume_invalid_id = {
        "volumeInfo": {
            "title": "Book With Other ID",
            "authors": ["Unknown"],
            "industryIdentifiers": [{"type": "OTHER", "identifier": "12345"}],
        }
    }
    assert client._parse_volume(raw_volume_invalid_id) is None


def test_google_books_isbn_10_fallback():
    client = GoogleBooksClient(api_key="test-api-key")
    raw_volume = {
        "volumeInfo": {
            "title": "Old Book",
            "authors": ["Author"],
            "industryIdentifiers": [{"type": "ISBN_10", "identifier": "0134494164"}],
        }
    }
    item = client._parse_volume(raw_volume)
    assert item is not None
    assert item.isbn == "0134494164"


@pytest.mark.asyncio
async def test_google_books_missing_api_key_safe():
    client = GoogleBooksClient(api_key="")
    items = await client.search_books("Clean Code")
    assert items == []

    book = await client.lookup_by_isbn("9780134494166")
    assert book is None


@pytest.mark.asyncio
async def test_google_books_rate_limit_429():
    client = GoogleBooksClient(api_key="test-key")
    mock_resp = MagicMock()
    mock_resp.status_code = 429

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        items = await client.search_books("Over quota")
        assert items == []


@pytest.mark.asyncio
async def test_google_books_timeout_graceful():
    client = GoogleBooksClient(api_key="test-key")

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = httpx.TimeoutException("Read timed out")
        items = await client.search_books("Timeout query")
        assert items == []


@pytest.mark.asyncio
async def test_google_books_network_error_graceful():
    client = GoogleBooksClient(api_key="test-key")

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = httpx.ConnectError("Connection refused")
        items = await client.search_books("Network error query")
        assert items == []


@pytest.mark.asyncio
async def test_google_books_empty_results():
    client = GoogleBooksClient(api_key="test-key")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {}
    mock_resp.json.return_value = {"totalItems": 0, "items": []}

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        items = await client.search_books("No matching books 12345")
        assert items == []


# =====================================================================
# 2. Cache-Control 지시어 준수 및 TTL 테스트
# =====================================================================


@pytest.mark.asyncio
async def test_google_books_cache_control_no_store():
    """Cache-Control: no-store 응답은 캐싱되지 않고 매번 새로 호출되는지 검증."""
    client = GoogleBooksClient(api_key="test-key")
    client.clear_cache()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"Cache-Control": "no-store"}
    mock_resp.json.return_value = {
        "totalItems": 1,
        "items": [
            {
                "volumeInfo": {
                    "title": "No Store Book",
                    "authors": ["Author"],
                    "industryIdentifiers": [
                        {"type": "ISBN_13", "identifier": "9780134494166"}
                    ],
                }
            }
        ],
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        # 1회차 호출
        items1 = await client.search_books("nostore")
        assert len(items1) == 1
        assert mock_get.call_count == 1
        assert len(client._cache) == 0  # 캐시에 저장되지 않음

        # 2회차 호출 (캐시 미저장으로 인해 HTTP 호출 다시 발생)
        items2 = await client.search_books("nostore")
        assert len(items2) == 1
        assert mock_get.call_count == 2


@pytest.mark.asyncio
async def test_google_books_cache_control_no_cache():
    """Cache-Control: no-cache 응답은 캐싱되지 않는지 검증."""
    client = GoogleBooksClient(api_key="test-key")
    client.clear_cache()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"Cache-Control": "no-cache"}
    mock_resp.json.return_value = {
        "totalItems": 1,
        "items": [
            {
                "volumeInfo": {
                    "title": "No Cache Book",
                    "authors": ["Author"],
                    "industryIdentifiers": [
                        {"type": "ISBN_13", "identifier": "9780134494166"}
                    ],
                }
            }
        ],
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        await client.search_books("nocache")
        assert len(client._cache) == 0
        assert mock_get.call_count == 1

        await client.search_books("nocache")
        assert mock_get.call_count == 2


@pytest.mark.asyncio
async def test_google_books_cache_control_max_age_and_expiry():
    """Cache-Control: max-age=60 지정 시 지정된 TTL을 준수하고 만료 시 재조회되는지 검증."""
    client = GoogleBooksClient(api_key="test-key")
    client.clear_cache()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"Cache-Control": "public, max-age=60"}
    mock_resp.json.return_value = {
        "totalItems": 1,
        "items": [
            {
                "volumeInfo": {
                    "title": "Max Age Book",
                    "authors": ["Author"],
                    "industryIdentifiers": [
                        {"type": "ISBN_13", "identifier": "9780134494166"}
                    ],
                }
            }
        ],
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        # 1. 첫 번째 조회 -> 캐시 저장 (TTL 60초)
        await client.search_books("maxage")
        assert mock_get.call_count == 1
        cache_key = "maxage:10"
        assert cache_key in client._cache
        items, expires_at = client._cache[cache_key]
        assert expires_at <= time.time() + 61.0

        # 2. 유효 시간 내 재조회 -> 캐시 히트 (HTTP 호출 없음)
        await client.search_books("maxage")
        assert mock_get.call_count == 1

        # 3. 캐시 만료 시각을 과거로 조작 -> 캐시 만료로 HTTP 재호출 발생
        client._cache[cache_key] = (items, time.time() - 10)
        await client.search_books("maxage")
        assert mock_get.call_count == 2


@pytest.mark.asyncio
async def test_google_books_default_ttl_when_no_cache_control():
    """Cache-Control 헤더가 없으면 기본 15분 TTL이 적용되는지 검증."""
    client = GoogleBooksClient(api_key="test-key")
    client.clear_cache()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {}
    mock_resp.json.return_value = {
        "totalItems": 1,
        "items": [
            {
                "volumeInfo": {
                    "title": "Default TTL Book",
                    "authors": ["Author"],
                    "industryIdentifiers": [
                        {"type": "ISBN_13", "identifier": "9780134494166"}
                    ],
                }
            }
        ],
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        await client.search_books("default")
        assert mock_get.call_count == 1
        cache_key = "default:10"
        _, expires_at = client._cache[cache_key]
        # 약 900초 (15분) 후 만료 확인
        assert expires_at >= time.time() + 890.0


# =====================================================================
# 3. ISBN 서지 정합성 및 엄격 대조 테스트
# =====================================================================


@pytest.mark.asyncio
async def test_google_books_lookup_by_isbn_exact_and_conversion_match():
    """ISBN-10으로 요청하더라도 볼륨의 유효한 ISBN-13과 변환 일치하면 정상 반환되는지 검증."""
    client = GoogleBooksClient(api_key="test-key")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "totalItems": 1,
        "items": [
            {
                "volumeInfo": {
                    "title": "Clean Architecture",
                    "authors": ["Robert C. Martin"],
                    "industryIdentifiers": [
                        {"type": "ISBN_10", "identifier": "0134494164"},
                        {"type": "ISBN_13", "identifier": "9780134494166"},
                    ],
                }
            }
        ],
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        # ISBN-10 요청 ('0134494164'의 13자리 표준 변환은 '9780134494166')
        ext_book = await client.lookup_by_isbn("0134494164")
        assert ext_book is not None
        assert ext_book.title == "Clean Architecture"
        assert ext_book.isbn == "9780134494166"


@pytest.mark.asyncio
async def test_google_books_lookup_by_isbn_mismatch_rejected():
    """Google Books가 요청 ISBN과 다른 도서를 반환했을 때 불일치로 판정하여 None을 반환하는지 검증."""
    client = GoogleBooksClient(api_key="test-key")
    # 요청한 ISBN은 9780201633610인데, 응답 도서는 9780134494166인 상황
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "totalItems": 1,
        "items": [
            {
                "volumeInfo": {
                    "title": "Mismatched Book",
                    "authors": ["Other Author"],
                    "industryIdentifiers": [
                        {"type": "ISBN_13", "identifier": "9780134494166"}
                    ],
                }
            }
        ],
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        # 요청 ISBN 불일치 시 잘못된 서지정보 주입을 방지하고 None 반환
        ext_book = await client.lookup_by_isbn("9780201633610")
        assert ext_book is None


@pytest.mark.asyncio
async def test_google_books_lookup_by_isbn_invalid_checksum_rejected():
    """체크섬이 잘못된 ISBN으로 요청 시 외부 호출 없이 즉시 None을 반환하는지 검증."""
    client = GoogleBooksClient(api_key="test-key")

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        # 체크섬 오류 (9780201633610의 마지막 자리는 0이어야 하나 9로 입력)
        ext_book = await client.lookup_by_isbn("9780201633619")
        assert ext_book is None
        assert mock_get.call_count == 0  # 외부 호출 차단


@pytest.mark.asyncio
async def test_google_books_lookup_by_isbn_no_identifiers_rejected():
    """응답 볼륨에 ISBN 식별자가 아예 없으면 서지정보로 반환하지 않고 None을 반환하는지 검증."""
    client = GoogleBooksClient(api_key="test-key")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "totalItems": 1,
        "items": [
            {
                "volumeInfo": {
                    "title": "Volume Without Identifiers",
                    "authors": ["Unknown"],
                }
            }
        ],
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        ext_book = await client.lookup_by_isbn("9780201633610")
        assert ext_book is None


# =====================================================================
# 4. 라우터 통합 및 시간 예산(Deadline) 검증
# =====================================================================


@pytest.mark.asyncio
async def test_search_router_fallback_to_google_on_yes24_empty(client: AsyncClient):
    """YES24 결과가 0건일 때 Google Books로 정상 폴백되고 dataSource가 GOOGLE로 설정되는지 검증."""
    google_item = BookSearchItem(
        title="Refactoring: Improving the Design of Existing Code",
        author="Martin Fowler",
        isbn="9780134757599",
        publisher="Addison-Wesley",
        total_pages=448,
        description="Martin Fowler's guide",
        data_source="GOOGLE",
    )

    with (
        patch(
            "app.routers.search.yes24_client.search_books",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_yes24,
        patch(
            "app.routers.search.google_books_client.search_books",
            new_callable=AsyncMock,
            return_value=[google_item],
        ) as mock_google,
    ):
        resp = await client.get("/api/v1/books/search?query=Refactoring")
        assert resp.status_code == 200
        data = resp.json()

        assert mock_yes24.call_count == 1
        assert mock_google.call_count == 1

        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["dataSource"] == "GOOGLE"
        assert (
            data["items"][0]["title"]
            == "Refactoring: Improving the Design of Existing Code"
        )
        assert "books" in data
        assert len(data["books"]) == 1
        assert data["books"][0]["data_source"] == "GOOGLE"


@pytest.mark.asyncio
async def test_search_router_yes24_hit_skips_google(client: AsyncClient):
    """YES24 검색 결과가 있으면 Google Books를 전혀 호출하지 않는지(단축 완료) 검증."""
    yes24_item = BookSearchItem(
        title="클린 코드",
        author="로버트 마틴",
        isbn="9788966260959",
        data_source="YES24",
    )

    with (
        patch(
            "app.routers.search.yes24_client.search_books",
            new_callable=AsyncMock,
            return_value=[yes24_item],
        ) as mock_yes24,
        patch(
            "app.routers.search.google_books_client.search_books",
            new_callable=AsyncMock,
        ) as mock_google,
    ):
        resp = await client.get("/api/v1/books/search?query=클린코드")
        assert resp.status_code == 200
        data = resp.json()

        assert mock_yes24.call_count == 1
        assert mock_google.call_count == 0  # Google Books 호출 생략
        assert data["items"][0]["dataSource"] == "YES24"
        assert data["books"][0]["data_source"] == "YES24"


@pytest.mark.asyncio
async def test_search_router_deadline_insufficient_skips_google(client: AsyncClient):
    """키워드 검색 시 잔여 Deadline이 1.0초 미만으로 부족하면 Google Books 호출을 생략하고 로컬 DB 폴백으로 진행되는지 검증."""
    monotonic_calls = [100.0, 103.8]

    with (
        patch(
            "app.routers.search.yes24_client.search_books",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch("app.routers.search.get_search_time", side_effect=monotonic_calls),
        patch(
            "app.routers.search.google_books_client.search_books",
            new_callable=AsyncMock,
        ) as mock_google,
    ):
        resp = await client.get("/api/v1/books/search?query=SlowQuery")
        assert resp.status_code == 200
        data = resp.json()

        # 잔여 시간이 0.7초로 1.0초 미만이므로 Google Books가 호출되지 않아야 함
        assert mock_google.call_count == 0
        assert data["total"] == 0
        assert data["items"] == []


@pytest.mark.asyncio
async def test_search_router_isbn_fallback_to_google(client: AsyncClient):
    """ISBN 검색 시 기존 공급자(YES24, 국립중앙도서관)가 모두 실패했을 때만 Google Books 단건 조회가 호출되는지 검증."""
    google_book = ExternalBook(
        title="Design Patterns",
        author="Gang of Four",
        isbn="9780201633610",
        genre=GenreType.NONE,
        genre_source="GOOGLE",
    )

    with (
        patch(
            "app.routers.search.yes24_client.lookup_by_isbn",
            new_callable=AsyncMock,
            return_value=None,
        ) as mock_yes24,
        patch(
            "app.routers.search.client.lookup_by_isbn",
            new_callable=AsyncMock,
            return_value=None,
        ) as mock_nl,
        patch(
            "app.routers.search.google_books_client.lookup_by_isbn",
            new_callable=AsyncMock,
            return_value=google_book,
        ) as mock_google_isbn,
    ):
        resp = await client.get("/api/v1/books/search?isbn=9780201633610")
        assert resp.status_code == 200
        data = resp.json()

        assert mock_yes24.call_count == 1
        assert mock_nl.call_count == 1
        assert mock_google_isbn.call_count == 1

        assert data["book"] is not None
        assert data["book"]["title"] == "Design Patterns"
        assert data["book"]["genreSource"] == "GOOGLE"
        assert data["book"]["genre"] == "NONE"


@pytest.mark.asyncio
async def test_search_router_isbn_deadline_insufficient_skips_google(
    client: AsyncClient,
):
    """ISBN 검색 시 국내 공급자 조회 후 잔여 Deadline이 1.0초 미만이면 Google Books 호출을 생략하는지 검증."""
    monotonic_calls = [100.0, 103.8]

    with (
        patch(
            "app.routers.search.yes24_client.lookup_by_isbn",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.routers.search.client.lookup_by_isbn",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch("app.routers.search.get_search_time", side_effect=monotonic_calls),
        patch(
            "app.routers.search.google_books_client.lookup_by_isbn",
            new_callable=AsyncMock,
        ) as mock_google_isbn,
    ):
        resp = await client.get("/api/v1/books/search?isbn=9780201633610")
        assert resp.status_code == 200
        data = resp.json()

        # 잔여 시간이 0.7초로 1.0초 미만이므로 Google Books ISBN 조회가 생략되어야 함
        assert mock_google_isbn.call_count == 0
        assert data["total"] == 0
        assert data["book"] is None


@pytest.mark.asyncio
async def test_search_router_isbn_google_not_called_if_nl_succeeds(
    client: AsyncClient,
):
    """ISBN 검색 시 국립도서관 결과가 있으면 Google Books ISBN 조회가 전혀 호출되지 않는지 검증."""
    nl_book = ExternalBook(
        title="한국 도서",
        author="한국 저자",
        isbn="9791162242742",
        genre=GenreType.TECHNOLOGY,
        genre_source="KDC",
    )

    with (
        patch(
            "app.routers.search.yes24_client.lookup_by_isbn",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.routers.search.client.lookup_by_isbn",
            new_callable=AsyncMock,
            return_value=nl_book,
        ),
        patch(
            "app.routers.search.google_books_client.lookup_by_isbn",
            new_callable=AsyncMock,
        ) as mock_google_isbn,
    ):
        resp = await client.get("/api/v1/books/search?isbn=9791162242742")
        assert resp.status_code == 200
        data = resp.json()

        assert mock_google_isbn.call_count == 0  # Google Books 호출 생략
        assert data["book"] is not None
        assert data["book"]["title"] == "한국 도서"
        assert data["book"]["genreSource"] == "KDC"


@pytest.mark.asyncio
async def test_search_router_isbn_registered_book_skips_all_external_calls(
    client: AsyncClient, db_session: AsyncSession
):
    """서재에 이미 등록된 도서는 외부 API(YES24, 국립도서관, Google Books)를 일절 호출하지 않고 즉시 반환하는지 검증."""
    shelf = Shelf(member_id=TEST_MEMBER_ID, name="기본 책장", is_default=True)
    db_session.add(shelf)
    await db_session.flush()

    book = LibraryBook(
        member_id=TEST_MEMBER_ID,
        shelf_id=shelf.id,
        shelf_rank="Z",
        title="Existing Library Book",
        author="Existing Author",
        isbn="9780201633610",
        genre=GenreType.TECHNOLOGY,
        reading_status=BookReadingStatus.READING,
    )
    db_session.add(book)
    await db_session.commit()

    token = create_access_token(TEST_MEMBER_ID, "test@example.com", "테스터")
    auth_headers = {"Authorization": f"Bearer {token}"}

    with (
        patch(
            "app.routers.search.yes24_client.lookup_by_isbn",
            new_callable=AsyncMock,
        ) as mock_yes24,
        patch(
            "app.routers.search.client.lookup_by_isbn",
            new_callable=AsyncMock,
        ) as mock_nl,
        patch(
            "app.routers.search.google_books_client.lookup_by_isbn",
            new_callable=AsyncMock,
        ) as mock_google,
    ):
        resp = await client.get(
            "/api/v1/books/search?isbn=9780201633610", headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()

        assert mock_yes24.call_count == 0
        assert mock_nl.call_count == 0
        assert mock_google.call_count == 0
        assert data["alreadyRegistered"] is True
        assert data["libraryBook"]["title"] == "Existing Library Book"


@pytest.mark.asyncio
async def test_search_router_is_registered_mapping_on_google_results(
    client: AsyncClient, db_session: AsyncSession
):
    """회원 서재에 등록된 도서가 Google Books 검색 결과에 포함된 경우 isRegistered=True 매핑 검증."""
    token = create_access_token(TEST_MEMBER_ID, "test@example.com", "테스터")
    auth_headers = {"Authorization": f"Bearer {token}"}

    shelf = Shelf(member_id=TEST_MEMBER_ID, name="기본 책장", is_default=True)
    db_session.add(shelf)
    await db_session.flush()

    book = LibraryBook(
        member_id=TEST_MEMBER_ID,
        shelf_id=shelf.id,
        shelf_rank="A",
        title="Registered Global Book",
        author="Global Author",
        isbn="9780134494166",
        genre=GenreType.TECHNOLOGY,
        reading_status=BookReadingStatus.READING,
    )
    db_session.add(book)
    await db_session.commit()

    google_item1 = BookSearchItem(
        title="Registered Global Book",
        author="Global Author",
        isbn="9780134494166",
        data_source="GOOGLE",
    )
    google_item2 = BookSearchItem(
        title="Unregistered Global Book",
        author="Another Author",
        isbn="9780134494999",
        data_source="GOOGLE",
    )

    with (
        patch(
            "app.routers.search.yes24_client.search_books",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "app.routers.search.google_books_client.search_books",
            new_callable=AsyncMock,
            return_value=[google_item1, google_item2],
        ),
    ):
        resp = await client.get(
            "/api/v1/books/search?query=Global", headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()

        assert data["total"] == 2
        assert data["alreadyRegistered"] is True
        assert data["items"][0]["isRegistered"] is True
        assert data["items"][1]["isRegistered"] is False
