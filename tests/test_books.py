import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_create_book_success(client: AsyncClient):
    req = {
        "title": "클린 아키텍처",
        "author": "로버트 C. 마틴",
        "isbn": "9788966262472",
        "genre": "TECHNOLOGY",
        "kdc": "005.133",
        "subject": "컴퓨터 프로그래밍",
        "publisher": "인사이트",
        "readingStatus": "READING",
        "totalPages": 350,
        "currentPage": 35,
    }
    resp = await client.post("/api/v1/library/books", json=req)
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "클린 아키텍처"
    assert data["genre"] == "TECHNOLOGY"
    assert data["genreName"] == "기술과학"
    assert data["progress"] == 10.0
    assert "shelfRank" in data
    assert "shelfId" in data


@pytest.mark.asyncio
async def test_create_book_duplicate_isbn(client: AsyncClient):
    req = {
        "title": "클린 아키텍처",
        "author": "로버트 C. 마틴",
        "isbn": "9788966262472",
    }
    resp1 = await client.post("/api/v1/library/books", json=req)
    assert resp1.status_code == 201

    resp2 = await client.post("/api/v1/library/books", json=req)
    assert resp2.status_code == 409
    assert resp2.json()["code"] == "BOOK_ALREADY_REGISTERED"


@pytest.mark.asyncio
async def test_list_books_filtering_and_sorting(client: AsyncClient):
    # 책 3권 등록
    await client.post(
        "/api/v1/library/books",
        json={
            "title": "A Book",
            "author": "김작가",
            "readingStatus": "READING",
            "totalPages": 100,
            "currentPage": 50,
        },
    )
    await client.post(
        "/api/v1/library/books",
        json={
            "title": "B Book",
            "author": "이작가",
            "readingStatus": "COMPLETED",
            "totalPages": 200,
            "currentPage": 200,
        },
    )
    await client.post(
        "/api/v1/library/books",
        json={"title": "C Book", "author": "김작가", "readingStatus": "PLANNED"},
    )

    # author 필터
    resp = await client.get("/api/v1/library/books?author=김작가")
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 2

    # readingStatus 필터
    resp2 = await client.get("/api/v1/library/books?readingStatus=COMPLETED")
    assert resp2.status_code == 200
    assert len(resp2.json()["items"]) == 1
    assert resp2.json()["items"][0]["title"] == "B Book"

    # PROGRESS DESC 정렬
    resp3 = await client.get("/api/v1/library/books?sortBy=PROGRESS&sortOrder=DESC")
    assert resp3.status_code == 200
    items = resp3.json()["items"]
    assert items[0]["title"] == "B Book"  # 100%
    assert items[1]["title"] == "A Book"  # 50%


@pytest.mark.asyncio
async def test_update_book_full_payload(client: AsyncClient):
    create_resp = await client.post(
        "/api/v1/library/books",
        json={"title": "원제", "author": "원저자", "genre": "NONE"},
    )
    book_id = create_resp.json()["bookId"]

    # 11개 필드 전체 전송 (ADR-0006)
    update_req = {
        "title": "수정된 제목",
        "author": "수정된 저자",
        "isbn": "9781234567890",
        "genre": "LITERATURE",
        "kdc": "813.6",
        "subject": "한국소설",
        "publisher": "새출판사",
        "publishedDate": "2024-01-01",
        "coverUrl": "https://example.com/cover.jpg",
        "readingStatus": "COMPLETED",
        "totalPages": 300,
    }
    patch_resp = await client.patch(f"/api/v1/library/books/{book_id}", json=update_req)
    assert patch_resp.status_code == 200
    data = patch_resp.json()
    assert data["title"] == "수정된 제목"
    assert data["genreName"] == "문학"
    assert data["subject"] == "한국소설"
    assert data["publishedDate"] == "2024-01-01"


@pytest.mark.asyncio
async def test_reorder_book(client: AsyncClient):
    # 도서 3권 등록
    b1 = (
        await client.post(
            "/api/v1/library/books", json={"title": "1번 책", "author": "저자"}
        )
    ).json()["bookId"]
    b2 = (
        await client.post(
            "/api/v1/library/books", json={"title": "2번 책", "author": "저자"}
        )
    ).json()["bookId"]
    b3 = (
        await client.post(
            "/api/v1/library/books", json={"title": "3번 책", "author": "저자"}
        )
    ).json()["bookId"]

    # 3번 책을 1번 책 '앞'으로 이동
    reorder_resp = await client.patch(
        f"/api/v1/library/books/{b3}/order",
        json={"beforeBookId": b1},
    )
    assert reorder_resp.status_code == 200

    # 목록 조회 시 순서가 3번, 1번, 2번이어야 함
    list_resp = await client.get(
        "/api/v1/library/books?sortBy=SHELF_ORDER&sortOrder=ASC"
    )
    items = list_resp.json()["items"]
    assert [x["bookId"] for x in items] == [b3, b1, b2]


@pytest.mark.asyncio
async def test_move_book_shelf(client: AsyncClient):
    # 책장 2 생성
    s2 = (
        await client.post("/api/v1/library/shelves", json={"name": "새 책장"})
    ).json()["shelfId"]
    # 도서 생성
    b1 = (
        await client.post(
            "/api/v1/library/books", json={"title": "이동할 책", "author": "저자"}
        )
    ).json()["bookId"]

    # 책장 이동
    move_resp = await client.patch(
        f"/api/v1/library/books/{b1}/shelf",
        json={"targetShelfId": s2},
    )
    assert move_resp.status_code == 200
    assert move_resp.json()["shelfId"] == s2


@pytest.mark.asyncio
async def test_update_progress_and_validation(client: AsyncClient):
    b1 = (
        await client.post(
            "/api/v1/library/books",
            json={"title": "진도책", "author": "저자", "totalPages": 100},
        )
    ).json()["bookId"]

    # 정상 진도
    p_resp = await client.patch(
        f"/api/v1/library/books/{b1}/progress",
        json={"currentPage": 60},
    )
    assert p_resp.status_code == 200
    assert p_resp.json()["progress"] == 60.0

    # 초과 진도 -> 400
    err_resp = await client.patch(
        f"/api/v1/library/books/{b1}/progress",
        json={"currentPage": 150},
    )
    assert err_resp.status_code == 400
    assert err_resp.json()["code"] == "INVALID_PAGE_VALUE"


@pytest.mark.asyncio
async def test_delete_book_cascades_scraps(
    client: AsyncClient, db_session: AsyncSession
):
    # 도서 등록
    b1 = (
        await client.post(
            "/api/v1/library/books", json={"title": "삭제될 책", "author": "저자"}
        )
    ).json()["bookId"]

    # 스크랩 등록
    scrap_resp = await client.post(
        f"/api/v1/library/books/{b1}/scraps",
        json={
            "sentence": "좋은 문장입니다.",
            "pageNumber": 10,
            "scrapImageUrl": "https://example.com/scrap.jpg",
        },
    )
    assert scrap_resp.status_code == 201
    scrap_id = scrap_resp.json()["scrapId"]

    # 도서 삭제
    del_resp = await client.delete(f"/api/v1/library/books/{b1}")
    assert del_resp.status_code == 204

    # 도서 조회 시 404
    get_b_resp = await client.get(f"/api/v1/library/books/{b1}")
    assert get_b_resp.status_code == 404

    # 스크랩 조회 시 404 (캐스케이드 소프트 삭제 확인)
    get_s_resp = await client.get(f"/api/v1/library/scraps/{scrap_id}")
    assert get_s_resp.status_code == 404
