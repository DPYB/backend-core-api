import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import guest_rate_limiter
from app.core.security import decode_jwt_token, get_demo_member_id


@pytest.fixture(autouse=True)
def reset_guest_rate_limiter():
    """각 테스트 격리를 위해 Rate Limiter 초기화"""
    guest_rate_limiter.clear()
    yield
    guest_rate_limiter.clear()


@pytest.mark.asyncio
async def test_guest_token_new_issue_and_claims(client: AsyncClient):
    """
    1. 신규 게스트 토큰 발급:
       - sub: guest-{uuid}
       - role: guest
       - email, name 클레임 없음 (Null 안전)
    """
    resp = await client.post("/api/v1/auth/guest", json={})
    assert resp.status_code == 200
    data = resp.json()

    assert data["tokenType"] == "Bearer"
    assert data["role"] == "guest"
    assert data["isGuest"] is True
    assert "accessToken" in data
    assert data["sub"].startswith("guest-")
    assert data["guestId"] in data["sub"]

    # 디코딩 및 클레임 검증
    payload = decode_jwt_token(data["accessToken"])
    assert payload["role"] == "guest"
    assert payload["sub"] == data["sub"]
    assert "email" not in payload
    assert "name" not in payload
    assert "nickname" not in payload


@pytest.mark.asyncio
async def test_guest_token_refresh_session_maintenance(client: AsyncClient):
    """
    2. 세션 유지 (Refresh/연장):
       - 바디에 guest_id가 들어오면 새 UUID를 만들지 않고 동일 ID 유지
    """
    original_guest_id = str(uuid.uuid4())
    resp = await client.post(
        "/api/v1/auth/guest",
        json={"guestId": original_guest_id},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["guestId"] == original_guest_id
    assert data["sub"] == f"guest-{original_guest_id}"

    payload = decode_jwt_token(data["accessToken"])
    assert payload["sub"] == f"guest-{original_guest_id}"
    assert payload["role"] == "guest"


@pytest.mark.asyncio
async def test_rate_limit_split_issue_vs_refresh(client: AsyncClient):
    """
    3. Rate Limit 분리:
       - 신규 발급(guest_id 없음)은 빡빡한 IP 제한 (5회 초과 시 429)
       - 갱신(guest_id 있음)은 널널하게 별도 버킷 카운팅 (5회 초과해도 통과)
    """
    # [신규 발급] 5회 성공 후 6번째 429 차단
    for _ in range(5):
        r = await client.post("/api/v1/auth/guest", json={})
        assert r.status_code == 200

    r_blocked = await client.post("/api/v1/auth/guest", json={})
    assert r_blocked.status_code == 429
    assert r_blocked.json()["code"] == "RATE_LIMIT_EXCEEDED"

    # [갱신] 신규 발급이 차단된 상태에서도 갱신(guest_id 보유)은 별도 버킷이므로 정상 통과!
    refresh_id = str(uuid.uuid4())
    r_refresh = await client.post(
        "/api/v1/auth/guest",
        json={"guestId": refresh_id},
    )
    assert r_refresh.status_code == 200
    assert r_refresh.json()["guestId"] == refresh_id


@pytest.mark.asyncio
async def test_guest_token_maps_to_demo_member_id_on_read(
    client: AsyncClient, db_session: AsyncSession
):
    """
    4. Mock 데이터 중앙 매핑:
       - 게스트 토큰으로 GET 요청 시 DEMO_MEMBER_ID로 매핑되어 기본 책장 및 대표 사서 조회 성공
    """
    guest_resp = await client.post("/api/v1/auth/guest", json={})
    guest_token = guest_resp.json()["accessToken"]
    guest_headers = {"Authorization": f"Bearer {guest_token}"}

    # 책장 조회 (GET /api/v1/library/shelves)
    shelves_resp = await client.get("/api/v1/library/shelves", headers=guest_headers)
    assert shelves_resp.status_code == 200
    shelves = shelves_resp.json()["shelves"]
    assert len(shelves) >= 1
    assert shelves[0]["name"] == "기본 책장"

    # 대표 사서 조회 (GET /api/v1/librarians/representative)
    rep_resp = await client.get(
        "/api/v1/librarians/representative", headers=guest_headers
    )
    assert rep_resp.status_code == 200
    assert rep_resp.json()["name"] == "블루"
    assert rep_resp.json()["type"] == "CAT"

    # 내 프로필 조회 (GET /api/v1/users/me) - email, nickname이 null이어도 crash 없이 정상 처리
    profile_resp = await client.get("/api/v1/users/me", headers=guest_headers)
    assert profile_resp.status_code == 200
    p_data = profile_resp.json()
    assert p_data["memberId"] == str(get_demo_member_id())


@pytest.mark.asyncio
async def test_guest_token_readonly_lock_blocks_all_mutations(client: AsyncClient):
    """
    5. 무결점 Read-Only 락:
       - role == 'guest'일 때 모든 POST/PUT/PATCH/DELETE 요청을 403 Forbidden으로 차단
    """
    guest_resp = await client.post("/api/v1/auth/guest", json={})
    guest_token = guest_resp.json()["accessToken"]
    guest_headers = {"Authorization": f"Bearer {guest_token}"}

    # 1. POST 책장 생성 시도 -> 403 차단
    post_shelf = await client.post(
        "/api/v1/library/shelves",
        json={"name": "게스트의 불법 책장"},
        headers=guest_headers,
    )
    assert post_shelf.status_code == 403
    assert post_shelf.json()["code"] == "GUEST_READONLY_MODE"

    # 2. POST 도서 등록 시도 -> 403 차단
    post_book = await client.post(
        "/api/v1/library/books",
        json={"title": "게스트의 불법 도서", "author": "해커"},
        headers=guest_headers,
    )
    assert post_book.status_code == 403
    assert post_book.json()["code"] == "GUEST_READONLY_MODE"

    # 3. PATCH 프로필 수정 시도 -> 403 차단
    patch_user = await client.patch(
        "/api/v1/users/me",
        json={"nickname": "해커게스트"},
        headers=guest_headers,
    )
    assert patch_user.status_code == 403
    assert patch_user.json()["code"] == "GUEST_READONLY_MODE"

    # 4. DELETE 회원 탈퇴 시도 -> 403 차단
    del_user = await client.delete("/api/v1/users/me", headers=guest_headers)
    assert del_user.status_code == 403
    assert del_user.json()["code"] == "GUEST_READONLY_MODE"

    # 5. POST 독서 기록 작성 시도 -> 403 차단
    post_rec = await client.post(
        "/api/v1/records",
        json={"title": "게스트 독서록", "content": "내용"},
        headers=guest_headers,
    )
    assert post_rec.status_code == 403
    assert post_rec.json()["code"] == "GUEST_READONLY_MODE"
