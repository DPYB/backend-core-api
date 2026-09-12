import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_scrap_lifecycle(client: AsyncClient):
    # 1. 도서 생성
    book_id = (
        await client.post(
            "/api/v1/library/books",
            json={"title": "스크랩용 도서", "author": "저자"},
        )
    ).json()["bookId"]

    # 2. 스크랩 생성
    req = {
        "sentence": "소프트웨어 아키텍처의 목표는 인력을 최소화하는 것이다.",
        "pageNumber": 15,
        "scrapImageUrl": "https://example.com/scraps/1.jpg",
        "memo": "핵심 구절",
    }
    create_resp = await client.post(f"/api/v1/library/books/{book_id}/scraps", json=req)
    assert create_resp.status_code == 201
    scrap_id = create_resp.json()["scrapId"]
    assert create_resp.json()["sentence"] == req["sentence"]

    # 3. 도서별 스크랩 목록 조회
    list_resp = await client.get(f"/api/v1/library/books/{book_id}/scraps")
    assert list_resp.status_code == 200
    assert len(list_resp.json()["items"]) == 1

    # 4. GET /api/v1/library/scraps?bookId={id} 조회
    query_resp = await client.get(f"/api/v1/library/scraps?bookId={book_id}")
    assert query_resp.status_code == 200
    assert len(query_resp.json()["items"]) == 1

    # 5. 스크랩 단건 상세 조회
    detail_resp = await client.get(f"/api/v1/library/scraps/{scrap_id}")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["sentence"] == req["sentence"]

    # 6. 스크랩 수정
    update_req = {
        "sentence": "수정된 핵심 문장",
        "pageNumber": 20,
        "scrapImageUrl": "https://example.com/scraps/1_updated.jpg",
        "memo": "수정된 메모",
    }
    patch_resp = await client.patch(
        f"/api/v1/library/scraps/{scrap_id}", json=update_req
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["sentence"] == "수정된 핵심 문장"
    assert patch_resp.json()["pageNumber"] == 20

    # 7. 스크랩 삭제
    del_resp = await client.delete(f"/api/v1/library/scraps/{scrap_id}")
    assert del_resp.status_code == 204

    # 8. 삭제 후 단건 조회 -> 404
    get_after_del = await client.get(f"/api/v1/library/scraps/{scrap_id}")
    assert get_after_del.status_code == 404


@pytest.mark.asyncio
async def test_scrap_access_denied(client: AsyncClient, other_client: AsyncClient):
    # client 회원이 도서 및 스크랩 생성
    book_id = (
        await client.post(
            "/api/v1/library/books",
            json={"title": "내 도서", "author": "저자"},
        )
    ).json()["bookId"]

    scrap_id = (
        await client.post(
            f"/api/v1/library/books/{book_id}/scraps",
            json={
                "sentence": "비밀 문장",
                "scrapImageUrl": "https://example.com/secret.jpg",
            },
        )
    ).json()["scrapId"]

    # other_client가 client의 도서에 스크랩 등록 시도 -> 403
    create_attempt = await other_client.post(
        f"/api/v1/library/books/{book_id}/scraps",
        json={
            "sentence": "해킹 문장",
            "scrapImageUrl": "https://example.com/hack.jpg",
        },
    )
    assert create_attempt.status_code == 403
    assert create_attempt.json()["code"] == "LIBRARY_BOOK_ACCESS_DENIED"

    # other_client가 client의 스크랩 조회 시도 -> 403
    get_attempt = await other_client.get(f"/api/v1/library/scraps/{scrap_id}")
    assert get_attempt.status_code == 403
    assert get_attempt.json()["code"] == "SCRAP_ACCESS_DENIED"
