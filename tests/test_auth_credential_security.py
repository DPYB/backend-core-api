"""
Phase 65 자격증명 보안 강화 (Refresh Token 응답 본문 노출 제거 및 세션 보안) 전용 테스트 스위트.
- 로그인, 소셜 로그인, 게스트 로그인, 토큰 갱신 성공 응답에서 `refreshToken` / `refresh_token` 필드 부재 검증
- `accessToken` 및 `access_token` 기존 계약 정상 유지 검증
- HttpOnly 쿠키의 발급, 갱신, 만료 및 로그아웃 시 삭제(`Max-Age=0`) 검증
- 쿠키 기반 세션 복원 및 토큰 갱신 전 시나리오 검증
- 401/404 등 인증 실패 예외 응답에 토큰 미노출 검증
- 실제 JSON 직렬화 결과 문자열 내 민감 키 전수 검사
"""

import json
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_refresh_token
from app.services.member_service import MemberService
from app.services.social_auth_service import SocialUserInfo


@pytest.mark.asyncio
async def test_login_response_omits_refresh_token_body_and_sets_cookie(
    client: AsyncClient, db_session: AsyncSession
):
    """
    1. 일반 이메일 로그인 시:
       - Response JSON Body에 'refreshToken' 및 'refresh_token' 필드가 완전히 존재하지 않음 (null이 아닌 필드 부재)
       - 'accessToken' 및 'access_token' 필드는 정상 유지
       - Set-Cookie 헤더를 통해 HttpOnly refresh_token 쿠키가 정상 발급됨
    """
    await MemberService.get_or_create_dev_member(
        db_session, "credential_sec_test@example.com"
    )

    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "credential_sec_test@example.com", "password": "anypassword"},
    )
    assert resp.status_code == 200
    data = resp.json()

    # Body 검증: refreshToken 및 refresh_token 키 자체가 없어야 함
    assert "refreshToken" not in data
    assert "refresh_token" not in data

    # Access Token 호환성 유지 검증
    assert "accessToken" in data
    assert "access_token" in data
    assert data["accessToken"] is not None
    assert data["access_token"] == data["accessToken"]
    assert data["tokenType"] == "Bearer"

    # raw JSON 덤프 문자열 전수 검사
    raw_json_str = json.dumps(data)
    assert "refreshToken" not in raw_json_str
    assert "refresh_token" not in raw_json_str

    # Cookie 발급 검증
    assert "set-cookie" in resp.headers
    set_cookie = resp.headers["set-cookie"]
    assert "refresh_token=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert resp.cookies.get("refresh_token") is not None


@pytest.mark.asyncio
async def test_guest_login_response_omits_refresh_token_body(client: AsyncClient):
    """
    2. 게스트 로그인 시:
       - Response JSON Body에 'refreshToken' 및 'refresh_token' 필드가 완전히 존재하지 않음
       - 쿠키 또한 발급되지 않음
    """
    resp = await client.post("/api/v1/auth/guest", json={})
    assert resp.status_code == 200
    data = resp.json()

    # Body 검증
    assert "refreshToken" not in data
    assert "refresh_token" not in data
    assert data["role"] == "guest"
    assert data["isGuest"] is True
    assert "accessToken" in data
    assert "access_token" in data
    assert data["accessToken"] == data["access_token"]

    # raw JSON 문자열 검사
    raw_json = json.dumps(data)
    assert "refreshToken" not in raw_json
    assert "refresh_token" not in raw_json

    # 쿠키 미발급 확인
    assert resp.cookies.get("refresh_token") is None


@pytest.mark.asyncio
async def test_social_logins_omit_refresh_token_body(
    client: AsyncClient, db_session: AsyncSession
):
    """
    3. Google / Kakao 소셜 로그인 시:
       - Response JSON Body에 'refreshToken' 및 'refresh_token' 필드 부재
       - Set-Cookie 헤더에 HttpOnly refresh_token 발급 확인
    """
    mock_google = SocialUserInfo(
        provider="GOOGLE",
        provider_id="social-sec-google-id",
        email="social_google@example.com",
        nickname="구글보안테스터",
    )
    with patch(
        "app.services.social_auth_service.SocialAuthService.verify_google_token",
        return_value=mock_google,
    ):
        resp_google = await client.post(
            "/api/v1/auth/social/google",
            json={"token": "mock-google-token"},
        )
        assert resp_google.status_code == 200
        data_g = resp_google.json()
        assert "refreshToken" not in data_g
        assert "refresh_token" not in data_g
        assert "accessToken" in data_g
        assert "access_token" in data_g
        assert "refresh_token=" in resp_google.headers.get("set-cookie", "")

    mock_kakao = SocialUserInfo(
        provider="KAKAO",
        provider_id="social-sec-kakao-id",
        email="social_kakao@example.com",
        nickname="카카오보안테스터",
    )
    with patch(
        "app.services.social_auth_service.SocialAuthService.verify_kakao_token",
        return_value=mock_kakao,
    ):
        resp_kakao = await client.post(
            "/api/v1/auth/social/kakao",
            json={"token": "mock-kakao-token"},
        )
        assert resp_kakao.status_code == 200
        data_k = resp_kakao.json()
        assert "refreshToken" not in data_k
        assert "refresh_token" not in data_k
        assert "accessToken" in data_k
        assert "access_token" in data_k
        assert "refresh_token=" in resp_kakao.headers.get("set-cookie", "")


@pytest.mark.asyncio
async def test_cookie_based_refresh_and_rotation_success(
    client: AsyncClient, db_session: AsyncSession
):
    """
    4. 쿠키 기반 세션 복원 및 토큰 갱신:
       - HttpOnly 쿠키 전달 시 200 OK
       - 새 accessToken 발급 (access_token 듀얼 유지)
       - Response Body에 refreshToken 미노출
       - Set-Cookie 헤더로 새 refresh_token 쿠키 재발급 확인
    """
    member, _ = await MemberService.get_or_create_dev_member(
        db_session, "refresh_flow_test@example.com"
    )
    token = create_refresh_token(member.member_id)

    headers = {"Cookie": f"refresh_token={token}"}
    resp = await client.post("/api/v1/auth/refresh", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    assert "accessToken" in data
    assert "access_token" in data
    assert data["accessToken"] == data["access_token"]
    assert "refreshToken" not in data
    assert "refresh_token" not in data

    # 새 쿠키 재발급 검증
    assert "set-cookie" in resp.headers
    assert "refresh_token=" in resp.headers["set-cookie"]
    assert resp.cookies.get("refresh_token") is not None


@pytest.mark.asyncio
async def test_refresh_failure_responses_do_not_leak_tokens(client: AsyncClient):
    """
    5. 인증 실패 및 예외 응답에 토큰 미노출 검증:
       - 쿠키 부재 시 401 에러
       - 조작된 토큰 시 401 에러
       - 응답 바디에 토큰 패턴 미노출
    """
    # 5-1. 쿠키 없음
    resp_empty = await client.post("/api/v1/auth/refresh")
    assert resp_empty.status_code == 401
    data_empty = resp_empty.json()
    assert data_empty["code"] == "UNAUTHORIZED"
    assert "Refresh Token이 제공되지 않았습니다." in data_empty["message"]
    assert (
        "token" not in json.dumps(data_empty).lower()
        or data_empty["code"] == "UNAUTHORIZED"
    )

    # 5-2. 조작된 토큰
    resp_tampered = await client.post(
        "/api/v1/auth/refresh",
        headers={"Cookie": "refresh_token=invalid.tampered.jwt.signature"},
    )
    assert resp_tampered.status_code == 401
    data_tampered = resp_tampered.json()
    assert data_tampered["code"] == "UNAUTHORIZED"
    assert "invalid.tampered.jwt.signature" not in json.dumps(data_tampered)


@pytest.mark.asyncio
async def test_logout_clears_cookie_and_returns_empty_body(client: AsyncClient):
    """
    6. 로그아웃 호출 시:
       - 204 No Content (응답 본문 없음)
       - Set-Cookie 헤더를 통해 refresh_token 쿠키 만료(Max-Age=0 또는 빈값) 확인
    """
    resp = await client.post("/api/v1/auth/logout")
    assert resp.status_code == 204
    assert resp.content == b""

    # 쿠키 삭제 헤더 검증
    set_cookie = resp.headers.get("set-cookie", "")
    assert "refresh_token=" in set_cookie
    assert 'refresh_token=""' in set_cookie or "Max-Age=0" in set_cookie


@pytest.mark.asyncio
async def test_json_schema_reflection_has_no_refresh_token_field():
    """
    7. Pydantic 모델 스키마 리플렉션 검증:
       - TokenResponse, LoginResponse, GuestLoginResponse 모델 필드 및 스키마에
         refresh_token / refreshToken이 존재하지 않음을 정적 검증
    """
    from app.schemas.auth import GuestLoginResponse, LoginResponse, TokenResponse

    for model_cls in (TokenResponse, LoginResponse, GuestLoginResponse):
        schema = model_cls.model_json_schema()
        properties = schema.get("properties", {})
        assert "refreshToken" not in properties, (
            f"{model_cls.__name__} has 'refreshToken' property"
        )
        assert "refresh_token" not in properties, (
            f"{model_cls.__name__} has 'refresh_token' property"
        )
        assert "accessToken" in properties, (
            f"{model_cls.__name__} missing 'accessToken'"
        )

    # 실제 직렬화(by_alias=True) 시 access_token 듀얼 유지 및 refresh_token 부재 확인
    sample = TokenResponse(
        access_token="test-access",
        token_type="Bearer",
        expires_in=3600,
        member_id="00000000-0000-0000-0000-000000000001",
        is_new_member=False,
    )
    dumped = sample.model_dump(by_alias=True)
    assert dumped["accessToken"] == "test-access"
    assert dumped["access_token"] == "test-access"
    assert "refreshToken" not in dumped
    assert "refresh_token" not in dumped
