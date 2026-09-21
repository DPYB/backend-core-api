import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security import get_demo_member_id
from app.models.enums import BookReadingStatus, GenreType
from app.models.library_book import LibraryBook
from app.models.reading_session import ReadingSession
from app.models.record import Record
from app.models.scrap import Scrap
from app.models.shelf import Shelf
from app.services.demo_seed_data import DEMO_SEED_BOOKS_BY_ISBN


@pytest.mark.asyncio
async def test_admin_demo_reset_auth_failures(client: AsyncClient):
    """
    1. 관리자 리셋 엔드포인트 인증 실패 검증:
       - X-Admin-Key 헤더 누락 시 401 Unauthorized
       - X-Admin-Key 불일치 시 403 Forbidden
    """
    # 1-1. 헤더 누락
    resp_no_key = await client.post("/api/v1/admin/demo/reset")
    assert resp_no_key.status_code == 401
    assert "X-Admin-Key" in resp_no_key.json()["message"]

    # 1-2. 잘못된 키
    resp_bad_key = await client.post(
        "/api/v1/admin/demo/reset",
        headers={"X-Admin-Key": "invalid-secret-key"},
    )
    assert resp_bad_key.status_code == 403


@pytest.mark.asyncio
async def test_admin_demo_reset_success_and_idempotence(
    client: AsyncClient, db_session: AsyncSession
):
    """
    2. 관리자 리셋 정상 동작 및 멱등성 검증:
       - 시드 도서의 진도율 및 상태 변경 후 리셋 시 원복 확인
       - 잉여 도서 및 스크랩/세션 추가 후 리셋 시 일괄 삭제 확인
       - 2회 연속 리셋 호출 시 멱등 성공 확인
    """
    demo_member_id = get_demo_member_id()

    # 2-0. 기본 책장 생성
    default_shelf = Shelf(
        member_id=demo_member_id,
        name="기본 책장",
        is_default=True,
    )
    db_session.add(default_shelf)
    await db_session.flush()

    # 2-1. 시드 도서 1권 생성 (《파견자들》 - 원래 current_page: 52, READING)
    seed_isbn = "9791191587524"
    seed_book = LibraryBook(
        member_id=demo_member_id,
        shelf_id=default_shelf.id,
        shelf_rank="a0",
        isbn=seed_isbn,
        title="파견자들",
        author="김초엽",
        genre=GenreType.LITERATURE,
        total_pages=444,
        current_page=200,  # 오염된 진도율 (원래 52)
        reading_status=BookReadingStatus.COMPLETED,  # 오염된 상태 (원래 READING)
    )
    db_session.add(seed_book)
    await db_session.flush()

    # 시드 도서의 정규 스크랩 1개 + 오염된 추가 스크랩 1개 생성
    valid_scrap = Scrap(
        book_id=seed_book.id,
        sentence="지상은 저주받은 땅이 아니었다. 단지 우리가 알던 형태가 아닌 다른 생명이 번성하고 있을 뿐이었다.",
        page_number=38,
        scrap_image_url="https://example.com/cover.jpg",
    )
    surplus_scrap_on_seed = Scrap(
        book_id=seed_book.id,
        sentence="사용자가 임의로 추가한 불필요한 스크랩 문장입니다.",
        page_number=100,
        scrap_image_url="https://example.com/bad.jpg",
    )
    db_session.add_all([valid_scrap, surplus_scrap_on_seed])

    # 2-2. 잉여 도서 1권 생성 (시드 외 사용자가 임의 등록한 책)
    surplus_book = LibraryBook(
        member_id=demo_member_id,
        shelf_id=default_shelf.id,
        shelf_rank="a1",
        isbn="9789999999999",
        title="사용자가 등록한 잉여 도서",
        author="임의저자",
        genre=GenreType.TECHNOLOGY,
        total_pages=300,
        current_page=100,
        reading_status=BookReadingStatus.READING,
    )
    db_session.add(surplus_book)
    await db_session.flush()

    # 잉여 도서의 스크랩 및 세션 생성
    surplus_scrap = Scrap(
        book_id=surplus_book.id,
        sentence="잉여 도서의 스크랩",
        scrap_image_url="https://example.com/surplus.jpg",
    )
    surplus_session = ReadingSession(
        member_id=demo_member_id,
        book_id=surplus_book.id,
        duration_minutes=20,
        duration_seconds=1200,
    )
    surplus_record = Record(
        member_id=demo_member_id,
        book_id=surplus_book.id,
        title="잉여 기록",
        content="잉여 내용",
    )
    db_session.add_all([surplus_scrap, surplus_session, surplus_record])
    await db_session.commit()

    # 2-3. 정상 관리자 리셋 호출
    admin_headers = {"X-Admin-Key": settings.ADMIN_API_KEY}
    resp1 = await client.post("/api/v1/admin/demo/reset", headers=admin_headers)
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["status"] == "SUCCESS"
    assert data1["deleted_surplus_books"] >= 1
    assert data1["deleted_surplus_scraps"] >= 1
    assert data1["restored_seed_books"] == 1

    # 2-4. DB 반영 상태 검증
    # 잉여 도서는 삭제되었어야 함
    surplus_book_check = await db_session.execute(
        select(LibraryBook).where(LibraryBook.id == surplus_book.id)
    )
    assert surplus_book_check.scalar_one_or_none() is None

    # 시드 도서는 원래 기준값으로 복원되었어야 함
    refreshed_seed = await db_session.execute(
        select(LibraryBook).where(LibraryBook.id == seed_book.id)
    )
    book_after_reset = refreshed_seed.scalar_one()
    expected_meta = DEMO_SEED_BOOKS_BY_ISBN[seed_isbn]
    assert book_after_reset.current_page == expected_meta["current_page"]  # 52로 복구
    assert (
        book_after_reset.reading_status == expected_meta["reading_status"]
    )  # READING으로 복구
    assert book_after_reset.completed_at is None

    # 시드 도서의 오염된 스크랩은 삭제되고 정규 스크랩만 남았어야 함
    scraps_check = (
        (await db_session.execute(select(Scrap).where(Scrap.book_id == seed_book.id)))
        .scalars()
        .all()
    )
    assert len(scraps_check) == 1
    assert scraps_check[0].sentence == valid_scrap.sentence

    # 2-5. 멱등성 검증 (동일한 리셋 재호출 시 에러 없이 SUCCESS)
    resp2 = await client.post("/api/v1/admin/demo/reset", headers=admin_headers)
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["status"] == "SUCCESS"
    assert data2["deleted_surplus_books"] == 0
    assert data2["restored_seed_books"] == 1
