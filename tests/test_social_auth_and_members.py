import uuid
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.librarian import Librarian
from app.models.library_book import LibraryBook
from app.models.member import Member
from app.models.record import Record
from app.models.shelf import Shelf
from app.services.social_auth_service import SocialUserInfo


@pytest.mark.asyncio
async def test_google_social_login_and_auto_signup(
    client: AsyncClient, db_session: AsyncSession
):
    """Google 소셜 로그인 시 신규 회원이 자동 생성되고 기본 책장이 생성되는지 검증"""
    mock_google_info = SocialUserInfo(
        provider="GOOGLE",
        provider_id="google-sub-123456",
        email="testuser@google.com",
        nickname="구글테스터",
        profile_image_url="https://example.com/avatar.jpg",
    )

    with patch(
        "app.services.social_auth_service.SocialAuthService.verify_google_token",
        return_value=mock_google_info,
    ):
        resp = await client.post(
            "/api/v1/auth/social/google",
            json={"token": "mock-valid-google-id-token"},
        )
        assert resp.status_code == 200
        data = resp.json()

        assert data["tokenType"] == "Bearer"
        assert data["isNewMember"] is True
        assert "accessToken" in data
        assert "refreshToken" in data

        member_id = uuid.UUID(data["memberId"])

        # DB 검증: Member 레코드 생성 확인
        stmt = select(Member).where(Member.member_id == member_id)
        res = await db_session.execute(stmt)
        member = res.scalars().first()
        assert member is not None
        assert member.email == "testuser@google.com"
        assert member.nickname == "구글테스터"
        assert member.status == "ACTIVE"

        # DB 검증: 기본 책장이 자동 생성되었는지 확인
        stmt_shelf = select(Shelf).where(
            Shelf.member_id == member_id, Shelf.is_default.is_(True)
        )
        res_shelf = await db_session.execute(stmt_shelf)
        shelf = res_shelf.scalars().first()
        assert shelf is not None
        assert shelf.is_default is True

        # 동일 계정 재로그인 시 기존 회원으로 로그인 (isNewMember = False)
        resp2 = await client.post(
            "/api/v1/auth/social/google",
            json={"token": "mock-valid-google-id-token"},
        )
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["isNewMember"] is False
        assert data2["memberId"] == str(member_id)


@pytest.mark.asyncio
async def test_kakao_social_login(client: AsyncClient, db_session: AsyncSession):
    """Kakao 소셜 로그인 및 토큰 발급 검증"""
    mock_kakao_info = SocialUserInfo(
        provider="KAKAO",
        provider_id="kakao-id-987654",
        email="kakao_987654@dontpawget.app",
        nickname="카카오테스터",
        profile_image_url=None,
    )

    with patch(
        "app.services.social_auth_service.SocialAuthService.verify_kakao_token",
        return_value=mock_kakao_info,
    ):
        resp = await client.post(
            "/api/v1/auth/social/kakao",
            json={"token": "mock-valid-kakao-access-token"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["isNewMember"] is True
        assert data["tokenType"] == "Bearer"


@pytest.mark.asyncio
async def test_refresh_token_endpoint(client: AsyncClient, db_session: AsyncSession):
    """Refresh Token을 이용한 토큰 갱신 검증"""
    mock_user = SocialUserInfo(
        provider="GOOGLE",
        provider_id="google-refresh-test",
        email="refresh@test.com",
        nickname="리프레시유저",
    )
    with patch(
        "app.services.social_auth_service.SocialAuthService.verify_google_token",
        return_value=mock_user,
    ):
        login_resp = await client.post(
            "/api/v1/auth/social/google",
            json={"token": "mock-token"},
        )
        refresh_token = login_resp.json()["refreshToken"]

    # refresh 요청
    refresh_resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refreshToken": refresh_token},
    )
    assert refresh_resp.status_code == 200
    data = refresh_resp.json()
    assert "accessToken" in data
    assert "refreshToken" in data
    assert data["isNewMember"] is False


@pytest.mark.asyncio
async def test_logout_endpoint(client: AsyncClient):
    """로그아웃 호출 시 204 No Content 멱등 응답 검증"""
    resp = await client.post("/api/v1/auth/logout")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_availability_check(client: AsyncClient, db_session: AsyncSession):
    """이메일 및 닉네임 중복 확인 검증"""
    # 1. 새 회원 생성
    member = Member(
        member_id=uuid.uuid4(),
        email="taken@example.com",
        nickname="이미있는닉네임",
        status="ACTIVE",
    )
    db_session.add(member)
    await db_session.commit()

    # 이메일 중복 체크 (이미 존재)
    resp = await client.post(
        "/api/v1/auth/availability",
        json={"field": "email", "value": "taken@example.com"},
    )
    assert resp.status_code == 200
    assert resp.json()["isAvailable"] is False

    # 이메일 중복 체크 (사용 가능)
    resp = await client.post(
        "/api/v1/auth/availability",
        json={"field": "email", "value": "available@example.com"},
    )
    assert resp.status_code == 200
    assert resp.json()["isAvailable"] is True

    # 닉네임 중복 체크 (이미 존재)
    resp = await client.post(
        "/api/v1/auth/availability",
        json={"field": "nickname", "value": "이미있는닉네임"},
    )
    assert resp.status_code == 200
    assert resp.json()["isAvailable"] is False

    # 닉네임 중복 체크 (사용 가능)
    resp = await client.post(
        "/api/v1/auth/availability",
        json={"field": "nickname", "value": "완전새로운닉네임"},
    )
    assert resp.status_code == 200
    assert resp.json()["isAvailable"] is True


@pytest.mark.asyncio
async def test_profile_and_withdrawal_cascade(
    client: AsyncClient, db_session: AsyncSession
):
    """프로필 조회, 수정 및 회원 탈퇴 시 데이터 Cascade 소프트 삭제 검증"""
    member_id = uuid.uuid4()
    member = Member(
        member_id=member_id,
        email="user_me@example.com",
        nickname="내프로필유저",
        status="ACTIVE",
    )
    db_session.add(member)
    await db_session.commit()

    # 토큰 발급
    auth_token = create_access_token(member_id, member.email, member.nickname)
    headers = {"Authorization": f"Bearer {auth_token}"}

    # 1. 내 프로필 조회 (GET /api/v1/users/me)
    get_resp = await client.get("/api/v1/users/me", headers=headers)
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["nickname"] == "내프로필유저"
    assert data["email"] == "user_me@example.com"

    # 2. 내 프로필 수정 (PATCH /api/v1/users/me)
    patch_resp = await client.patch(
        "/api/v1/users/me",
        headers=headers,
        json={"nickname": "수정된닉네임"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["nickname"] == "수정된닉네임"

    # 3. 데이터 등록: 책장, 도서, 독서기록
    shelf = Shelf(member_id=member_id, name="테스트책장", is_default=False)
    db_session.add(shelf)
    await db_session.flush()

    book = LibraryBook(
        member_id=member_id,
        shelf_id=shelf.id,
        shelf_rank="a0",
        isbn="9788934972464",
        title="소프트웨어의 품격",
        author="작가",
    )
    db_session.add(book)

    rec = Record(
        member_id=member_id,
        book_id=1,
        title="좋은 책",
        content="감상평",
    )
    db_session.add(rec)
    await db_session.commit()

    # 4. 회원 탈퇴 (DELETE /api/v1/users/me)
    del_resp = await client.delete("/api/v1/users/me", headers=headers)
    assert del_resp.status_code == 204

    # 5. 탈퇴 후 프로필 조회 시 404
    after_resp = await client.get("/api/v1/users/me", headers=headers)
    assert after_resp.status_code == 404

    # 6. 연관 데이터 소프트 삭제 일괄 확인
    res_b = await db_session.execute(
        select(LibraryBook).where(LibraryBook.member_id == member_id)
    )
    assert res_b.scalars().first().deleted_at is not None

    res_s = await db_session.execute(select(Shelf).where(Shelf.member_id == member_id))
    assert res_s.scalars().first().deleted_at is not None

    res_r = await db_session.execute(
        select(Record).where(Record.member_id == member_id)
    )
    assert res_r.scalars().first().deleted_at is not None


@pytest.mark.asyncio
async def test_dev_login_auto_signup_and_cookie(
    client: AsyncClient, db_session: AsyncSession
):
    """개발/프론트 호환 로그인 시 자동 가입, 기본책장/고양이 사서 지급 및 쿠키 발급 검증"""
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "frontend_dev@example.com", "password": "anypassword"},
    )
    assert resp.status_code == 200
    data = resp.json()

    # snake_case 및 camelCase 듀얼 지원 확인
    assert data["accessToken"] is not None
    assert data["access_token"] == data["accessToken"]
    assert data["refreshToken"] is not None
    assert data["refresh_token"] == data["refreshToken"]
    assert data["tokenType"] == "Bearer"
    assert data["isNewMember"] is True

    # member 프로필 필드 포함 확인 (프론트 AuthProvider 연동)
    assert "member" in data
    assert data["member"]["email"] == "frontend_dev@example.com"
    assert data["member"]["nickname"] == "frontend_dev"

    # Set-Cookie 헤더에 refresh_token 포함 확인
    assert "set-cookie" in resp.headers
    assert "refresh_token=" in resp.headers["set-cookie"]
    assert "HttpOnly" in resp.headers["set-cookie"]

    member_id = uuid.UUID(data["memberId"])

    # DB 검증: 기본 책장 생성 확인
    stmt_shelf = select(Shelf).where(
        Shelf.member_id == member_id, Shelf.is_default.is_(True)
    )
    shelf = (await db_session.execute(stmt_shelf)).scalars().first()
    assert shelf is not None
    assert shelf.is_default is True

    # DB 검증: 기본 대표 고양이 사서(CAT) 자동 생성 확인
    stmt_lib = select(Librarian).where(
        Librarian.member_id == member_id, Librarian.is_representative.is_(True)
    )
    lib = (await db_session.execute(stmt_lib)).scalars().first()
    assert lib is not None
    assert lib.name == "블루"
    assert lib.level == 1

    # 동일 이메일 재로그인 시 기존 회원 조회 (isNewMember = False)
    resp2 = await client.post(
        "/api/v1/auth/login",
        json={"email": "frontend_dev@example.com", "password": "anypassword"},
    )
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["isNewMember"] is False
    assert data2["memberId"] == str(member_id)


@pytest.mark.asyncio
async def test_refresh_token_via_cookie(client: AsyncClient, db_session: AsyncSession):
    """쿠키(HttpOnly)로 전달된 refresh_token을 이용한 세션 갱신 검증"""
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "cookie_user@example.com"},
    )
    refresh_token = login_resp.json()["refreshToken"]

    # 바디 없이 쿠키 헤더만 전송하여 refresh 호출
    headers = {"Cookie": f"refresh_token={refresh_token}"}
    refresh_resp = await client.post(
        "/api/v1/auth/refresh",
        headers=headers,
    )
    assert refresh_resp.status_code == 200
    data = refresh_resp.json()
    assert "accessToken" in data
    assert "access_token" in data
    assert data["accessToken"] is not None
    # 새 refresh 쿠키 재발급 확인
    assert "set-cookie" in refresh_resp.headers
    assert "refresh_token=" in refresh_resp.headers["set-cookie"]


@pytest.mark.asyncio
async def test_refresh_token_cookie_samesite_in_production(
    client: AsyncClient, monkeypatch
):
    """프로덕션 환경에서 SameSite=None 및 Secure=True 쿠키 발급 검증"""
    from app.config import settings

    monkeypatch.setattr(settings, "ENV", "production")

    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "prod_cookie@example.com"},
    )
    set_cookie_header = login_resp.headers.get("set-cookie", "")
    assert "samesite=none" in set_cookie_header.lower()
    assert "secure" in set_cookie_header.lower()


@pytest.mark.asyncio
async def test_logout_removes_refresh_cookie(client: AsyncClient):
    """로그아웃 호출 시 refresh_token 쿠키가 만료/삭제되는지 검증"""
    resp = await client.post("/api/v1/auth/logout")
    assert resp.status_code == 204
    assert "set-cookie" in resp.headers
    assert (
        'refresh_token=""' in resp.headers["set-cookie"]
        or "Max-Age=0" in resp.headers["set-cookie"]
    )
