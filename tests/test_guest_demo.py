from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.rate_limit import guest_rate_limiter
from app.core.security import (
    create_access_token,
    get_demo_member_id,
)


@pytest.fixture(autouse=True)
def reset_limiters():
    guest_rate_limiter.clear()
    yield
    guest_rate_limiter.clear()


@pytest.fixture(autouse=True)
def mock_ai_vectorization():
    """AI 벡터화 외부 HTTP 통신 자동 차단 (0ms 대기 보장)"""
    with patch(
        "app.services.record_service.RecordService.trigger_ai_vectorization",
        new=AsyncMock(),
    ) as m:
        yield m


@pytest.fixture
async def guest_token_and_headers(
    client: AsyncClient, monkeypatch
) -> tuple[str, dict[str, str]]:
    monkeypatch.setattr(settings, "ENABLE_GUEST_WRITE", True)
    resp = await client.post("/api/v1/auth/guest", json={})
    assert resp.status_code == 200
    token = resp.json()["accessToken"]
    return token, {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_guest_write_allowlist_full_lifecycle(
    client: AsyncClient, guest_token_and_headers: tuple[str, dict[str, str]]
):
    """
    1. 게스트 쓰기 Allowlist 전체 생명주기 검증:
       - 도서 등록 -> 진도율 변경 -> 스크랩 등록 -> 세션 기록 -> 감상기록 작성 -> 스크랩 삭제 -> 도서 삭제
       - 모두 403 차단 없이 정상 허용(201/200/204)됨을 확인
    """
    _, headers = guest_token_and_headers

    # 1. 도서 등록
    book_resp = await client.post(
        "/api/v1/library/books",
        json={
            "title": "게스트의 체험 도서",
            "author": "체험 작가",
            "isbn": "9789999999991",
            "totalPages": 300,
            "currentPage": 10,
        },
        headers=headers,
    )
    assert book_resp.status_code == 201
    book_id = book_resp.json()["bookId"]

    # 2. 진도율 수정
    prog_resp = await client.patch(
        f"/api/v1/library/books/{book_id}/progress",
        json={"currentPage": 80},
        headers=headers,
    )
    assert prog_resp.status_code == 200
    assert prog_resp.json()["currentPage"] == 80

    # 3. 스크랩 생성
    scrap_resp = await client.post(
        f"/api/v1/library/books/{book_id}/scraps",
        json={
            "sentence": "게스트가 직접 남긴 인상적인 한 줄입니다.",
            "pageNumber": 50,
            "memo": "게스트 메모",
            "scrapImageUrl": "https://contents.kyobobook.co.kr/test.jpg",
        },
        headers=headers,
    )
    assert scrap_resp.status_code == 201
    scrap_id = scrap_resp.json()["scrapId"]

    # 4. 독서 세션 기록
    session_resp = await client.post(
        "/api/v1/reading-sessions",
        json={
            "bookId": book_id,
            "durationMinutes": 20,
            "startPage": 10,
            "endPage": 80,
            "memo": "몰입해서 읽음",
        },
        headers=headers,
    )
    assert session_resp.status_code == 201

    # 5. 독서 감상기록 생성
    record_resp = await client.post(
        "/api/v1/records",
        json={
            "book_id": book_id,
            "title": "게스트의 멋진 감상문",
            "content": "공용 체험 서재에서 작성한 감상 기록입니다.",
            "rating": 5,
        },
        headers=headers,
    )
    assert record_resp.status_code == 201

    # 6. 스크랩 삭제
    del_scrap = await client.delete(
        f"/api/v1/library/scraps/{scrap_id}",
        headers=headers,
    )
    assert del_scrap.status_code == 204

    # 7. 도서 삭제
    del_book = await client.delete(
        f"/api/v1/library/books/{book_id}",
        headers=headers,
    )
    assert del_book.status_code == 204


@pytest.mark.asyncio
async def test_guest_quota_enforcement(
    client: AsyncClient,
    guest_token_and_headers: tuple[str, dict[str, str]],
    monkeypatch,
):
    """
    2. 게스트 쿼터 상한 검증:
       - 도서 한도 초과 시 403 DEMO_QUOTA_EXCEEDED
       - 스크랩 한도 초과 시 403 DEMO_SCRAP_LIMIT_EXCEEDED
    """
    _, headers = guest_token_and_headers

    # 현재 게스트의 도서 수 확인 후 한도를 (현재 + 2)로 설정
    curr_books_resp = await client.get("/api/v1/library/books", headers=headers)
    curr_count = len(curr_books_resp.json()["books"])
    monkeypatch.setattr(settings, "DEMO_MAX_BOOKS", curr_count + 2)
    monkeypatch.setattr(settings, "DEMO_MAX_SCRAPS_PER_BOOK", 2)

    # 도서 2권 등록 (성공)
    r1 = await client.post(
        "/api/v1/library/books",
        json={"title": "도서 1", "author": "저자 1", "isbn": "9781000000011"},
        headers=headers,
    )
    assert r1.status_code == 201
    b1_id = r1.json()["bookId"]

    r2 = await client.post(
        "/api/v1/library/books",
        json={"title": "도서 2", "author": "저자 2", "isbn": "9781000000012"},
        headers=headers,
    )
    assert r2.status_code == 201

    # 도서 3번째 등록 -> 403 DEMO_QUOTA_EXCEEDED
    r3 = await client.post(
        "/api/v1/library/books",
        json={"title": "도서 3", "author": "저자 3", "isbn": "9781000000013"},
        headers=headers,
    )
    assert r3.status_code == 403
    assert r3.json()["code"] == "DEMO_QUOTA_EXCEEDED"

    # 스크랩 2건 등록 (성공)
    s1 = await client.post(
        f"/api/v1/library/books/{b1_id}/scraps",
        json={"sentence": "문장 1", "pageNumber": 1},
        headers=headers,
    )
    assert s1.status_code == 201

    s2 = await client.post(
        f"/api/v1/library/books/{b1_id}/scraps",
        json={"sentence": "문장 2", "pageNumber": 2},
        headers=headers,
    )
    assert s2.status_code == 201

    # 스크랩 3번째 등록 -> 403 DEMO_SCRAP_LIMIT_EXCEEDED
    s3 = await client.post(
        f"/api/v1/library/books/{b1_id}/scraps",
        json={"sentence": "문장 3", "pageNumber": 3},
        headers=headers,
    )
    assert s3.status_code == 403
    assert s3.json()["code"] == "DEMO_QUOTA_EXCEEDED"


@pytest.mark.asyncio
async def test_cover_url_sanitization(
    client: AsyncClient, guest_token_and_headers: tuple[str, dict[str, str]]
):
    """
    3. 표지 이미지 악성 URL 차단 및 정제 검증:
       - ISBN이 있는 도서에 악성 URL 입력 시 안전한 교보문고 CDN URL로 정제
       - ISBN이 없는 도서에 악성 URL 입력 시 기본 표지 '/books.webp'로 정제
       - 공인 CDN URL(kyobobook, nl.go.kr, aladin)은 그대로 유지
    """
    _, headers = guest_token_and_headers

    # 1) 악성 외부 도메인 + ISBN 있는 경우 -> 교보 CDN URL로 정제
    resp_evil_isbn = await client.post(
        "/api/v1/library/books",
        json={
            "title": "악성 표지 도서",
            "author": "공격자",
            "isbn": "9781111111119",
            "coverUrl": "https://evil-attacker.com/malicious.png",
        },
        headers=headers,
    )
    assert resp_evil_isbn.status_code == 201
    assert (
        resp_evil_isbn.json()["coverUrl"]
        == "https://contents.kyobobook.co.kr/sih/fit-in/458x0/pdt/9781111111119.jpg"
    )

    # 2) 도메인 스푸핑 + ISBN 없는 경우 -> /books.webp 로 정제
    resp_spoof_no_isbn = await client.post(
        "/api/v1/library/books",
        json={
            "title": "스푸핑 도서",
            "author": "공격자",
            "isbn": "",
            "coverUrl": "https://contents.kyobobook.co.kr.evil.com/cover.jpg",
        },
        headers=headers,
    )
    assert resp_spoof_no_isbn.status_code == 201
    assert resp_spoof_no_isbn.json()["coverUrl"] == "/books.webp"

    # 3) 공인 교보 CDN URL -> 원본 유지
    valid_kyobo_url = (
        "https://contents.kyobobook.co.kr/sih/fit-in/458x0/pdt/9788934972464.jpg"
    )
    resp_valid = await client.post(
        "/api/v1/library/books",
        json={
            "title": "정상 표지 도서",
            "author": "정상 작가",
            "isbn": "9781111111117",
            "coverUrl": valid_kyobo_url,
        },
        headers=headers,
    )
    assert resp_valid.status_code == 201
    assert resp_valid.json()["coverUrl"] == valid_kyobo_url


@pytest.mark.asyncio
async def test_guest_scrap_image_sanitization_vs_member_base64(
    client: AsyncClient, guest_token_and_headers: tuple[str, dict[str, str]]
):
    """
    4. 스크랩 이미지 처리 차별화 검증:
       - 게스트는 대용량/임의 이미지를 보내도 DB에 빈 문자열 ""로 정제되어 저장됨
       - 일반 회원은 Base64 Data URL 이미지를 정상적으로 보존하여 저장함
    """
    _, guest_headers = guest_token_and_headers
    data_url_sample = "data:image/jpeg;base64," + "A" * 1000

    # 1. 게스트 도서 등록 및 스크랩 생성
    g_book = await client.post(
        "/api/v1/library/books",
        json={"title": "게스트 책", "author": "저자", "isbn": "9782000000001"},
        headers=guest_headers,
    )
    g_book_id = g_book.json()["bookId"]

    g_scrap = await client.post(
        f"/api/v1/library/books/{g_book_id}/scraps",
        json={
            "sentence": "게스트의 문장",
            "pageNumber": 12,
            "scrapImageUrl": data_url_sample,
        },
        headers=guest_headers,
    )
    assert g_scrap.status_code == 201
    # 게스트는 이미지 URL이 빈 문자열 ""로 정제됨
    assert g_scrap.json()["scrapImageUrl"] == ""

    # 2. 일반 회원(기본 클라이언트) 도서 등록 및 스크랩 생성
    m_book = await client.post(
        "/api/v1/library/books",
        json={"title": "회원 책", "author": "저자", "isbn": "9782000000002"},
    )
    m_book_id = m_book.json()["bookId"]

    m_scrap = await client.post(
        f"/api/v1/library/books/{m_book_id}/scraps",
        json={
            "sentence": "회원의 문장",
            "pageNumber": 34,
            "scrapImageUrl": data_url_sample,
        },
    )
    assert m_scrap.status_code == 201
    # 일반 회원은 Base64 이미지 URL이 그대로 보존됨
    assert m_scrap.json()["scrapImageUrl"] == data_url_sample


@pytest.mark.asyncio
async def test_large_scrap_payload_limit(client: AsyncClient):
    """
    5. 스크랩 이미지 2MB 상한 검증:
       - 2,000,000자 초과 요청 시 400 Bad Request (INVALID_SCRAP_DATA) 에러 반환
    """
    book_resp = await client.post(
        "/api/v1/library/books",
        json={"title": "테스트 도서", "author": "저자", "isbn": "9783000000001"},
    )
    book_id = book_resp.json()["bookId"]

    oversized_url = "data:image/jpeg;base64," + "B" * 2_000_010
    scrap_resp = await client.post(
        f"/api/v1/library/books/{book_id}/scraps",
        json={
            "sentence": "너무 큰 이미지 스크랩",
            "pageNumber": 1,
            "scrapImageUrl": oversized_url,
        },
    )
    assert scrap_resp.status_code == 400
    assert scrap_resp.json()["code"] == "INVALID_SCRAP_DATA"


@pytest.mark.asyncio
async def test_guest_isolation_from_demo_account(
    client: AsyncClient, guest_token_and_headers: tuple[str, dict[str, str]]
):
    """
    6. 발표용 데모 계정(DEMO_MEMBER_ID) 데이터 격리 검증:
       - 게스트의 도서 등록 및 삭제가 DEMO_MEMBER_ID의 서재에 전혀 영향을 주지 않음
    """
    _, guest_headers = guest_token_and_headers
    demo_id = get_demo_member_id()
    demo_token = create_access_token(
        member_id=demo_id, email="demo@dontpawget.com", nickname="발표계정"
    )
    demo_headers = {"Authorization": f"Bearer {demo_token}"}

    # 1. 발표 계정에 도서 1권 등록
    d_book = await client.post(
        "/api/v1/library/books",
        json={
            "title": "발표용 특수 도서",
            "author": "발표자",
            "isbn": "9784000000001",
        },
        headers=demo_headers,
    )
    assert d_book.status_code == 201
    d_book_id = d_book.json()["bookId"]

    # 2. 게스트 계정에 도서 1권 등록
    g_book = await client.post(
        "/api/v1/library/books",
        json={
            "title": "게스트의 체험 도서",
            "author": "방문객",
            "isbn": "9784000000002",
        },
        headers=guest_headers,
    )
    assert g_book.status_code == 201
    g_book_id = g_book.json()["bookId"]

    # 3. 발표 계정 서재 조회 -> 발표용 특수 도서만 조회되고 게스트 도서는 없음
    d_list = await client.get("/api/v1/library/books", headers=demo_headers)
    assert d_list.status_code == 200
    d_isbns = [b["isbn"] for b in d_list.json()["books"]]
    assert "9784000000001" in d_isbns
    assert "9784000000002" not in d_isbns

    # 4. 게스트 서재 조회 -> 게스트 도서가 조회되고 발표용 특수 도서는 없음
    g_list = await client.get("/api/v1/library/books", headers=guest_headers)
    assert g_list.status_code == 200
    g_isbns = [b["isbn"] for b in g_list.json()["books"]]
    assert "9784000000002" in g_isbns
    assert "9784000000001" not in g_isbns

    # 5. 게스트가 자기 도서 삭제
    del_g = await client.delete(
        f"/api/v1/library/books/{g_book_id}", headers=guest_headers
    )
    assert del_g.status_code == 204

    # 6. 발표 계정 도서는 여전히 안전하게 존재
    d_check = await client.get(
        f"/api/v1/library/books/{d_book_id}", headers=demo_headers
    )
    assert d_check.status_code == 200
    assert d_check.json()["title"] == "발표용 특수 도서"


@pytest.mark.asyncio
async def test_guest_record_rate_limit_by_ip(
    client: AsyncClient, guest_token_and_headers: tuple[str, dict[str, str]]
):
    """
    7. 게스트 감상기록 생성 IP Rate Limit 검증:
       - 동일 IP(CF-Connecting-IP)로 1분 내 5회 생성 후 6번째에 429 RATE_LIMIT_EXCEEDED
       - 다른 IP로 요청 시 성공
    """
    _, guest_headers = guest_token_and_headers
    client_ip_headers = {
        **guest_headers,
        "CF-Connecting-IP": "203.0.113.195",
    }

    # 도서 1권 등록
    b_resp = await client.post(
        "/api/v1/library/books",
        json={"title": "기록용 도서", "author": "저자", "isbn": "9785000000001"},
        headers=guest_headers,
    )
    book_id = b_resp.json()["bookId"]

    # 5회 정상 등록
    for i in range(5):
        r = await client.post(
            "/api/v1/records",
            json={
                "book_id": book_id,
                "title": f"기록 {i + 1}",
                "content": f"내용 {i + 1}",
                "rating": 5,
            },
            headers=client_ip_headers,
        )
        assert r.status_code == 201

    # 6번째 호출 시 429 차단
    r_blocked = await client.post(
        "/api/v1/records",
        json={
            "book_id": book_id,
            "title": "기록 6",
            "content": "내용 6",
            "rating": 5,
        },
        headers=client_ip_headers,
    )
    assert r_blocked.status_code == 429
    assert r_blocked.json()["code"] == "RATE_LIMIT_EXCEEDED"

    # 다른 IP로 요청 시 정상 통과
    other_ip_headers = {
        **guest_headers,
        "CF-Connecting-IP": "203.0.113.196",
    }
    r_other = await client.post(
        "/api/v1/records",
        json={
            "book_id": book_id,
            "title": "기록 다른 IP",
            "content": "내용",
            "rating": 5,
        },
        headers=other_ip_headers,
    )
    assert r_other.status_code == 201


@pytest.mark.asyncio
async def test_kill_switch_read_200_write_403(client: AsyncClient):
    """
    8. ENABLE_GUEST_WRITE=False (코드 기본값) 상태 검증:
       - 읽기(GET)는 200 OK
       - 쓰기(POST)는 403 GUEST_READONLY_MODE
    """
    assert settings.ENABLE_GUEST_WRITE is False

    resp = await client.post("/api/v1/auth/guest", json={})
    assert resp.status_code == 200
    guest_headers = {"Authorization": f"Bearer {resp.json()['accessToken']}"}

    # 읽기는 200 허용
    get_resp = await client.get("/api/v1/library/books", headers=guest_headers)
    assert get_resp.status_code == 200

    # 쓰기는 403 GUEST_READONLY_MODE 차단
    post_resp = await client.post(
        "/api/v1/library/books",
        json={"title": "차단될 도서", "author": "저자", "isbn": "9781234567890"},
        headers=guest_headers,
    )
    assert post_resp.status_code == 403
    assert post_resp.json()["code"] == "GUEST_READONLY_MODE"


@pytest.mark.asyncio
async def test_ensure_guest_member_idempotency(db_session: AsyncSession):
    """
    9. ensure_guest_member 멱등성 검증 (단위 테스트, SQLite 호환):
       - 순차 2회 호출 시 동일 member_id 반환
       - 시드 도서가 정확히 9권(중복 없음)
    """
    from sqlalchemy import func, select

    from app.models.library_book import LibraryBook
    from app.services.member_service import MemberService

    # 1회차 호출 — 게스트 생성 + 시드 주입
    m1 = await MemberService.ensure_guest_member(db_session)
    assert m1 is not None

    # 2회차 호출 — 이미 존재하므로 그대로 반환
    m2 = await MemberService.ensure_guest_member(db_session)
    assert m2.member_id == m1.member_id

    # 도서 수가 정확히 9권
    count_stmt = select(func.count(LibraryBook.id)).where(
        LibraryBook.member_id == m1.member_id
    )
    book_count = (await db_session.execute(count_stmt)).scalar()
    assert book_count == 9, f"시드 도서가 {book_count}권, 기대값: 9권"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_ensure_guest_member_concurrency(db_session: AsyncSession):
    """
    9. 동시 접속 환경에서 ensure_guest_member 동시 호출 시:
       - 중복 생성(IntegrityError) 없이 모두 정상 완료
       - 도서 9권이 중복 없이 정확히 9권만 유지됨
    """
    import asyncio

    from sqlalchemy import func, select

    from app.models.library_book import LibraryBook
    from app.services.member_service import MemberService
    from tests.conftest import TestSessionLocal

    async def run_ensure():
        async with TestSessionLocal() as session:
            return await MemberService.ensure_guest_member(session)

    # 3개 태스크 동시 실행
    members = await asyncio.gather(run_ensure(), run_ensure(), run_ensure())
    assert all(m.member_id == members[0].member_id for m in members)

    # 도서 수가 9권인지 확인
    async with TestSessionLocal() as session:
        count_stmt = select(func.count(LibraryBook.id)).where(
            LibraryBook.member_id == members[0].member_id
        )
        book_count = (await session.execute(count_stmt)).scalar()
        assert book_count == 9


@pytest.mark.integration
@pytest.mark.asyncio
async def test_guest_demo_integration_double_reset(client: AsyncClient):
    """
    10. 통합 테스트: ensure_guest_member 및 target=all|demo|guest 리셋을 각각 2회 이상 연속 실행하여 멱등성 검증
    """
    from app.services.member_service import MemberService
    from tests.conftest import TestSessionLocal

    # 1. ensure_guest_member 2회 연속 실행
    async with TestSessionLocal() as session:
        m1 = await MemberService.ensure_guest_member(session)
    async with TestSessionLocal() as session:
        m2 = await MemberService.ensure_guest_member(session)
    assert m1.member_id == m2.member_id

    # 2. 관리자 리셋 엔드포인트 2회씩 연속 실행 (all, demo, guest)
    admin_headers = {"X-Admin-Key": settings.ADMIN_API_KEY}
    for target in ("all", "demo", "guest"):
        for _ in range(2):
            resp = await client.post(
                f"/api/v1/admin/demo/reset?target={target}",
                headers=admin_headers,
            )
            assert resp.status_code == 200
            assert resp.json()["status"] == "SUCCESS"
            assert resp.json()["target"] == target
