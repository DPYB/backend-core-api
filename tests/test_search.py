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
    assert data["libraryBook"]["genreName"] == "컴퓨터 프로그래밍"  # Subject 1순위 노출
    assert data["libraryBook"]["displayGenre"] == "컴퓨터 프로그래밍"
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
        assert data["book"]["genreName"] == "소프트웨어 리팩터링"  # Subject 1순위 노출
        assert data["book"]["displayGenre"] == "소프트웨어 리팩터링"


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
        assert book.cover_url is not None
        assert "kyobobook.co.kr" in book.cover_url
        assert book.subject == "SF/과학소설"
        assert book.display_genre == "SF/과학소설"
        assert book.genre == GenreType.LITERATURE
        assert book.genre_name == "SF/과학소설"  # Subject 1순위 노출


@pytest.mark.asyncio
async def test_search_by_keyword_query(client: AsyncClient, db_session: AsyncSession):
    shelf = Shelf(member_id=TEST_MEMBER_ID, name="기본 책장", is_default=True)
    db_session.add(shelf)
    await db_session.flush()

    book = LibraryBook(
        member_id=TEST_MEMBER_ID,
        shelf_id=shelf.id,
        shelf_rank="V",
        title="인공지능 철학 콘서트",
        author="이수영",
        isbn="9788900000001",
        genre=GenreType.PHILOSOPHY,
        subject="인공지능 윤리",
        reading_status=BookReadingStatus.READING,
        total_pages=300,
        current_page=50,
    )
    db_session.add(book)
    await db_session.commit()

    from app.core.security import create_access_token

    token = create_access_token(TEST_MEMBER_ID, "test@example.com", "테스터")

    # YES24 결과가 없을 때의 로컬 회원 서재 fallback 검증 (외부 네트워크 차단 모킹)
    with patch(
        "app.routers.search.yes24_client.search_books", new_callable=AsyncMock
    ) as mock_yes24:
        mock_yes24.return_value = []
        resp = await client.get(
            "/api/v1/books/search?query=인공지능",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["alreadyRegistered"] is True
        assert data["libraryBook"]["title"] == "인공지능 철학 콘서트"
        # AI 에이전트 호환용 books 필드 검증
        assert "books" in data
        assert len(data["books"]) == 1
        assert data["books"][0]["title"] == "인공지능 철학 콘서트"
        assert data["books"][0]["book_id"] == str(book.id)


@pytest.mark.asyncio
async def test_get_book_by_id_alias(client: AsyncClient, db_session: AsyncSession):
    shelf = Shelf(member_id=TEST_MEMBER_ID, name="기본 책장", is_default=True)
    db_session.add(shelf)
    await db_session.flush()

    book = LibraryBook(
        member_id=TEST_MEMBER_ID,
        shelf_id=shelf.id,
        shelf_rank="V",
        title="데미안",
        author="헤르만 헤세",
        isbn="9788937460449",
        genre=GenreType.LITERATURE,
        subject="성장소설",
        reading_status=BookReadingStatus.COMPLETED,
        total_pages=240,
        current_page=240,
    )
    db_session.add(book)
    await db_session.commit()

    # /api/v1/books/{book_id} 별칭 호출 검증
    resp = await client.get(f"/api/v1/books/{book.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["bookId"] == book.id
    assert data["title"] == "데미안"
    assert data["readingStatus"] == "COMPLETED"
    assert data["displayGenre"] == "성장소설"


@pytest.mark.asyncio
async def test_national_library_martian_sf_override():
    """국립중앙도서관에서 KDC 843(영미소설)로 내려오는 마션이 제목 SF 키워드로 인해 SF/과학소설로 보정되는지 검증"""
    from unittest.mock import MagicMock

    from app.services.national_library import NationalLibraryClient

    client = NationalLibraryClient(cert_key="test-key")
    client.clear_cache()

    mock_resp_data = {
        "TOTAL_COUNT": "1",
        "docs": [
            {
                "TITLE": "마션 (어느 외톨이 우주인의 화성 생존기)",
                "AUTHOR": "앤디 위어",
                "EA_ISBN": "9788925556277",
                "KDC": "843.6",
                "PAGE": "599p",
            }
        ],
    }
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_resp_data

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        book = await client.lookup_by_isbn("9788925556277")
        assert book is not None
        assert book.title == "마션 (어느 외톨이 우주인의 화성 생존기)"
        assert book.genre == GenreType.LITERATURE
        assert book.subject == "SF/과학소설"
        assert book.display_genre == "SF/과학소설"


@pytest.mark.asyncio
async def test_search_keyword_yes24_success(client: AsyncClient):
    """YES24 키워드 검색 성공 시 query 에코 및 items 목록 정상 반환 검증"""
    from app.schemas.search import BookSearchItem

    mock_items = [
        BookSearchItem(
            title="불편한 편의점",
            author="김호연 저",
            isbn="9791161571188",
            publisher="나무옆의자",
            published_date="2021-04-20",
            cover_url="https://image.yes24.com/goods/99308021/L",
            total_pages=268,
            description="청파동 골목 작은 편의점 이야기",
            genre_source="KDC",
            is_registered=False,
            star_score=9.5,
        ),
        BookSearchItem(
            title="불편한 편의점 2",
            author="김호연 저",
            isbn="9791161571379",
            publisher="나무옆의자",
            published_date="2022-08-10",
            cover_url="https://image.yes24.com/goods/111088149/L",
            total_pages=320,
            description="편의점 두 번째 이야기",
            genre_source="KDC",
            is_registered=False,
            star_score=9.6,
        ),
    ]

    with patch(
        "app.routers.search.yes24_client.search_books", new_callable=AsyncMock
    ) as mock_search:
        mock_search.return_value = mock_items
        resp = await client.get("/api/v1/books/search?query=불편한")
        assert resp.status_code == 200
        data = resp.json()

        assert data["query"] == "불편한"  # 오타 자동교정 대응 query 에코 검증
        assert data["total"] == 2
        assert len(data["items"]) == 2
        assert data["items"][0]["title"] == "불편한 편의점"
        assert data["items"][0]["totalPages"] == 268
        assert data["items"][0]["description"] == "청파동 골목 작은 편의점 이야기"
        assert data["items"][0]["starScore"] == 9.5
        assert data["items"][0]["isRegistered"] is False
        assert "books" in data
        assert len(data["books"]) == 2


@pytest.mark.asyncio
async def test_search_keyword_yes24_is_registered_mapping(
    client: AsyncClient, db_session: AsyncSession
):
    """회원 서재에 1편이 이미 등록되어 있을 때 isRegistered=True 매핑 검증"""
    from app.schemas.search import BookSearchItem

    shelf = Shelf(member_id=TEST_MEMBER_ID, name="기본 책장", is_default=True)
    db_session.add(shelf)
    await db_session.flush()

    book = LibraryBook(
        member_id=TEST_MEMBER_ID,
        shelf_id=shelf.id,
        shelf_rank="V",
        title="불편한 편의점",
        author="김호연",
        isbn="9791161571188",
        genre=GenreType.LITERATURE,
        reading_status=BookReadingStatus.COMPLETED,
        total_pages=268,
        current_page=268,
    )
    db_session.add(book)
    await db_session.commit()

    mock_items = [
        BookSearchItem(
            title="불편한 편의점",
            author="김호연",
            isbn="9791161571188",
            publisher="나무옆의자",
            cover_url="https://image.yes24.com/goods/99308021/L",
            total_pages=268,
            is_registered=False,
        ),
        BookSearchItem(
            title="불편한 편의점 2",
            author="김호연",
            isbn="9791161571379",
            publisher="나무옆의자",
            cover_url="https://image.yes24.com/goods/111088149/L",
            total_pages=320,
            is_registered=False,
        ),
    ]

    with patch(
        "app.routers.search.yes24_client.search_books", new_callable=AsyncMock
    ) as mock_search:
        mock_search.return_value = mock_items
        # 인증 헤더와 함께 호출
        from app.core.security import create_access_token

        token = create_access_token(TEST_MEMBER_ID, "test@example.com", "테스터")
        resp = await client.get(
            "/api/v1/books/search?query=불편한",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()

        assert data["query"] == "불편한"
        assert data["alreadyRegistered"] is True
        assert data["items"][0]["isbn"] == "9791161571188"
        assert data["items"][0]["isRegistered"] is True  # 1편 등록됨
        assert data["items"][1]["isbn"] == "9791161571379"
        assert data["items"][1]["isRegistered"] is False  # 2편 미등록


@pytest.mark.asyncio
async def test_yes24_client_dedup_and_filter():
    """Yes24Client 단위 테스트: ISBN 누락 세트 상품 필터링, Dedup, TTL 캐시 검증"""
    from unittest.mock import MagicMock

    from app.services.yes24 import Yes24Client

    client = Yes24Client(api_key="test-key")
    client.clear_cache()

    mock_json_data = {
        "success": True,
        "message": "성공",
        "data": {
            "items": [
                {
                    "title": "클린 코드",
                    "author": "로버트 마틴",
                    "isbn13": "9788966265527",
                    "publisher": "인사이트",
                    "pages": 584,
                    "cover": "https://image.yes24.com/goods/196209093/L",
                    "contentDetail": {
                        "bookIntroduction": "애자일 소프트웨어 장인 정신"
                    },
                    "starScore": 9.8,
                },
                {
                    # 동일 ISBN 중복 상품 (사은품 한정판 등)
                    "title": "클린 코드 (한정판 에디션)",
                    "author": "로버트 마틴",
                    "isbn13": "9788966265527",
                    "publisher": "인사이트",
                    "pages": 584,
                },
                {
                    # ISBN 누락 묶음 세트 상품
                    "title": "클린 코드 + 클린 아키텍처 세트",
                    "author": "로버트 마틴",
                    "isbn13": "",
                    "isbn10": "",
                    "pages": 900,
                },
            ]
        },
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_json_data

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp

        # 1차 호출
        items = await client.search_books("클린코드")
        assert len(items) == 1  # 중복 제거 및 세트상품 제외되어 1건만 남아야 함!
        assert items[0].title == "클린 코드"
        assert items[0].isbn == "9788966265527"
        assert items[0].total_pages == 584
        assert items[0].description == "애자일 소프트웨어 장인 정신"
        assert items[0].star_score == 9.8
        assert mock_get.call_count == 1

        # 2차 호출 (동일 검색어 캐시 테스트)
        items_cached = await client.search_books("클린코드")
        assert len(items_cached) == 1
        assert mock_get.call_count == 1  # 캐시 히트로 추가 호출 0회!
