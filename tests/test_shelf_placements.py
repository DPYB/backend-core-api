import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_db
from app.main import app


@pytest.mark.asyncio
async def test_update_shelf_placements_success(client: AsyncClient):
    # 1. 도서 3권 등록
    b1_res = await client.post(
        "/api/v1/library/books",
        json={"title": "책 1", "author": "저자 1", "totalPages": 100},
    )
    assert b1_res.status_code == 201
    b1_id = b1_res.json()["bookId"]

    b2_res = await client.post(
        "/api/v1/library/books",
        json={"title": "책 2", "author": "저자 2", "totalPages": 150},
    )
    assert b2_res.status_code == 201
    b2_id = b2_res.json()["bookId"]

    b3_res = await client.post(
        "/api/v1/library/books",
        json={"title": "책 3", "author": "저자 3", "totalPages": 200},
    )
    assert b3_res.status_code == 201
    b3_id = b3_res.json()["bookId"]

    # 2. 선반 배치 일괄 업데이트: 0단에 [b2, b1], 1단에 [b3]
    placement_payload = {
        "librarianType": "CAT",
        "assignments": {
            "0": [b2_id, b1_id],
            "1": [b3_id],
        },
    }
    update_res = await client.put(
        "/api/v1/library/books/shelf-placements",
        json=placement_payload,
    )
    assert update_res.status_code == 200
    res_data = update_res.json()
    assert res_data["status"] == "success"
    # b2 (tier 0, order 0), b1 (tier 0, order 1), b3 (tier 1, order 0)
    assert res_data["updatedCount"] >= 2

    # 3. 목록 조회 시 각 도서의 shelfTier, shelfOrder 반환 검증
    list_res = await client.get("/api/v1/library/books")
    assert list_res.status_code == 200
    books = {b["bookId"]: b for b in list_res.json()["items"]}

    assert books[b2_id]["shelfTier"] == 0
    assert books[b2_id]["shelfOrder"] == 0

    assert books[b1_id]["shelfTier"] == 0
    assert books[b1_id]["shelfOrder"] == 1

    assert books[b3_id]["shelfTier"] == 1
    assert books[b3_id]["shelfOrder"] == 0

    # 4. 단건 조회 시 shelfTier, shelfOrder 반환 검증
    detail_res = await client.get(f"/api/v1/library/books/{b1_id}")
    assert detail_res.status_code == 200
    assert detail_res.json()["shelfTier"] == 0
    assert detail_res.json()["shelfOrder"] == 1


@pytest.mark.asyncio
async def test_list_books_sort_by_shelf_placement(client: AsyncClient):
    # 3권 등록 후 0단 [b2, b1], 1단 [b3] 배치
    b1_id = (
        await client.post(
            "/api/v1/library/books",
            json={"title": "책 1", "author": "저자 1"},
        )
    ).json()["bookId"]
    b2_id = (
        await client.post(
            "/api/v1/library/books",
            json={"title": "책 2", "author": "저자 2"},
        )
    ).json()["bookId"]
    b3_id = (
        await client.post(
            "/api/v1/library/books",
            json={"title": "책 3", "author": "저자 3"},
        )
    ).json()["bookId"]

    await client.put(
        "/api/v1/library/books/shelf-placements",
        json={
            "assignments": {
                "0": [b2_id, b1_id],
                "1": [b3_id],
            }
        },
    )

    # sortBy=SHELF_PLACEMENT ASC 정렬 시: b2 (0단 0번) -> b1 (0단 1번) -> b3 (1단 0번)
    asc_res = await client.get(
        "/api/v1/library/books?sortBy=SHELF_PLACEMENT&sortOrder=ASC"
    )
    assert asc_res.status_code == 200
    asc_ids = [b["bookId"] for b in asc_res.json()["items"]]
    assert asc_ids == [b2_id, b1_id, b3_id]

    # sortBy=SHELF_PLACEMENT DESC 정렬 시: b3 -> b1 -> b2
    desc_res = await client.get(
        "/api/v1/library/books?sortBy=SHELF_PLACEMENT&sortOrder=DESC"
    )
    assert desc_res.status_code == 200
    desc_ids = [b["bookId"] for b in desc_res.json()["items"]]
    assert desc_ids == [b3_id, b1_id, b2_id]


@pytest.mark.asyncio
async def test_update_shelf_placements_empty_assignments(client: AsyncClient):
    res = await client.put(
        "/api/v1/library/books/shelf-placements",
        json={"assignments": {}},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "success"
    assert res.json()["updatedCount"] == 0


@pytest.mark.asyncio
async def test_update_shelf_placements_duplicate_book_id(client: AsyncClient):
    b1_id = (
        await client.post(
            "/api/v1/library/books",
            json={"title": "책 1", "author": "저자 1"},
        )
    ).json()["bookId"]

    # 동일 도서 ID가 여러 선반에 중복 포함된 경우 400 거부
    res = await client.put(
        "/api/v1/library/books/shelf-placements",
        json={
            "assignments": {
                "0": [b1_id],
                "1": [b1_id],
            }
        },
    )
    assert res.status_code == 400
    assert res.json()["code"] == "INVALID_REORDER_TARGET"


@pytest.mark.asyncio
async def test_update_shelf_placements_nonexistent_book(client: AsyncClient):
    res = await client.put(
        "/api/v1/library/books/shelf-placements",
        json={"assignments": {"0": [999999]}},
    )
    assert res.status_code == 404
    assert res.json()["code"] == "LIBRARY_BOOK_NOT_FOUND"


@pytest.mark.asyncio
async def test_update_shelf_placements_forbidden_other_member_book(
    client: AsyncClient, other_client: AsyncClient
):
    # other_client가 도서 등록
    other_book_id = (
        await other_client.post(
            "/api/v1/library/books",
            json={"title": "타인 책", "author": "타인 저자"},
        )
    ).json()["bookId"]

    # 내 client가 타인의 도서 ID를 포함하여 업데이트 시도
    res = await client.put(
        "/api/v1/library/books/shelf-placements",
        json={"assignments": {"0": [other_book_id]}},
    )
    assert res.status_code == 403
    assert res.json()["code"] == "LIBRARY_BOOK_ACCESS_DENIED"


@pytest.mark.asyncio
async def test_update_shelf_placements_invalid_tier_keys(client: AsyncClient):
    b1_id = (
        await client.post(
            "/api/v1/library/books",
            json={"title": "책 1", "author": "저자 1"},
        )
    ).json()["bookId"]

    # 음수 선반 번호
    neg_res = await client.put(
        "/api/v1/library/books/shelf-placements",
        json={"assignments": {"-1": [b1_id]}},
    )
    assert neg_res.status_code == 400
    assert "code" in neg_res.json()

    # 숫자가 아닌 문자열 선반 번호
    invalid_str_res = await client.put(
        "/api/v1/library/books/shelf-placements",
        json={"assignments": {"abc": [b1_id]}},
    )
    assert invalid_str_res.status_code == 400
    assert "code" in invalid_str_res.json()


@pytest.mark.asyncio
async def test_demo_account_allowed_shelf_placements(db_session: AsyncSession):
    """데모 계정 토큰으로 선반 배치 동기화 요청 시 Allowlist를 통과하는지 검증"""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer mock-token-{settings.DEMO_MEMBER_ID}"},
    ) as demo_client:
        # 데모 계정으로 도서 등록
        b_res = await demo_client.post(
            "/api/v1/library/books",
            json={"title": "데모 책", "author": "데모 저자"},
        )
        assert b_res.status_code == 201
        book_id = b_res.json()["bookId"]

        # 데모 계정으로 선반 배치 일괄 업데이트
        placement_res = await demo_client.put(
            "/api/v1/library/books/shelf-placements",
            json={"assignments": {"0": [book_id]}},
        )
        assert placement_res.status_code == 200
        assert placement_res.json()["status"] == "success"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_and_update_book_response_contains_shelf_placement(
    client: AsyncClient,
):
    # 등록 시 shelfTier, shelfOrder 기본값 0 반환
    b_res = await client.post(
        "/api/v1/library/books",
        json={"title": "신규 책", "author": "저자"},
    )
    assert b_res.status_code == 201
    b_data = b_res.json()
    assert b_data["shelfTier"] == 0
    assert b_data["shelfOrder"] == 0
    book_id = b_data["bookId"]

    # 선반 배치 1단 2번으로 변경
    await client.put(
        "/api/v1/library/books/shelf-placements",
        json={"assignments": {"1": [999999, 888888, book_id] if False else [book_id]}},
    )

    # 도서 정보 수정 시에도 현재 shelfTier, shelfOrder 보존 반환
    u_res = await client.patch(
        f"/api/v1/library/books/{book_id}",
        json={"title": "수정된 책", "author": "저자", "readingStatus": "READING"},
    )
    assert u_res.status_code == 200
    u_data = u_res.json()
    assert u_data["shelfTier"] == 1
    assert u_data["shelfOrder"] == 0


@pytest.mark.asyncio
async def test_update_shelf_placements_string_and_int_coercion(client: AsyncClient):
    b1_id = (
        await client.post(
            "/api/v1/library/books",
            json={"title": "책 1", "author": "저자 1"},
        )
    ).json()["bookId"]
    b2_id = (
        await client.post(
            "/api/v1/library/books",
            json={"title": "책 2", "author": "저자 2"},
        )
    ).json()["bookId"]

    # 문자열 ID 배열 ['123'] 및 정수 선반 키 0 혼합 입력 유연 처리
    res = await client.put(
        "/api/v1/library/books/shelf-placements",
        json={"assignments": {0: [str(b1_id)], "1": [b2_id]}},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "success"

    detail_b1 = (await client.get(f"/api/v1/library/books/{b1_id}")).json()
    assert detail_b1["shelfTier"] == 0
    assert detail_b1["shelfOrder"] == 0

    detail_b2 = (await client.get(f"/api/v1/library/books/{b2_id}")).json()
    assert detail_b2["shelfTier"] == 1
    assert detail_b2["shelfOrder"] == 0
