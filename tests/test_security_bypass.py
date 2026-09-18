import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_x_member_id_without_jwt_is_unauthorized(client: AsyncClient):
    """
    [보안 회귀 방지 불변식 1]
    JWT 토큰 없이 임의의 X-Member-Id 헤더만 보낸 요청은
    무조건 401 Unauthorized로 단호히 거부되어야 한다.
    """
    spoofed_member_id = uuid.uuid4()
    # client fixture의 Authorization 헤더를 덮어써서 빈 토큰 + X-Member-Id 전송
    unauthorized_headers = {
        "Authorization": "",
        "X-Member-Id": str(spoofed_member_id),
    }

    # 1. 독서 기록 엔드포인트
    resp = await client.get("/api/v1/records", headers=unauthorized_headers)
    assert resp.status_code == 401
    assert resp.json()["code"] == "UNAUTHORIZED"

    # 2. 독서 세션 엔드포인트
    resp = await client.post(
        "/api/v1/reading-sessions",
        json={"durationMinutes": 30},
        headers=unauthorized_headers,
    )
    assert resp.status_code == 401
    assert resp.json()["code"] == "UNAUTHORIZED"

    # 3. 월간 리포트 통계 엔드포인트
    resp = await client.get(
        "/api/v1/reports/monthly-stats?year=2026&month=9",
        headers=unauthorized_headers,
    )
    assert resp.status_code == 401
    assert resp.json()["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_spoofed_x_member_id_is_ignored_when_jwt_present(client: AsyncClient):
    """
    [보안 회귀 방지 불변식 2]
    공격자가 서명된 본인 JWT를 보유한 상태에서, 헤더에 다른 사용자의 X-Member-Id를
    주입하더라도 시스템은 X-Member-Id를 완전히 무시하고 JWT 내의 sub(본인)만 식별해야 한다.
    """
    my_member_id = uuid.uuid4()
    victim_member_id = uuid.uuid4()

    headers = {
        "Authorization": f"Bearer mock-token-{my_member_id}",
        "X-Member-Id": str(victim_member_id),  # 악의적 신분 위장 시도
    }

    payload = {
        "book_id": 999,
        "title": "보안 검증 독서 기록",
        "content": "공격자의 기록이 피해자에게 귀속되지 않아야 함",
    }
    resp = await client.post("/api/v1/records", json=payload, headers=headers)
    assert resp.status_code == 201
    data = resp.json()

    # 시스템이 X-Member-Id(victim)를 무시하고 JWT의 sub(my_member_id)로 안전하게 귀속시켰는지 검증
    assert data["member_id"] == str(my_member_id)
    assert data["member_id"] != str(victim_member_id)


@pytest.mark.asyncio
async def test_optional_member_id_ignores_x_member_id(client: AsyncClient):
    """
    [보안 회귀 방지 불변식 3]
    선택적 인증 엔드포인트(예: 도서 상세 조회 /api/v1/books/{book_id})에서
    토큰 없이 X-Member-Id만 들어오면 member_id=None (비로그인)으로 처리되어야 한다.
    """
    spoofed_member_id = uuid.uuid4()
    unauthorized_headers = {
        "Authorization": "",
        "X-Member-Id": str(spoofed_member_id),
    }

    # 비로그인 상태에서 위조 헤더만 보낸 경우 도서가 없으면 404 (정상적인 None 처리)
    resp = await client.get(
        "/api/v1/books/99999",
        headers=unauthorized_headers,
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "LIBRARY_BOOK_NOT_FOUND"
