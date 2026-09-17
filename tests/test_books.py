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
    assert data["genreName"] == "컴퓨터 프로그래밍"  # Subject 1순위 노출
    assert data["displayGenre"] == "컴퓨터 프로그래밍"
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


@pytest.mark.asyncio
async def test_update_progress_auto_completes_when_reaching_total_pages(
    client: AsyncClient,
):
    # 1. totalPages 100인 도서 등록 (기본 PLANNED)
    book_id = (
        await client.post(
            "/api/v1/library/books",
            json={"title": "완독 테스트 도서", "author": "테스터", "totalPages": 100},
        )
    ).json()["bookId"]

    # 2. current_page == total_pages (100) 도달
    resp = await client.patch(
        f"/api/v1/library/books/{book_id}/progress",
        json={"currentPage": 100},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["currentPage"] == 100
    assert data["progress"] == 100.0
    assert data["readingStatus"] == "COMPLETED"
    assert data["completedAt"] is not None

    # 3. 단건 조회에서도 완독 상태와 completedAt 유지 확인
    detail_resp = await client.get(f"/api/v1/library/books/{book_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["readingStatus"] == "COMPLETED"
    assert detail["completedAt"] is not None


@pytest.mark.asyncio
async def test_update_progress_reverts_to_reading_when_page_decreased(
    client: AsyncClient,
):
    # 1. 완독 상태인 도서 생성
    book_id = (
        await client.post(
            "/api/v1/library/books",
            json={"title": "되돌리기 도서", "author": "테스터", "totalPages": 100},
        )
    ).json()["bookId"]
    await client.patch(
        f"/api/v1/library/books/{book_id}/progress",
        json={"currentPage": 100},
    )

    # 2. 페이지를 50으로 감소 -> READING 상태로 자동 복귀 및 completedAt 리셋
    revert_resp = await client.patch(
        f"/api/v1/library/books/{book_id}/progress",
        json={"currentPage": 50},
    )
    assert revert_resp.status_code == 200
    data = revert_resp.json()
    assert data["currentPage"] == 50
    assert data["progress"] == 50.0
    assert data["readingStatus"] == "READING"
    assert data["completedAt"] is None

    # 3. 단건 조회에서도 리셋 확인
    detail = (await client.get(f"/api/v1/library/books/{book_id}")).json()
    assert detail["readingStatus"] == "READING"
    assert detail["completedAt"] is None


@pytest.mark.asyncio
async def test_update_progress_transitions_planned_to_reading(client: AsyncClient):
    # 1. PLANNED 도서 생성 (currentPage 0)
    book_id = (
        await client.post(
            "/api/v1/library/books",
            json={"title": "읽기 시작 도서", "author": "테스터", "totalPages": 200},
        )
    ).json()["bookId"]

    # 2. 10페이지 입력 시 PLANNED -> READING 자동 전이
    resp = await client.patch(
        f"/api/v1/library/books/{book_id}/progress",
        json={"currentPage": 10},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["readingStatus"] == "READING"
    assert data["completedAt"] is None


@pytest.mark.asyncio
async def test_update_book_metadata_auto_sync_status_and_completed_at(
    client: AsyncClient,
):
    # 1. totalPages: 200, currentPage: 150 도서 생성
    create_resp = await client.post(
        "/api/v1/library/books",
        json={
            "title": "메타데이터 수정 도서",
            "author": "테스터",
            "totalPages": 200,
            "currentPage": 150,
            "readingStatus": "READING",
        },
    )
    book_id = create_resp.json()["bookId"]

    # 2. totalPages를 150으로 수정 (currentPage == totalPages 일치 발생)
    update_resp = await client.patch(
        f"/api/v1/library/books/{book_id}",
        json={
            "title": "메타데이터 수정 도서",
            "author": "테스터",
            "genre": "LITERATURE",
            "readingStatus": "READING",  # 클라이언트가 READING으로 보냈어도 totalPages 도달로 COMPLETED 자동 전이
            "totalPages": 150,
        },
    )
    assert update_resp.status_code == 200
    u_data = update_resp.json()
    assert u_data["readingStatus"] == "COMPLETED"
    assert u_data["completedAt"] is not None

    # 3. 명시적으로 readingStatus를 READING으로 되돌릴 때 completedAt 리셋
    revert_update = await client.patch(
        f"/api/v1/library/books/{book_id}",
        json={
            "title": "메타데이터 수정 도서",
            "author": "테스터",
            "genre": "LITERATURE",
            "readingStatus": "READING",
            "totalPages": 300,
        },
    )
    assert revert_update.status_code == 200
    assert revert_update.json()["readingStatus"] == "READING"
    assert revert_update.json()["completedAt"] is None


@pytest.mark.asyncio
async def test_create_book_flexible_genre_inputs(client: AsyncClient):
    # 1. 한글 'SF' 장르 입력 -> 대분류 LITERATURE, 세부 주제 'SF', displayGenre 'SF'
    resp1 = await client.post(
        "/api/v1/library/books",
        json={
            "title": "우리가 빛의 속도로 갈 수 없다면",
            "author": "김초엽",
            "genre": "SF",
        },
    )
    assert resp1.status_code == 201
    d1 = resp1.json()
    assert d1["genre"] == "LITERATURE"
    assert d1["genreName"] == "SF"  # Subject 1순위 보장
    assert d1["subject"] == "SF"
    assert d1["displayGenre"] == "SF"

    # 2. 한글 '에세이' 장르 입력
    resp2 = await client.post(
        "/api/v1/library/books",
        json={
            "title": "바람이 분다 당신이 좋다",
            "author": "이병률",
            "genre": "에세이",
        },
    )
    assert resp2.status_code == 201
    d2 = resp2.json()
    assert d2["genre"] == "LITERATURE"
    assert d2["subject"] == "에세이"
    assert d2["displayGenre"] == "에세이"

    # 3. KDC 분류기호만 주어졌을 때 세부 주제 자동 추론 ('813.7' -> 'SF/과학소설')
    resp3 = await client.post(
        "/api/v1/library/books",
        json={
            "title": "SF 소설집",
            "author": "SF 작가",
            "kdc": "813.7",
            "genre": "LITERATURE",
        },
    )
    assert resp3.status_code == 201
    d3 = resp3.json()
    assert d3["subject"] == "SF/과학소설"
    assert d3["displayGenre"] == "SF/과학소설"


@pytest.mark.asyncio
async def test_create_book_kyobo_cdn_cover_auto_injected(client: AsyncClient):
    # coverUrl을 보내지 않아도 정식 13자리 ISBN이 있으면 교보 CDN 자동 주입
    resp = await client.post(
        "/api/v1/library/books",
        json={
            "title": "표지 자동 주입 테스트",
            "author": "작가",
            "isbn": "9791190090018",
            "coverUrl": None,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "contents.kyobobook.co.kr" in data["coverUrl"]
    assert "9791190090018" in data["coverUrl"]


@pytest.mark.asyncio
async def test_list_books_response_contains_books_field(client: AsyncClient):
    # 도서 생성 후 목록 조회 시 items와 books가 모두 존재하는지 확인
    await client.post(
        "/api/v1/library/books",
        json={"title": "호환성 도서", "author": "호환 작가"},
    )
    resp = await client.get("/api/v1/library/books")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "books" in data
    assert isinstance(data["books"], list)
    assert len(data["books"]) >= 1
    assert data["books"][0]["title"] == "호환성 도서"
