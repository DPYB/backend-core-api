import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_librarian_types_catalog(client: AsyncClient):
    resp = await client.get("/api/v1/librarian-types")
    assert resp.status_code == 200
    types = resp.json()["types"]
    assert len(types) == 4
    type_names = [t["type"] for t in types]
    assert "CAT" in type_names
    assert "SHOEBILL" in type_names
    assert "SEA_SLUG" in type_names
    assert "GECKO" in type_names


@pytest.mark.asyncio
async def test_acquire_librarian_and_duplicate_conflict(client: AsyncClient):
    # 1. 고양이 사서 획득
    req = {"type": "CAT", "name": "파란이"}
    resp1 = await client.post("/api/v1/librarians", json=req)
    assert resp1.status_code == 201
    data1 = resp1.json()
    assert data1["name"] == "파란이"
    assert data1["type"] == "CAT"
    assert data1["level"] == 1
    assert data1["experience"] == 0
    assert data1["isRepresentative"] is False

    # 2. 동일 타입 중복 획득 시도 -> 409
    resp2 = await client.post(
        "/api/v1/librarians", json={"type": "CAT", "name": "파란이2"}
    )
    assert resp2.status_code == 409
    assert resp2.json()["code"] == "LIBRARIAN_ALREADY_OWNED"


@pytest.mark.asyncio
async def test_representative_librarian_lifecycle(client: AsyncClient):
    # 1. 대표 사서가 없는 상태에서 조회 -> 404
    rep_resp = await client.get("/api/v1/librarians/representative")
    assert rep_resp.status_code == 404
    assert rep_resp.json()["code"] == "REPRESENTATIVE_LIBRARIAN_NOT_SELECTED"

    # 2. 사서 2마리 획득
    cat_id = (
        await client.post("/api/v1/librarians", json={"type": "CAT", "name": "냥이"})
    ).json()["librarianId"]
    bird_id = (
        await client.post(
            "/api/v1/librarians", json={"type": "SHOEBILL", "name": "슈빌이"}
        )
    ).json()["librarianId"]

    # 3. 고양이를 대표 사서로 지정
    set_rep_resp = await client.patch(f"/api/v1/librarians/{cat_id}/representative")
    assert set_rep_resp.status_code == 200
    assert set_rep_resp.json()["librarianId"] == cat_id
    assert set_rep_resp.json()["isRepresentative"] is True

    # 4. 대표 사서 조회
    curr_rep = await client.get("/api/v1/librarians/representative")
    assert curr_rep.status_code == 200
    assert curr_rep.json()["librarianId"] == cat_id

    # 5. 슈빌을 대표 사서로 변경
    set_bird_rep = await client.patch(f"/api/v1/librarians/{bird_id}/representative")
    assert set_bird_rep.status_code == 200

    # 6. 내 사서 목록 조회 -> 슈빌만 대표이고 고양이는 해제되었는지 확인
    my_libs = (await client.get("/api/v1/librarians")).json()
    cat_item = next(item for item in my_libs if item["librarianId"] == cat_id)
    bird_item = next(item for item in my_libs if item["librarianId"] == bird_id)
    assert cat_item["isRepresentative"] is False
    assert bird_item["isRepresentative"] is True


@pytest.mark.asyncio
async def test_rename_and_dismiss_librarian(client: AsyncClient):
    lib_id = (
        await client.post(
            "/api/v1/librarians", json={"type": "GECKO", "name": "초기이름"}
        )
    ).json()["librarianId"]

    # 개명
    rename_resp = await client.patch(
        f"/api/v1/librarians/{lib_id}", json={"name": "새이름"}
    )
    assert rename_resp.status_code == 200
    assert rename_resp.json()["name"] == "새이름"

    # 방출 (삭제)
    del_resp = await client.delete(f"/api/v1/librarians/{lib_id}")
    assert del_resp.status_code == 204

    # 내 사서 목록에서 제외되었는지 확인
    my_libs = (await client.get("/api/v1/librarians")).json()
    assert not any(item["librarianId"] == lib_id for item in my_libs)
