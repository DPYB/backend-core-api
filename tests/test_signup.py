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


@pytest.fixture(autouse=True)
def mock_send_email():
    from unittest.mock import AsyncMock, patch

    with patch(
        "app.services.email_service.EmailService.send_verification_email",
        new_callable=AsyncMock,
    ) as m:
        yield m


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
    assert member.status == "PENDING_VERIFICATION"
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
    """실제 이메일 인증 코드 발급, 미인증 로그인 차단, 확인 및 활성화 플로우 검증"""
    from app.models.member import EmailVerification

    # 1. 회원가입 먼저 진행
    signup_payload = {
        "email": "verify_test@example.com",
        "password": "Password123!",
        "agreeTerms": True,
        "agreePrivacy": True,
    }
    signup_resp = await client.post("/api/v1/auth/signup", json=signup_payload)
    assert signup_resp.status_code == 201

    # 2. DB에서 발급된 6자리 인증 코드 확인
    v_stmt = select(EmailVerification).where(
        EmailVerification.email == "verify_test@example.com"
    )
    v_record = (await db_session.execute(v_stmt)).scalars().first()
    assert v_record is not None
    assert len(v_record.code) == 6
    assert v_record.is_verified is False

    # 3. 인증 전 로그인 시도 시 403 EMAIL_NOT_VERIFIED 차단 확인
    pre_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "verify_test@example.com", "password": "Password123!"},
    )
    assert pre_login.status_code == 403
    assert pre_login.json()["code"] == "EMAIL_NOT_VERIFIED"

    # 4. 잘못된 코드로 confirm 시 400 에러
    wrong_confirm = await client.post(
        "/api/v1/auth/signup/confirm",
        json={"email": "verify_test@example.com", "code": "999999"},
    )
    assert wrong_confirm.status_code == 400
    assert wrong_confirm.json()["code"] == "INVALID_VERIFICATION_CODE"

    # 5. 올바른 코드로 confirm 호출 -> 200 OK & ACTIVE 전이
    confirm_resp = await client.post(
        "/api/v1/auth/signup/confirm",
        json={"email": "verify_test@example.com", "code": v_record.code},
    )
    assert confirm_resp.status_code == 200
    assert confirm_resp.json()["status"] == "ACTIVE"

    # 6. 인증 완료 후 정상 로그인 성공 확인
    post_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "verify_test@example.com", "password": "Password123!"},
    )
    assert post_login.status_code == 200
    assert "accessToken" in post_login.json() or "access_token" in post_login.json()

    # 7. 이미 인증된 회원에게 resend 호출 시 안내 메시지 확인
    resend_resp = await client.post(
        "/api/v1/auth/signup/resend",
        json={"email": "verify_test@example.com"},
    )
    assert resend_resp.status_code == 200

    # 8. 없는 이메일 confirm 시 404
    not_found_resp = await client.post(
        "/api/v1/auth/signup/confirm",
        json={"email": "nonexistent@example.com", "code": "123456"},
    )
    assert not_found_resp.status_code == 404
