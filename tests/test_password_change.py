import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, verify_password
from app.models.member import Member
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
async def test_change_password_success(client: AsyncClient, db_session: AsyncSession):
    """정상 비밀번호 변경 성공 검증"""
    # 1. 회원가입
    signup_payload = {
        "email": "pw_test@example.com",
        "password": "OldPassword123!",
        "nickname": "비번테스터",
        "agreeTerms": True,
        "agreePrivacy": True,
    }
    signup_resp = await client.post("/api/v1/auth/signup", json=signup_payload)
    assert signup_resp.status_code == 201
    member_data = signup_resp.json()

    # 2. 토큰 발급
    from uuid import UUID

    token = create_access_token(
        UUID(member_data["memberId"]), member_data["email"], member_data["nickname"]
    )
    headers = {"Authorization": f"Bearer {token}"}

    # 3. 비밀번호 변경 요청
    change_payload = {
        "currentPassword": "OldPassword123!",
        "newPassword": "NewPassword456@",
    }
    resp = await client.post(
        "/api/v1/auth/password/change", json=change_payload, headers=headers
    )
    assert resp.status_code == 200
    assert "성공적" in resp.json()["message"]

    # 4. DB에서 새 비밀번호 해시 검증
    member_stmt = select(Member).where(Member.email == "pw_test@example.com")
    member = (await db_session.execute(member_stmt)).scalars().first()
    assert member is not None
    assert verify_password("NewPassword456@", member.password_hash)
    assert not verify_password("OldPassword123!", member.password_hash)


@pytest.mark.asyncio
async def test_change_password_invalid_current_password(
    client: AsyncClient, db_session: AsyncSession
):
    """현재 비밀번호가 틀렸을 때 401 반환 검증"""
    signup_payload = {
        "email": "pw_wrong@example.com",
        "password": "CorrectPassword123!",
        "nickname": "오류테스터",
        "agreeTerms": True,
        "agreePrivacy": True,
    }
    signup_resp = await client.post("/api/v1/auth/signup", json=signup_payload)
    assert signup_resp.status_code == 201
    member_data = signup_resp.json()

    from uuid import UUID

    token = create_access_token(
        UUID(member_data["memberId"]), member_data["email"], member_data["nickname"]
    )
    headers = {"Authorization": f"Bearer {token}"}

    change_payload = {
        "currentPassword": "WrongPassword999!",
        "newPassword": "NewPassword456@",
    }
    resp = await client.post(
        "/api/v1/auth/password/change", json=change_payload, headers=headers
    )
    assert resp.status_code == 401
    data = resp.json()
    assert data["code"] == "INVALID_PASSWORD"


@pytest.mark.asyncio
async def test_change_password_same_as_current(
    client: AsyncClient, db_session: AsyncSession
):
    """현재 비밀번호와 동일한 새 비밀번호 요청 시 400 반환 검증"""
    signup_payload = {
        "email": "pw_same@example.com",
        "password": "SamePassword123!",
        "nickname": "동일비번테스터",
        "agreeTerms": True,
        "agreePrivacy": True,
    }
    signup_resp = await client.post("/api/v1/auth/signup", json=signup_payload)
    assert signup_resp.status_code == 201
    member_data = signup_resp.json()

    from uuid import UUID

    token = create_access_token(
        UUID(member_data["memberId"]), member_data["email"], member_data["nickname"]
    )
    headers = {"Authorization": f"Bearer {token}"}

    change_payload = {
        "currentPassword": "SamePassword123!",
        "newPassword": "SamePassword123!",
    }
    resp = await client.post(
        "/api/v1/auth/password/change", json=change_payload, headers=headers
    )
    assert resp.status_code == 400
    data = resp.json()
    assert data["code"] == "SAME_AS_CURRENT_PASSWORD"


@pytest.mark.asyncio
async def test_change_password_too_weak(client: AsyncClient, db_session: AsyncSession):
    """비밀번호 복잡도 미충족 시 400 반환 검증"""
    signup_payload = {
        "email": "pw_weak@example.com",
        "password": "ValidPassword123!",
        "nickname": "취약테스터",
        "agreeTerms": True,
        "agreePrivacy": True,
    }
    signup_resp = await client.post("/api/v1/auth/signup", json=signup_payload)
    assert signup_resp.status_code == 201
    member_data = signup_resp.json()

    from uuid import UUID

    token = create_access_token(
        UUID(member_data["memberId"]), member_data["email"], member_data["nickname"]
    )
    headers = {"Authorization": f"Bearer {token}"}

    # 단순 숫자 (8자 미만 및 영문/특수문자 없음) -> Pydantic min_length=8에 걸리거나 복잡도 regex에 걸림
    change_payload = {
        "currentPassword": "ValidPassword123!",
        "newPassword": "simplepassword",
    }
    resp = await client.post(
        "/api/v1/auth/password/change", json=change_payload, headers=headers
    )
    assert resp.status_code == 400
