import uuid

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import GenreType
from app.schemas.search import ExternalBook
from app.services.ai_agent import AiAgentClient, ClassifyGenreResult
from app.services.national_library import NationalLibraryClient
from app.services.yes24 import Yes24Client


@pytest.mark.asyncio
async def test_create_book_with_ai_genre_classification(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    """신규 도서 등록 시 AI Agent 장르 분류 호출 및 LLM 출처, confidence 영속화 검증"""
    call_count = 0

    async def mock_classify_genre(
        self, title, author="", description=None, kdc=None, isbn=None
    ):
        nonlocal call_count
        call_count += 1
        return ClassifyGenreResult(
            genre=GenreType.PHILOSOPHY,
            subject="미술치료/심리",
            confidence=0.92,
            source="LLM",
            reason="명화 심리치료 도서",
        )

    monkeypatch.setattr(AiAgentClient, "classify_genre", mock_classify_genre)

    payload = {
        "title": "그림의 힘",
        "author": "김선현",
        "isbn": "9788950958749",
        "description": "지친 몸과 마음을 치유하는 그림의 힘",
        "kdc": "513.8",
    }
    resp = await client.post("/api/v1/library/books", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["genre"] == "PHILOSOPHY"
    assert data["subject"] == "미술치료/심리"
    assert data["genreSource"] == "LLM"
    assert data["genreConfidence"] == 0.92
    assert call_count == 1


@pytest.mark.asyncio
async def test_create_book_genre_cache_reuse_for_same_isbn(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    """동일 ISBN 도서가 이미 등록되어 있을 때 두 번째 등록 시 AI Agent 호출 없이 캐시 재활용 검증"""
    ai_call_count = 0

    async def mock_classify_genre(
        self, title, author="", description=None, kdc=None, isbn=None
    ):
        nonlocal ai_call_count
        ai_call_count += 1
        return ClassifyGenreResult(
            genre=GenreType.LITERATURE,
            subject="한국현대소설",
            confidence=0.88,
            source="LLM",
        )

    monkeypatch.setattr(AiAgentClient, "classify_genre", mock_classify_genre)

    test_isbn = "9788937462566"  # 달과 6펜스 유효 ISBN-13

    # 1. 첫 번째 도서 등록 -> AI Agent 호출 (ai_call_count = 1)
    payload_1 = {
        "title": "달과 6펜스",
        "author": "서머싯 몸",
        "isbn": test_isbn,
        "description": "예술적 열망과 광기의 삶",
    }
    resp_1 = await client.post("/api/v1/library/books", json=payload_1)
    assert resp_1.status_code == 201
    assert resp_1.json()["genreSource"] == "LLM"
    assert ai_call_count == 1

    # 2. 다른 회원이 동일 ISBN 등록 -> AI Agent 호출 생략(ai_call_count 그대로 1) 및 캐시 재사용
    other_member_id = uuid.uuid4()
    # auth override로 다른 회원 세션 흉내내기
    from app.core.security import get_current_member_id
    from app.main import app

    app.dependency_overrides[get_current_member_id] = lambda: other_member_id

    try:
        payload_2 = {
            "title": "달과 6펜스 (동일판본)",
            "author": "서머싯 몸",
            "isbn": test_isbn,
        }
        resp_2 = await client.post("/api/v1/library/books", json=payload_2)
        assert resp_2.status_code == 201
        data_2 = resp_2.json()
        assert data_2["genre"] == "LITERATURE"
        assert data_2["subject"] == "한국현대소설"
        assert data_2["genreSource"] == "LLM"
        assert data_2["genreConfidence"] == 0.88
        # 핵심 검증: AI Agent 호출이 증가하지 않고 DB 캐시를 재활용함!
        assert ai_call_count == 1
    finally:
        app.dependency_overrides.pop(get_current_member_id, None)


@pytest.mark.asyncio
async def test_create_book_user_override_protection(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    """사용자가 genre_source='USER'로 수동 지정한 경우 AI Agent가 호출되지 않고 사용자 값 보존 검증"""
    ai_call_count = 0

    async def mock_classify_genre(
        self, title, author="", description=None, kdc=None, isbn=None
    ):
        nonlocal ai_call_count
        ai_call_count += 1
        return ClassifyGenreResult(
            genre=GenreType.NONE, subject=None, confidence=None, source="LLM"
        )

    monkeypatch.setattr(AiAgentClient, "classify_genre", mock_classify_genre)

    payload = {
        "title": "사용자 커스텀 분류 도서",
        "author": "작가",
        "isbn": "9788901234564",
        "genre": "ARTS",
        "subject": "나만의 맞춤 예술",
        "genre_source": "USER",
    }
    resp = await client.post("/api/v1/library/books", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["genre"] == "ARTS"
    assert data["subject"] == "나만의 맞춤 예술"
    assert data["genreSource"] == "USER"
    assert data["genreConfidence"] is None
    # AI 호출 0회 검증!
    assert ai_call_count == 0


@pytest.mark.asyncio
async def test_update_book_genre_confidence_and_user_protection(client: AsyncClient):
    """도서 수정 시 genre_confidence 반영 및 사용자 수정 시 보호 검증 (PATCH)"""
    # 1. 도서 등록
    create_payload = {
        "title": "수정 대상 도서",
        "author": "홍길동",
        "genre": "LITERATURE",
        "subject": "고전소설",
        "genre_source": "LLM",
        "genre_confidence": 0.85,
    }
    create_resp = await client.post("/api/v1/library/books", json=create_payload)
    assert create_resp.status_code == 201
    book_id = create_resp.json()["bookId"]

    # 2. 도서 수정 (사용자가 직접 장르 변경 -> USER 출처 지정)
    update_payload = {
        "title": "수정 대상 도서",
        "author": "홍길동",
        "genre": "HISTORY",
        "subject": "역사 소설",
        "genre_source": "USER",
        "reading_status": "READING",
    }
    update_resp = await client.patch(
        f"/api/v1/library/books/{book_id}", json=update_payload
    )
    assert update_resp.status_code == 200
    updated_data = update_resp.json()
    assert updated_data["genre"] == "HISTORY"
    assert updated_data["subject"] == "역사 소설"
    assert updated_data["genreSource"] == "USER"


@pytest.mark.asyncio
async def test_yes24_lookup_by_isbn(monkeypatch: pytest.MonkeyPatch):
    """YES24 단건 조회 lookup_by_isbn 정상 파싱, 캐싱 및 link 추출 검증"""
    client = Yes24Client(api_key="mock-key")

    async def mock_get(self, url, **kwargs):
        req = httpx.Request("GET", url)
        return httpx.Response(
            200,
            json={
                "success": True,
                "data": {
                    "items": [
                        {
                            "title": "테스트 도서",
                            "author": "저자",
                            "isbn13": "9788950958749",
                            "publisher": "출판사",
                            "pages": 320,
                            "goodsNo": "12345678",
                            "contentDetail": {
                                "bookIntroduction": "책 소개 내용입니다.",
                            },
                        }
                    ]
                },
            },
            request=req,
        )

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    item = await client.lookup_by_isbn("9788950958749")
    assert item is not None
    assert item.title == "테스트 도서"
    assert item.isbn == "9788950958749"
    assert item.total_pages == 320
    assert item.description == "책 소개 내용입니다."
    assert item.link == "https://www.yes24.com/Product/Goods/12345678"

    # 캐시 적재 확인 (동일 키로 호출 시 네트워크 요청 없이 반환)
    cached_item = await client.lookup_by_isbn("9788950958749")
    assert cached_item == item


@pytest.mark.asyncio
async def test_search_by_isbn_parallel_fusion(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    """ISBN 검색 시 YES24(소개글/쪽수/링크)와 국립중앙도서관(KDC/장르/주제어) 병렬 융합 검증"""

    # 1. YES24 단건 조회 모킹
    async def mock_yes24_lookup(self, isbn: str):
        from app.schemas.search import BookSearchItem

        return BookSearchItem(
            title="병렬 융합 도서",
            author="공동 저자",
            isbn=isbn,
            publisher="YES24 출판사",
            total_pages=450,
            description="상세한 YES24 책 소개 줄거리입니다.",
            cover_url="https://image.yes24.com/cover.jpg",
            link="https://www.yes24.com/Product/Goods/99999",
        )

    monkeypatch.setattr(Yes24Client, "lookup_by_isbn", mock_yes24_lookup)

    # 2. 국립중앙도서관 단건 조회 모킹
    async def mock_nl_lookup(self, isbn: str):
        return ExternalBook(
            title="병렬 융합 도서 (도서관명)",
            author="공동 저자",
            isbn=isbn,
            genre=GenreType.TECHNOLOGY,
            kdc="004.7",
            subject="IT/인공지능",
            publisher="국립도서관 등록 출판사",
        )

    monkeypatch.setattr(NationalLibraryClient, "lookup_by_isbn", mock_nl_lookup)

    # 3. 검색 API 호출
    target_isbn = "9788950958749"
    resp = await client.get(f"/api/v1/books/search?isbn={target_isbn}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["book"] is not None
    fused_book = data["book"]
    # YES24 우선 필드 검증
    assert fused_book["description"] == "상세한 YES24 책 소개 줄거리입니다."
    assert fused_book["totalPages"] == 450
    assert fused_book["link"] == "https://www.yes24.com/Product/Goods/99999"
    # 국립도서관 우선 필드 검증
    assert fused_book["kdc"] == "004.7"
    assert fused_book["genre"] == "TECHNOLOGY"
    assert fused_book["subject"] == "IT/인공지능"


@pytest.mark.asyncio
async def test_create_book_genre_cache_reuse_with_existing_request_genre(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    """요청에 KDC 장르가 이미 있더라도 캐시된 LLM 장르를 만났을 때 올바르게 승격 및 출처/신뢰도 일관성 검증"""
    ai_call_count = 0

    async def mock_classify_genre(
        self, title, author="", description=None, kdc=None, isbn=None
    ):
        nonlocal ai_call_count
        ai_call_count += 1
        return ClassifyGenreResult(
            genre=GenreType.PHILOSOPHY,
            subject="미술치료/심리",
            confidence=0.96,
            source="LLM",
        )

    monkeypatch.setattr(AiAgentClient, "classify_genre", mock_classify_genre)

    target_isbn = "9788950958749"

    # 1. 첫 번째 회원 등록: LLM 장르(PHILOSOPHY)로 캐시 생성
    resp_1 = await client.post(
        "/api/v1/library/books",
        json={
            "title": "그림의 힘",
            "author": "김선현",
            "isbn": target_isbn,
            "description": "명화 심리치료",
        },
    )
    assert resp_1.status_code == 201
    assert resp_1.json()["genre"] == "PHILOSOPHY"
    assert resp_1.json()["genreSource"] == "LLM"
    assert ai_call_count == 1

    # 2. 두 번째 회원 등록: 요청에 이미 KDC 장르(TECHNOLOGY)가 들어있는 상황 모사
    other_member_id = uuid.uuid4()
    from app.core.security import get_current_member_id
    from app.main import app

    app.dependency_overrides[get_current_member_id] = lambda: other_member_id
    try:
        resp_2 = await client.post(
            "/api/v1/library/books",
            json={
                "title": "그림의 힘 (회원2)",
                "author": "김선현",
                "isbn": target_isbn,
                "genre": "TECHNOLOGY",
                "subject": "의학/건강",
                "genre_source": "KDC",
            },
        )
        assert resp_2.status_code == 201
        data_2 = resp_2.json()
        # 핵심 검증: KDC 요청 장르가 아닌 캐시된 LLM 장르로 승격되며 출처/신뢰도 일관성 유지
        assert data_2["genre"] == "PHILOSOPHY"
        assert data_2["subject"] == "미술치료/심리"
        assert data_2["genreSource"] == "LLM"
        assert data_2["genreConfidence"] == 0.96
        # AI 호출수 그대로 1 (캐시 적재 재사용)
        assert ai_call_count == 1
    finally:
        app.dependency_overrides.pop(get_current_member_id, None)


@pytest.mark.asyncio
async def test_yes24_lookup_by_isbn_mismatched_isbn_not_returned_and_not_cached(
    monkeypatch: pytest.MonkeyPatch,
):
    """YES24 단건 조회 시 일치하는 ISBN이 없으면 첫 번째 항목을 채택하지 않고 None 반환 및 미캐싱 검증"""
    client = Yes24Client(api_key="mock-key")

    async def mock_get(self, url, **kwargs):
        req = httpx.Request("GET", url)
        return httpx.Response(
            200,
            json={
                "success": True,
                "data": {
                    "items": [
                        {
                            "title": "전혀 무관한 도서",
                            "author": "엉뚱한 작가",
                            "isbn13": "9788901234564",  # 요청 ISBN과 전혀 다름
                            "goodsNo": "99999",
                        }
                    ]
                },
            },
            request=req,
        )

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    requested_isbn = "9788950958749"
    item = await client.lookup_by_isbn(requested_isbn)
    # 일치하지 않으므로 None 반환
    assert item is None
    # 캐시에도 저장되지 않아야 함
    assert f"isbn:{requested_isbn}" not in client._cache


@pytest.mark.asyncio
async def test_search_by_isbn_provider_failures(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    """병렬 서지 검색에서 YES24 실패/국립도서관 실패/양쪽 실패 상황별 격리 검증"""
    target_isbn = "9788950958749"

    # 케이스 1: YES24 실패(None) + 국립도서관 성공
    async def mock_yes24_fail(self, isbn: str):
        return None

    async def mock_nl_success(self, isbn: str):
        return ExternalBook(
            title="국립도서관 단독 도서",
            author="도서관 저자",
            isbn=isbn,
            genre=GenreType.LITERATURE,
            kdc="813.6",
            subject="한국소설",
            publisher="도서관 출판사",
        )

    monkeypatch.setattr(Yes24Client, "lookup_by_isbn", mock_yes24_fail)
    monkeypatch.setattr(NationalLibraryClient, "lookup_by_isbn", mock_nl_success)

    resp_1 = await client.get(f"/api/v1/books/search?isbn={target_isbn}")
    assert resp_1.status_code == 200
    book_1 = resp_1.json()["book"]
    assert book_1 is not None
    assert book_1["title"] == "국립도서관 단독 도서"
    assert book_1["genre"] == "LITERATURE"
    assert book_1["link"] is None

    # 케이스 2: 국립도서관 실패(None) + YES24 성공
    async def mock_yes24_success(self, isbn: str):
        from app.schemas.search import BookSearchItem

        return BookSearchItem(
            title="마션 (SF 소설)",
            author="앤디 위어",
            isbn=isbn,
            publisher="RHK",
            total_pages=530,
            description="화성 조난 SF 생존기",
            link="https://www.yes24.com/Product/Goods/777",
        )

    async def mock_nl_fail(self, isbn: str):
        return None

    monkeypatch.setattr(Yes24Client, "lookup_by_isbn", mock_yes24_success)
    monkeypatch.setattr(NationalLibraryClient, "lookup_by_isbn", mock_nl_fail)

    resp_2 = await client.get(f"/api/v1/books/search?isbn={target_isbn}")
    assert resp_2.status_code == 200
    book_2 = resp_2.json()["book"]
    assert book_2 is not None
    assert book_2["title"] == "마션 (SF 소설)"
    # SF 키워드로 LITERATURE 추론
    assert book_2["genre"] == "LITERATURE"
    assert book_2["subject"] == "SF/과학소설"
    assert book_2["link"] == "https://www.yes24.com/Product/Goods/777"

    # 케이스 3: 양쪽 모두 실패(None)
    monkeypatch.setattr(Yes24Client, "lookup_by_isbn", mock_yes24_fail)
    monkeypatch.setattr(NationalLibraryClient, "lookup_by_isbn", mock_nl_fail)

    resp_3 = await client.get(f"/api/v1/books/search?isbn={target_isbn}")
    assert resp_3.status_code == 200
    assert resp_3.json()["total"] == 0
    assert resp_3.json()["book"] is None


@pytest.mark.asyncio
async def test_create_book_ai_timeout_kdc_fallback_consistency(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    """AI Agent 타임아웃 발생 시 KDC_FALLBACK 출처가 등록 및 조회까지 일관되게 유지되는지 검증"""

    async def mock_classify_timeout(
        self, title, author="", description=None, kdc=None, isbn=None
    ):
        return ClassifyGenreResult(
            genre=GenreType.LITERATURE,
            subject="한국문학",
            confidence=None,
            source="KDC_FALLBACK",
            reason="AI Agent request timed out",
        )

    monkeypatch.setattr(AiAgentClient, "classify_genre", mock_classify_timeout)

    payload = {
        "title": "타임아웃 폴백 도서",
        "author": "작가",
        "isbn": "9788937462566",
        "kdc": "810",
    }
    create_resp = await client.post("/api/v1/library/books", json=payload)
    assert create_resp.status_code == 201
    created_book = create_resp.json()
    assert created_book["genreSource"] == "KDC_FALLBACK"
    assert created_book["genreConfidence"] is None
    book_id = created_book["bookId"]

    # 단건 상세 조회에서도 KDC_FALLBACK 유지 확인
    detail_resp = await client.get(f"/api/v1/library/books/{book_id}")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["genreSource"] == "KDC_FALLBACK"


@pytest.mark.asyncio
async def test_create_and_update_book_invalid_genre_source_rejected(
    client: AsyncClient,
):
    """유효하지 않은 genre_source 인입 시 400 Bad Request 에러로 차단 검증"""
    # 1. 등록 시 잘못된 genre_source
    resp_create = await client.post(
        "/api/v1/library/books",
        json={
            "title": "비정상 출처 도서",
            "author": "저자",
            "genre_source": "HACKER_SOURCE",
        },
    )
    assert resp_create.status_code == 400
    assert resp_create.json()["code"] == "INVALID_BOOK_DATA"

    # 2. 정상 등록 후 수정 시 잘못된 genre_source
    valid_create = await client.post(
        "/api/v1/library/books",
        json={
            "title": "정상 도서",
            "author": "저자",
            "genre_source": "USER",
        },
    )
    assert valid_create.status_code == 201
    book_id = valid_create.json()["bookId"]

    resp_update = await client.patch(
        f"/api/v1/library/books/{book_id}",
        json={
            "title": "정상 도서",
            "author": "저자",
            "reading_status": "READING",
            "genre_source": "UNKNOWN_SOURCE",
        },
    )
    assert resp_update.status_code == 400
    assert resp_update.json()["code"] == "INVALID_BOOK_DATA"
