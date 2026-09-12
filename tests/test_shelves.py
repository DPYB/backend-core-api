import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_get_shelves_auto_create_default(client: AsyncClient):
    resp = await client.get("/api/v1/library/shelves")
    assert resp.status_code == 200
    data = resp.json()
    assert "shelves" in data
    assert len(data["shelves"]) == 1
    default_shelf = data["shelves"][0]
    assert default_shelf["name"] == "기본 책장"
    assert default_shelf["isDefault"] is True
    assert default_shelf["bookCount"] == 0


@pytest.mark.asyncio
async def test_create_shelf(client: AsyncClient):
    resp = await client.post("/api/v1/library/shelves", json={"name": "철학 도서"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "철학 도서"
    assert data["isDefault"] is False
    assert "shelfId" in data


@pytest.mark.asyncio
async def test_update_shelf_name(client: AsyncClient):
    # 1. 책장 생성
    create_resp = await client.post("/api/v1/library/shelves", json={"name": "철학"})
    shelf_id = create_resp.json()["shelfId"]

    # 2. 이름 변경
    resp = await client.patch(
        f"/api/v1/library/shelves/{shelf_id}", json={"name": "동양 철학"}
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "동양 철학"


@pytest.mark.asyncio
async def test_delete_default_shelf_forbidden(client: AsyncClient):
    # 기본 책장 조회하여 id 획득
    list_resp = await client.get("/api/v1/library/shelves")
    default_shelf_id = list_resp.json()["shelves"][0]["shelfId"]

    # 기본 책장 삭제 시도
    resp = await client.delete(f"/api/v1/library/shelves/{default_shelf_id}")
    assert resp.status_code == 400
    assert resp.json()["code"] == "DEFAULT_SHELF_CANNOT_BE_DELETED"


@pytest.mark.asyncio
async def test_delete_shelf_moves_books_to_default(
    client: AsyncClient, db_session: AsyncSession
):
    # 1. 기본 책장 및 보조 책장 생성
    list_resp = await client.get("/api/v1/library/shelves")
    default_shelf_id = list_resp.json()["shelves"][0]["shelfId"]

    create_resp = await client.post(
        "/api/v1/library/shelves", json={"name": "삭제할 책장"}
    )
    custom_shelf_id = create_resp.json()["shelfId"]

    # 2. 기본 책장에 도서 1권 등록
    await client.post(
        "/api/v1/library/books",
        json={"title": "기본 책장 책", "author": "저자1", "shelfId": default_shelf_id},
    )

    # 3. 보조 책장에 도서 2권 등록
    await client.post(
        "/api/v1/library/books",
        json={"title": "이동될 책 1", "author": "저자2", "shelfId": custom_shelf_id},
    )
    await client.post(
        "/api/v1/library/books",
        json={"title": "이동될 책 2", "author": "저자3", "shelfId": custom_shelf_id},
    )

    # 4. 보조 책장 삭제
    del_resp = await client.delete(f"/api/v1/library/shelves/{custom_shelf_id}")
    assert del_resp.status_code == 204

    # 5. 기본 책장 도서 목록 조회 -> 총 3권이 기본 책장에 있어야 함
    books_resp = await client.get(f"/api/v1/library/shelves/{default_shelf_id}/books")
    assert books_resp.status_code == 200
    items = books_resp.json()["items"]
    assert len(items) == 3
    assert items[0]["title"] == "기본 책장 책"
    assert items[1]["title"] == "이동될 책 1"
    assert items[2]["title"] == "이동될 책 2"
    # 순서 보장 (shelfRank ASC)
    assert items[0]["shelfRank"] < items[1]["shelfRank"] < items[2]["shelfRank"]


@pytest.mark.asyncio
async def test_shelf_access_denied(client: AsyncClient, other_client: AsyncClient):
    # client 회원이 책장 생성
    create_resp = await client.post(
        "/api/v1/library/shelves", json={"name": "비공개 책장"}
    )
    shelf_id = create_resp.json()["shelfId"]

    # other_client가 해당 책장 수정 시도
    patch_resp = await other_client.patch(
        f"/api/v1/library/shelves/{shelf_id}", json={"name": "해킹"}
    )
    assert patch_resp.status_code == 403
    assert patch_resp.json()["code"] == "SHELF_ACCESS_DENIED"
