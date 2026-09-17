import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_get_and_delete_records(client: AsyncClient):
    member_id = uuid.uuid4()
    headers = {"X-Member-Id": str(member_id)}

    payload = {
        "book_id": 101,
        "title": "클린 코드 독서 기록",
        "content": "이 책을 읽고 코드 작성 태도가 완전히 바뀌었습니다.",
        "rating": 5,
        "read_at": "2026-03-30T10:00:00Z",
        "scraps": [
            {
                "sentence": "보이스카우트 규칙: 언제나 처음 왔을 때보다 깨끗하게 해놓고 떠나라.",
                "page_number": 42,
                "memo": "마음에 와닿는 구절",
                "scrap_image_url": "https://example.com/scraps/1.jpg",
            }
        ],
    }

    with patch(
        "app.services.record_service.RecordService.trigger_ai_vectorization",
        new=AsyncMock(),
    ) as mock_trigger:
        # 1. 독서 기록 생성 (POST)
        response = await client.post("/api/v1/records", json=payload, headers=headers)
        assert response.status_code == 201
        data = response.json()
        assert data["member_id"] == str(member_id)
        assert data["title"] == "클린 코드 독서 기록"
        assert len(data["scraps"]) == 1
        assert data["scraps"][0]["sentence"].startswith("보이스카우트")
        assert (
            data["scraps"][0]["scrap_image_url"] == "https://example.com/scraps/1.jpg"
        )

        mock_trigger.assert_awaited_once()

    record_id = data["id"]

    # 2. 독서 기록 목록 조회 (GET)
    list_res = await client.get("/api/v1/records", headers=headers)
    assert list_res.status_code == 200
    records = list_res.json()
    assert records[0]["id"] == record_id
    assert records[0]["title"] == "클린 코드 독서 기록"
    assert len(records[0]["scraps"]) == 1

    # 3. 독서 기록 단건 상세 조회 (GET /{record_id})
    detail_res = await client.get(f"/api/v1/records/{record_id}", headers=headers)
    assert detail_res.status_code == 200
    detail_data = detail_res.json()
    assert detail_data["id"] == record_id
    assert detail_data["member_id"] == str(member_id)
    assert len(detail_data["scraps"]) == 1

    # 4. 독서 기록 소프트 삭제 (DELETE /{record_id})
    del_res = await client.delete(f"/api/v1/records/{record_id}", headers=headers)
    assert del_res.status_code == 204

    # 5. 소프트 삭제 후 단건 조회 시 404 반환 검증
    get_after_del = await client.get(f"/api/v1/records/{record_id}", headers=headers)
    assert get_after_del.status_code == 404

    # 6. 소프트 삭제 후 목록 조회 시 제외 검증
    list_after_del = await client.get("/api/v1/records", headers=headers)
    assert list_after_del.status_code == 200
    assert not any(r["id"] == record_id for r in list_after_del.json())

    # 7. 이미 삭제된 레코드 재삭제 시 404 반환
    del_again = await client.delete(f"/api/v1/records/{record_id}", headers=headers)
    assert del_again.status_code == 404


@pytest.mark.asyncio
async def test_create_record_without_member_id(client: AsyncClient):
    """AUTH_DISABLED 테스트 환경에서는 X-Member-Id 없이도 DEFAULT_TEST_MEMBER_ID로 자동 인증되어 201 반환."""
    payload = {
        "book_id": 101,
        "title": "테스트",
        "content": "내용",
    }
    response = await client.post("/api/v1/records", json=payload)
    # AUTH_DISABLED=True 테스트 환경에서는 Bearer JWT / X-Member-Id 없이도
    # DEFAULT_TEST_MEMBER_ID로 자동 인증 처리 → 201 Created
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_member_isolation(client: AsyncClient):
    """A 회원의 레코드를 B 회원이 조회하거나 삭제할 수 없음을 검증."""
    member_a = uuid.uuid4()
    member_b = uuid.uuid4()

    payload = {
        "book_id": 202,
        "title": "A회원의 비밀 독서록",
        "content": "A회원만 볼 수 있는 감상문",
    }

    # A회원으로 레코드 생성
    create_res = await client.post(
        "/api/v1/records", json=payload, headers={"X-Member-Id": str(member_a)}
    )
    assert create_res.status_code == 201
    record_id = create_res.json()["id"]

    # B회원이 A회원의 record_id 단건 조회 시 404
    get_res = await client.get(
        f"/api/v1/records/{record_id}", headers={"X-Member-Id": str(member_b)}
    )
    assert get_res.status_code == 404

    # B회원의 목록 조회 시 A회원 레코드 미포함
    list_res = await client.get(
        "/api/v1/records", headers={"X-Member-Id": str(member_b)}
    )
    assert list_res.status_code == 200
    assert not any(r["id"] == record_id for r in list_res.json())

    # B회원이 A회원의 record_id 삭제 시도 시 404
    del_res = await client.delete(
        f"/api/v1/records/{record_id}", headers={"X-Member-Id": str(member_b)}
    )
    assert del_res.status_code == 404
