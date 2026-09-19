import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_password
from app.models.librarian import Librarian
from app.models.member import Member
from app.models.shelf import Shelf
from app.models.terms import MemberAgreement, Terms


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
        Terms(
            code="AI_ANALYSIS",
            name="AI 분석 활용 동의",
            content="AI 분석 본문",
            is_required=False,
        ),
    ]
    db_session.add_all(terms)
    await db_session.commit()


@pytest.mark.asyncio
async def test_signup_success(client: AsyncClient, db_session: AsyncSession):
    """정상 회원가입 및 기본 책장/고양이 사서/약관동의 자동 생성 검증"""
    payload = {
        "email": "signup_user@example.com",
        "password": "Password123!",
        "nickname": "가입테스터",
        "birthDate": "1995-05-15",
        "gender": "MALE",
        "agreeTerms": True,
        "agreePrivacy": True,
        "agreeAiAnalysis": True,
    }

    resp = await client.post("/api/v1/auth/signup", json=payload)
    assert resp.status_code == 201
    data = resp.json()

    assert data["email"] == "signup_user@example.com"
    assert data["nickname"] == "가입테스터"
    assert "memberId" in data
    member_id = uuid.UUID(data["memberId"])

    # 1. DB 회원 레코드 검증
    stmt = select(Member).where(Member.member_id == member_id)
    member = (await db_session.execute(stmt)).scalars().first()
    assert member is not None
    assert member.email == "signup_user@example.com"
    assert member.gender == "MALE"
    assert str(member.birth_date) == "1995-05-15"
    assert member.password_hash is not None
    assert verify_password("Password123!", member.password_hash) is True

    # 2. 기본 책장(Default Shelf) 검증
    shelf_stmt = select(Shelf).where(
        Shelf.member_id == member_id, Shelf.is_default.is_(True)
    )
    shelf = (await db_session.execute(shelf_stmt)).scalars().first()
    assert shelf is not None
    assert shelf.is_default is True

    # 3. 기본 대표 사서(CAT "블루", Lv.1) 검증
    lib_stmt = select(Librarian).where(
        Librarian.member_id == member_id, Librarian.is_representative.is_(True)
    )
    lib = (await db_session.execute(lib_stmt)).scalars().first()
    assert lib is not None
    assert lib.name == "블루"
    assert lib.level == 1

    # 4. 약관 동의 이력 검증
    agree_stmt = select(MemberAgreement).where(MemberAgreement.member_id == member_id)
    agreements = (await db_session.execute(agree_stmt)).scalars().all()
    assert len(agreements) == 3


@pytest.mark.asyncio
async def test_signup_duplicate_email_conflict(
    client: AsyncClient, db_session: AsyncSession
):
    """이미 가입된 이메일로 가입 시도 시 409 Conflict 반환 검증"""
    member = Member(
        member_id=uuid.uuid4(),
        email="existing@example.com",
        nickname="기존회원",
        status="ACTIVE",
    )
    db_session.add(member)
    await db_session.commit()

    payload = {
        "email": "existing@example.com",
        "password": "Password123!",
        "agreeTerms": True,
        "agreePrivacy": True,
    }

    resp = await client.post("/api/v1/auth/signup", json=payload)
    assert resp.status_code == 409
    data = resp.json()
    assert data["code"] == "EMAIL_ALREADY_EXISTS"


@pytest.mark.asyncio
async def test_signup_missing_required_terms(client: AsyncClient):
    """필수 약관(이용약관 또는 개인정보) 미동의 시 400 Bad Request 반환 검증"""
    payload = {
        "email": "noterms@example.com",
        "password": "Password123!",
        "agreeTerms": False,
        "agreePrivacy": True,
    }

    resp = await client.post("/api/v1/auth/signup", json=payload)
    assert resp.status_code == 400
    data = resp.json()
    assert data["code"] == "TERMS_NOT_AGREED"


@pytest.mark.asyncio
async def test_signup_validation_errors(client: AsyncClient):
    """비밀번호 길이 미달 등 Pydantic 검증 오류 검증"""
    # 8자 미만 비밀번호
    payload = {
        "email": "invalid_pw@example.com",
        "password": "short",
        "agreeTerms": True,
        "agreePrivacy": True,
    }
    resp = await client.post("/api/v1/auth/signup", json=payload)
    assert resp.status_code in (400, 422)


@pytest.mark.asyncio
async def test_confirm_signup_and_resend(client: AsyncClient, db_session: AsyncSession):
    """프론트엔드 EmailVerification 호환 confirm 및 resend 엔드포인트 검증"""
    # 1. 회원가입 먼저 진행
    signup_payload = {
        "email": "verify_test@example.com",
        "password": "Password123!",
        "agreeTerms": True,
        "agreePrivacy": True,
    }
    signup_resp = await client.post("/api/v1/auth/signup", json=signup_payload)
    assert signup_resp.status_code == 201

    # 2. confirm 호출
    confirm_resp = await client.post(
        "/api/v1/auth/signup/confirm",
        json={"email": "verify_test@example.com", "code": "123456"},
    )
    assert confirm_resp.status_code == 200
    confirm_data = confirm_resp.json()
    assert confirm_data["status"] == "ACTIVE"

    # 3. resend 호출
    resend_resp = await client.post(
        "/api/v1/auth/signup/resend",
        json={"email": "verify_test@example.com"},
    )
    assert resend_resp.status_code == 200

    # 4. 없는 이메일 confirm 시 404
    not_found_resp = await client.post(
        "/api/v1/auth/signup/confirm",
        json={"email": "nonexistent@example.com", "code": "123456"},
    )
    assert not_found_resp.status_code == 404
