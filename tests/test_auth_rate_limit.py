import asyncio
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import auth_rate_limiter
from app.core.security import create_access_token
from app.models.terms import Terms


@pytest.fixture(autouse=True)
async def seed_terms(db_session: AsyncSession):
    """테스트용 기본 약관 시드 데이터 적재"""
    terms = [
        Terms(
            code="TERMS_OF_SERVICE",
            name="서비스 이용약관",
            content="이용약관 본문",
            is_required=True,
        ),
        Terms(
            code="PRIVACY",
            name="개인정보 처리방침",
            content="개인정보 본문",
            is_required=True,
        ),
    ]
    db_session.add_all(terms)
    await db_session.commit()


@pytest.mark.asyncio
async def test_login_rate_limit_by_email(client: AsyncClient):
    """로그인 동일 이메일 5회 초과 시 429 및 Retry-After 헤더 반환 검증"""
    auth_rate_limiter.clear()

    # 1. 서로 다른 IP에서 동일 이메일로 5회 로그인 시도 (모두 404/401 등 일반 응답)
    for i in range(5):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "victim@example.com", "password": "wrongpassword123!"},
            headers={"X-Forwarded-For": f"198.51.100.{i + 1}"},
        )
        assert resp.status_code != 429

    # 2. 6번째 요청: 동일 이메일이므로 IP가 달라도 429 차단
    resp_blocked = await client.post(
        "/api/v1/auth/login",
        json={"email": "victim@example.com", "password": "wrongpassword123!"},
        headers={"X-Forwarded-For": "198.51.100.99"},
    )
    assert resp_blocked.status_code == 429
    body = resp_blocked.json()
    assert body["code"] == "RATE_LIMIT_EXCEEDED"
    assert "Retry-After" in resp_blocked.headers
    retry_after = int(resp_blocked.headers["Retry-After"])
    assert 1 <= retry_after <= 60

    # 429 에러 응답에도 보안 헤더가 누락 없이 주입되는지 검증
    assert resp_blocked.headers.get("x-content-type-options") == "nosniff"
    assert resp_blocked.headers.get("x-frame-options") == "DENY"


@pytest.mark.asyncio
async def test_login_rate_limit_by_ip(client: AsyncClient):
    """로그인 동일 IP에서 서로 다른 이메일로 10회 초과 시 429 차단 검증 (스프레이 공격 방어)"""
    auth_rate_limiter.clear()
    client_ip = "203.0.113.50"

    # 10회 서로 다른 이메일로 시도
    for i in range(10):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": f"target_{i}@example.com", "password": "wrongpassword123!"},
            headers={"X-Forwarded-For": client_ip},
        )
        assert resp.status_code != 429

    # 11번째 요청: 이메일이 새것이어도 동일 IP이므로 429 차단
    resp_blocked = await client.post(
        "/api/v1/auth/login",
        json={"email": "new_target@example.com", "password": "wrongpassword123!"},
        headers={"X-Forwarded-For": client_ip},
    )
    assert resp_blocked.status_code == 429
    assert resp_blocked.json()["code"] == "RATE_LIMIT_EXCEEDED"
    assert "Retry-After" in resp_blocked.headers


@pytest.mark.asyncio
async def test_login_email_normalization_defense(client: AsyncClient):
    """이메일 대소문자나 공백 변형(Stripe/Lower)으로 Rate Limit을 우회할 수 없도록 검증"""
    auth_rate_limiter.clear()

    # 혼합 케이스 및 공백 포함 요청 5회 발송
    variants = [
        "Victim@Example.Com",
        "  victim@example.com",
        "VICTIM@EXAMPLE.COM  ",
        "  Victim@Example.Com  ",
        "vIcTiM@eXaMpLe.cOm",
    ]

    for email_var in variants:
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": email_var, "password": "pwd"},
            headers={"X-Forwarded-For": f"198.51.100.{len(email_var)}"},
        )
        assert resp.status_code != 429

    # 6번째 변형 시도: 동일 정규화 이메일로 429 차단
    resp_blocked = await client.post(
        "/api/v1/auth/login",
        json={"email": "VICTIM@example.com", "password": "pwd"},
        headers={"X-Forwarded-For": "198.51.100.200"},
    )
    assert resp_blocked.status_code == 429
    assert resp_blocked.json()["code"] == "RATE_LIMIT_EXCEEDED"


@pytest.mark.asyncio
async def test_rate_limit_isolation_between_different_entities(client: AsyncClient):
    """IP A 차단이 IP B에 영향을 주지 않고, 이메일 A 차단이 이메일 B에 영향을 주지 않음을 검증"""
    auth_rate_limiter.clear()

    # userA 5회 소진으로 차단 유도
    for _ in range(5):
        await client.post(
            "/api/v1/auth/login",
            json={"email": "userA@example.com", "password": "pwd"},
            headers={"X-Forwarded-For": "198.51.100.1"},
        )

    # userA는 차단됨
    resp_user_a = await client.post(
        "/api/v1/auth/login",
        json={"email": "userA@example.com", "password": "pwd"},
        headers={"X-Forwarded-For": "198.51.100.2"},
    )
    assert resp_user_a.status_code == 429

    # userB는 다른 IP(198.51.100.2)에서 정상 접근 가능 (429 아님)
    resp_user_b = await client.post(
        "/api/v1/auth/login",
        json={"email": "userB@example.com", "password": "pwd"},
        headers={"X-Forwarded-For": "198.51.100.2"},
    )
    assert resp_user_b.status_code != 429


@pytest.mark.asyncio
async def test_password_change_rate_limits(client: AsyncClient):
    """비밀번호 변경 엔드포인트 IP 5회 및 회원 5회 제한 검증"""
    auth_rate_limiter.clear()

    # 1. 회원가입 및 토큰 발급
    signup_resp = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": "pwd_limiter@example.com",
            "password": "Password123!",
            "nickname": "비번제한테스터",
            "agreeTerms": True,
            "agreePrivacy": True,
        },
    )
    assert signup_resp.status_code == 201
    member_data = signup_resp.json()
    token = create_access_token(
        UUID(member_data["memberId"]), member_data["email"], member_data["nickname"]
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Forwarded-For": "203.0.113.111",
    }

    # 5회 비밀번호 변경 시도 (현재 비밀번호 불일치로 401 발생하더라도 Rate Limit 카운트)
    change_payload = {
        "currentPassword": "WrongCurrent123!",
        "newPassword": "NewPassword456@",
    }
    for _ in range(5):
        resp = await client.post(
            "/api/v1/auth/password/change",
            json=change_payload,
            headers=headers,
        )
        assert resp.status_code == 401

    # 6번째 시도: 429 차단
    resp_blocked = await client.post(
        "/api/v1/auth/password/change",
        json=change_payload,
        headers=headers,
    )
    assert resp_blocked.status_code == 429
    assert resp_blocked.json()["code"] == "RATE_LIMIT_EXCEEDED"
    assert "Retry-After" in resp_blocked.headers


@pytest.mark.asyncio
async def test_concurrent_rate_limiting(client: AsyncClient):
    """동시 요청(Concurrent requests) 환경에서 동시성 제어 및 원자적 카운팅 검증"""
    auth_rate_limiter.clear()

    # 15개의 동시 로그인 요청을 비동기 병렬 전송
    async def make_request(i: int):
        return await client.post(
            "/api/v1/auth/login",
            json={"email": f"concur_{i}@example.com", "password": "pwd"},
            headers={"X-Forwarded-For": "198.51.100.77"},
        )

    responses = await asyncio.gather(*(make_request(i) for i in range(15)))

    # IP당 제한이 10회이므로, 10개는 일반 응답(404 등), 5개는 반드시 429 Too Many Requests여야 함
    blocked_count = sum(1 for r in responses if r.status_code == 429)
    passed_count = sum(1 for r in responses if r.status_code != 429)

    assert passed_count == 10
    assert blocked_count == 5
