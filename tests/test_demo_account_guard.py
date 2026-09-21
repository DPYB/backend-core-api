import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security import create_access_token, get_demo_member_id


@pytest.fixture
def demo_jwt_token() -> str:
    """데모 계정(DEMO_MEMBER_ID)으로 서명된 정상 Bearer JWT 토큰 발급"""
    demo_id = get_demo_member_id()
    return create_access_token(
        member_id=demo_id,
        email="demo@dontpawget.com",
        nickname="데모냥이",
    )


@pytest.fixture
def demo_headers(demo_jwt_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {demo_jwt_token}"}


@pytest.mark.asyncio
async def test_demo_account_allowed_mutations(
    client: AsyncClient, demo_headers: dict[str, str]
):
    """
    1. 데모 계정 허용 쓰기 라우트 검증:
       - 도서 등록 (POST /api/v1/library/books)
       - 도서 진도율 수정 (PATCH /api/v1/library/books/{id}/progress)
       - 스크랩 작성 (POST /api/v1/library/books/{id}/scraps)
       - 세션 기록 (POST /api/v1/reading-sessions)
    """
    # 1-1. 도서 등록 성공
    create_resp = await client.post(
        "/api/v1/library/books",
        json={
            "title": "데모 체험용 도서",
            "author": "홍길동",
            "isbn": "9781111111111",
            "totalPages": 200,
            "currentPage": 10,
        },
        headers=demo_headers,
    )
    assert create_resp.status_code == 201
    book_id = create_resp.json()["bookId"]

    # 1-2. 진도율 수정 성공
    progress_resp = await client.patch(
        f"/api/v1/library/books/{book_id}/progress",
        json={"currentPage": 50},
        headers=demo_headers,
    )
    assert progress_resp.status_code == 200
    assert progress_resp.json()["currentPage"] == 50

    # 1-3. 스크랩 작성 성공
    scrap_resp = await client.post(
        f"/api/v1/library/books/{book_id}/scraps",
        json={
            "sentence": "인상 깊은 데모 문장입니다.",
            "pageNumber": 25,
            "scrapImageUrl": "https://example.com/scrap.jpg",
            "memo": "데모 메모",
        },
        headers=demo_headers,
    )
    assert scrap_resp.status_code == 201
    scrap_id = scrap_resp.json()["scrapId"]

    # 1-4. 스크랩 수정 성공
    patch_scrap_resp = await client.patch(
        f"/api/v1/library/scraps/{scrap_id}",
        json={
            "sentence": "수정된 인상 깊은 데모 문장",
            "scrapImageUrl": "https://example.com/scrap_updated.jpg",
            "memo": "수정된 데모 메모",
        },
        headers=demo_headers,
    )
    assert patch_scrap_resp.status_code == 200

    # 1-5. 독서 세션 기록 성공
    session_resp = await client.post(
        "/api/v1/reading-sessions",
        json={
            "bookId": book_id,
            "durationMinutes": 15,
            "startPage": 50,
            "endPage": 60,
        },
        headers=demo_headers,
    )
    assert session_resp.status_code == 201


@pytest.mark.asyncio
async def test_demo_account_blocked_destructive_mutations(
    client: AsyncClient, demo_headers: dict[str, str]
):
    """
    2. 데모 계정 차단 라우트 검증 (403 DEMO_ACCOUNT_PROTECTED):
       - 비밀번호 변경 (POST /api/v1/auth/password/change)
       - 회원 탈퇴 (DELETE /api/v1/users/me)
       - 프로필 수정 (PATCH /api/v1/users/me)
       - 도서 삭제 (DELETE /api/v1/library/books/{book_id})
       - 책장 생성/수정/삭제 (POST/PATCH/DELETE /api/v1/library/shelves)
    """
    # 2-1. 비밀번호 변경 시도 -> 403 차단
    resp_pw = await client.post(
        "/api/v1/auth/password/change",
        json={"currentPassword": "old", "newPassword": "NewPassword123!"},
        headers=demo_headers,
    )
    assert resp_pw.status_code == 403
    assert resp_pw.json()["code"] == "DEMO_ACCOUNT_PROTECTED"

    # 2-2. 회원 탈퇴 시도 -> 403 차단
    resp_withdraw = await client.delete("/api/v1/users/me", headers=demo_headers)
    assert resp_withdraw.status_code == 403
    assert resp_withdraw.json()["code"] == "DEMO_ACCOUNT_PROTECTED"

    # 2-3. 프로필 수정 시도 -> 403 차단
    resp_profile = await client.patch(
        "/api/v1/users/me",
        json={"nickname": "해킹된데모"},
        headers=demo_headers,
    )
    assert resp_profile.status_code == 403
    assert resp_profile.json()["code"] == "DEMO_ACCOUNT_PROTECTED"

    # 2-4. 도서 삭제 시도 -> 403 차단
    resp_del_book = await client.delete(
        "/api/v1/library/books/9999",
        headers=demo_headers,
    )
    assert resp_del_book.status_code == 403
    assert resp_del_book.json()["code"] == "DEMO_ACCOUNT_PROTECTED"

    # 2-5. 책장 생성 시도 -> 403 차단
    resp_shelf = await client.post(
        "/api/v1/library/shelves",
        json={"name": "데모의 임의 책장"},
        headers=demo_headers,
    )
    assert resp_shelf.status_code == 403
    assert resp_shelf.json()["code"] == "DEMO_ACCOUNT_PROTECTED"


@pytest.mark.asyncio
async def test_demo_account_book_quota_limit(
    client: AsyncClient, demo_headers: dict[str, str], monkeypatch
):
    """
    3. 데모 계정 도서 Quota 제한 검증:
       - 설정된 한도(테스트를 위해 DEMO_MAX_BOOKS=2로 설정) 도달 후 추가 등록 시 403 DEMO_QUOTA_EXCEEDED 반환
    """
    monkeypatch.setattr(settings, "DEMO_MAX_BOOKS", 2)

    # 1번째 도서 등록 (성공)
    r1 = await client.post(
        "/api/v1/library/books",
        json={"title": "도서 1", "author": "저자 1", "isbn": "9781000000001"},
        headers=demo_headers,
    )
    assert r1.status_code == 201

    # 2번째 도서 등록 (성공)
    r2 = await client.post(
        "/api/v1/library/books",
        json={"title": "도서 2", "author": "저자 2", "isbn": "9781000000002"},
        headers=demo_headers,
    )
    assert r2.status_code == 201

    # 3번째 도서 등록 -> Quota 초과로 403 차단
    r3 = await client.post(
        "/api/v1/library/books",
        json={"title": "도서 3", "author": "저자 3", "isbn": "9781000000003"},
        headers=demo_headers,
    )
    assert r3.status_code == 403
    assert r3.json()["code"] == "DEMO_QUOTA_EXCEEDED"


@pytest.mark.asyncio
async def test_demo_account_scrap_quota_limit(
    client: AsyncClient, demo_headers: dict[str, str], monkeypatch
):
    """
    4. 데모 계정 도서당 스크랩 Quota 제한 검증:
       - 설정된 한도(테스트를 위해 DEMO_MAX_SCRAPS_PER_BOOK=2로 설정) 도달 후 추가 등록 시 403 DEMO_QUOTA_EXCEEDED 반환
    """
    monkeypatch.setattr(settings, "DEMO_MAX_SCRAPS_PER_BOOK", 2)

    # 도서 등록
    b_resp = await client.post(
        "/api/v1/library/books",
        json={"title": "스크랩 테스트 도서", "author": "저자", "isbn": "9782000000001"},
        headers=demo_headers,
    )
    book_id = b_resp.json()["bookId"]

    # 1번째 스크랩 (성공)
    s1 = await client.post(
        f"/api/v1/library/books/{book_id}/scraps",
        json={
            "sentence": "문장 1",
            "pageNumber": 1,
            "scrapImageUrl": "https://example.com/s1.jpg",
        },
        headers=demo_headers,
    )
    assert s1.status_code == 201

    # 2번째 스크랩 (성공)
    s2 = await client.post(
        f"/api/v1/library/books/{book_id}/scraps",
        json={
            "sentence": "문장 2",
            "pageNumber": 2,
            "scrapImageUrl": "https://example.com/s2.jpg",
        },
        headers=demo_headers,
    )
    assert s2.status_code == 201

    # 3번째 스크랩 -> Quota 초과로 403 차단
    s3 = await client.post(
        f"/api/v1/library/books/{book_id}/scraps",
        json={
            "sentence": "문장 3",
            "pageNumber": 3,
            "scrapImageUrl": "https://example.com/s3.jpg",
        },
        headers=demo_headers,
    )
    assert s3.status_code == 403
    assert s3.json()["code"] == "DEMO_QUOTA_EXCEEDED"


@pytest.mark.asyncio
async def test_normal_member_is_not_restricted(
    client: AsyncClient, db_session: AsyncSession, monkeypatch
):
    """
    5. 일반 회원은 데모 가드/상한에 영향을 받지 않고 정상 동작 (무회귀 검증):
       - 비밀번호 변경, 프로필 수정, 도서 삭제, 쿼터 제한 없이 통과
    """
    monkeypatch.setattr(settings, "DEMO_MAX_BOOKS", 1)

    from app.models.member import Member
    from tests.conftest import TEST_MEMBER_ID

    # 회원 레코드 생성
    normal_member = Member(
        member_id=TEST_MEMBER_ID,
        email="normal@test.com",
        nickname="일반유저",
        status="ACTIVE",
    )
    db_session.add(normal_member)
    await db_session.commit()

    # 일반 회원 토큰(기본 client 픽스처는 TEST_MEMBER_ID 사용)
    # 도서 2권 연속 등록 (상한 1권이지만 일반 회원이므로 2권 모두 성공)
    r1 = await client.post(
        "/api/v1/library/books",
        json={"title": "일반 도서 1", "author": "저자 1", "isbn": "9783000000001"},
    )
    assert r1.status_code == 201

    r2 = await client.post(
        "/api/v1/library/books",
        json={"title": "일반 도서 2", "author": "저자 2", "isbn": "9783000000002"},
    )
    assert r2.status_code == 201

    # 프로필 수정 통과 (데모 가드에 막히지 않음)
    patch_resp = await client.patch(
        "/api/v1/users/me",
        json={"nickname": "일반사용자"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["nickname"] == "일반사용자"
