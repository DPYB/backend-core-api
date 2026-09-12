import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_auth_missing_token():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/library/shelves")
        assert resp.status_code == 401
        data = resp.json()
        assert data["code"] == "UNAUTHORIZED"
        assert "message" in data


@pytest.mark.asyncio
async def test_auth_invalid_token():
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": "Bearer invalid_garbage_token"},
    ) as client:
        resp = await client.get("/api/v1/library/shelves")
        assert resp.status_code == 401
        data = resp.json()
        assert data["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_not_found_errors(client: AsyncClient):
    # 존재하지 않는 책장
    resp1 = await client.get("/api/v1/library/shelves/999999/books")
    assert resp1.status_code == 404
    assert resp1.json()["code"] == "SHELF_NOT_FOUND"

    # 존재하지 않는 도서
    resp2 = await client.get("/api/v1/library/books/999999")
    assert resp2.status_code == 404
    assert resp2.json()["code"] == "LIBRARY_BOOK_NOT_FOUND"

    # 존재하지 않는 스크랩
    resp3 = await client.get("/api/v1/library/scraps/999999")
    assert resp3.status_code == 404
    assert resp3.json()["code"] == "SCRAP_NOT_FOUND"

    # 존재하지 않는 사서 개명
    resp4 = await client.patch("/api/v1/librarians/999999", json={"name": "이름"})
    assert resp4.status_code == 404
    assert resp4.json()["code"] == "LIBRARIAN_NOT_FOUND"


@pytest.mark.asyncio
async def test_validation_errors(client: AsyncClient):
    # 빈 책장 이름 -> 400 INVALID_SHELF_DATA
    resp1 = await client.post("/api/v1/library/shelves", json={"name": ""})
    assert resp1.status_code == 400
    assert resp1.json()["code"] == "INVALID_SHELF_DATA"

    # 스크랩 공백 문장 -> 400 INVALID_SCRAP_DATA
    # 먼저 책 1권 생성
    book_id = (
        await client.post(
            "/api/v1/library/books",
            json={"title": "테스트", "author": "저자"},
        )
    ).json()["bookId"]

    resp2 = await client.post(
        f"/api/v1/library/books/{book_id}/scraps",
        json={"sentence": "   ", "scrapImageUrl": "https://example.com/a.jpg"},
    )
    assert resp2.status_code == 400
    assert resp2.json()["code"] == "INVALID_SCRAP_DATA"
