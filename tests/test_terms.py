import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.member import Member
from app.models.terms import MemberAgreement, Terms


@pytest.mark.asyncio
async def test_terms_list_and_agreement(client: AsyncClient, db_session: AsyncSession):
    """약관 목록 조회 및 동의/철회 테스트"""
    # 1. 약관 2건 생성 (필수 1건, 선택 1건)
    term1 = Terms(
        code="TERMS_OF_SERVICE",
        name="서비스 이용약관",
        content="이용약관 내용입니다.",
        is_required=True,
        effective_at=datetime.now(UTC),
    )
    term2 = Terms(
        code="AI_ANALYSIS",
        name="AI 독서 분석 동의",
        content="AI 분석 내용입니다.",
        is_required=False,
        effective_at=datetime.now(UTC),
    )
    db_session.add_all([term1, term2])
    await db_session.commit()

    # 2. 약관 목록 조회 (GET /api/v1/terms)
    resp = await client.get("/api/v1/terms")
    assert resp.status_code == 200
    terms_list = resp.json()
    assert len(terms_list) >= 2
    codes = [t["code"] for t in terms_list]
    assert "TERMS_OF_SERVICE" in codes
    assert "AI_ANALYSIS" in codes

    # 3. 회원 생성 및 로그인 토큰 발급
    member_id = uuid.uuid4()
    member = Member(
        member_id=member_id,
        email="terms_user@test.com",
        nickname="약관테스터",
        status="ACTIVE",
    )
    db_session.add(member)
    await db_session.commit()

    token = create_access_token(member_id, member.email, member.nickname)
    headers = {"Authorization": f"Bearer {token}"}

    # 4. 약관 동의 등록 (POST /api/v1/terms/agreements)
    agree_resp = await client.post(
        "/api/v1/terms/agreements",
        headers=headers,
        json={"termsId": term2.id, "action": "AGREE"},
    )
    assert agree_resp.status_code == 200
    assert agree_resp.json()["success"] is True
    assert agree_resp.json()["action"] == "AGREE"

    # DB 확인
    stmt = select(MemberAgreement).where(
        MemberAgreement.member_id == member_id,
        MemberAgreement.terms_id == term2.id,
    )
    res = await db_session.execute(stmt)
    agreement = res.scalars().first()
    assert agreement is not None
    assert agreement.action == "AGREE"

    # 5. 필수 약관 철회 시도 시 400 에러 확인
    fail_resp = await client.post(
        "/api/v1/terms/agreements",
        headers=headers,
        json={"termsId": term1.id, "action": "WITHDRAW"},
    )
    assert fail_resp.status_code == 400
    assert fail_resp.json()["code"] == "CANNOT_WITHDRAW_REQUIRED_TERMS"
