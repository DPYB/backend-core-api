from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.isbn import (
    calculate_isbn13_check_digit,
    convert_isbn10_to_isbn13,
    normalize_isbn,
    validate_isbn10,
    validate_isbn13,
)
from app.models.enums import BookReadingStatus, GenreType
from app.models.library_book import LibraryBook
from app.models.shelf import Shelf
from app.schemas.search import ExternalBook
from tests.conftest import TEST_MEMBER_ID

# ==============================================================================
# 1. 단위 테스트: app.core.isbn 유틸리티 검증
# ==============================================================================


def test_validate_isbn10_numeric():
    # 유효한 10자리 (숫자 체크디지트: 사피엔스 8934972467)
    assert validate_isbn10("8934972467") is True
    assert validate_isbn10("89-349-7246-7") is True

    # 잘못된 체크디지트
    assert validate_isbn10("8934972468") is False
    assert validate_isbn10("8934972460") is False

    # 잘못된 길이 및 비숫자
    assert validate_isbn10("123456789") is False
    assert validate_isbn10("12345678901") is False
    assert validate_isbn10("abcdefghij") is False
    assert validate_isbn10(None) is False


def test_validate_isbn10_x_check_digit():
    # 유효한 10자리 ('X' 또는 'x' 체크디지트)
    assert validate_isbn10("012000030X") is True
    assert validate_isbn10("012000030x") is True
    assert validate_isbn10("0-12-000030-X") is True
    assert validate_isbn10("0-12-000030-x") is True

    # 중간에 'X'가 들어간 경우
    assert validate_isbn10("012X000301") is False


def test_calculate_isbn13_check_digit():
    # 978893497246 -> 4
    assert calculate_isbn13_check_digit("978893497246") == "4"
    # 978012000030 -> 2
    assert calculate_isbn13_check_digit("978012000030") == "2"

    with pytest.raises(ValueError):
        calculate_isbn13_check_digit("12345")


def test_validate_isbn13():
    # 유효한 13자리
    assert validate_isbn13("9788934972464") is True
    assert validate_isbn13("978-89-349-7246-4") is True
    assert validate_isbn13("9788966262472") is True

    # 잘못된 체크디지트
    assert validate_isbn13("9788934972460") is False
    assert validate_isbn13("9781234567890") is False

    # 잘못된 길이 및 비숫자
    assert validate_isbn13("978893497246") is False
    assert validate_isbn13("97889349724641") is False
    assert validate_isbn13("978893497246X") is False
    assert validate_isbn13(None) is False


def test_convert_isbn10_to_isbn13():
    # 숫자 체크디지트 ISBN-10 -> ISBN-13
    assert convert_isbn10_to_isbn13("8934972467") == "9788934972464"
    assert convert_isbn10_to_isbn13("89-349-7246-7") == "9788934972464"

    # 'X' 체크디지트 ISBN-10 -> ISBN-13 (새 체크디지트 2 산출)
    assert convert_isbn10_to_isbn13("012000030X") == "9780120000302"
    assert convert_isbn10_to_isbn13("0-12-000030-x") == "9780120000302"

    # 유효하지 않은 ISBN-10 변환 시도 시 ValueError
    with pytest.raises(ValueError, match="유효하지 않은 10자리 ISBN"):
        convert_isbn10_to_isbn13("8934972460")


def test_normalize_isbn():
    # 1. 10자리 -> 13자리 정규화
    assert normalize_isbn("8934972467") == "9788934972464"
    assert normalize_isbn("012000030x") == "9780120000302"
    assert normalize_isbn(" 0-12-000030-X ") == "9780120000302"

    # 2. 13자리 정규화
    assert normalize_isbn("978-89-349-7246-4") == "9788934972464"
    assert normalize_isbn(" 9788934972464 ") == "9788934972464"

    # 3. None 및 빈 문자열
    assert normalize_isbn(None) is None
    assert normalize_isbn("") is None
    assert normalize_isbn("   ") is None

    # 4. 오류 검증
    with pytest.raises(ValueError, match="체크디지트"):
        normalize_isbn("8934972460")
    with pytest.raises(ValueError, match="체크디지트"):
        normalize_isbn("9781234567890")
    with pytest.raises(ValueError, match="10자리 또는 13자리"):
        normalize_isbn("12345")


# ==============================================================================
# 2. API 통합 테스트: 도서 등록 및 수정 정규화 검증
# ==============================================================================


@pytest.mark.asyncio
async def test_create_book_with_isbn10_normalized_to_isbn13(
    client: AsyncClient, db_session: AsyncSession
):
    """10자리 ISBN(숫자 및 X)으로 등록 시 DB 및 응답에 표준 13자리로 변환되어 저장됨"""
    # 1. 숫자 체크디지트 10자리 ISBN (사피엔스: 8934972467 -> 9788934972464)
    resp1 = await client.post(
        "/api/v1/library/books",
        json={
            "title": "사피엔스 (10자리 등록)",
            "author": "유발 하라리",
            "isbn": "8934972467",
        },
    )
    assert resp1.status_code == 201
    data1 = resp1.json()
    assert data1["isbn"] == "9788934972464"

    # DB 직접 확인
    book1 = (
        await db_session.execute(
            select(LibraryBook).where(LibraryBook.id == data1["bookId"])
        )
    ).scalar_one()
    assert book1.isbn == "9788934972464"

    # 2. 'X' 체크디지트 10자리 ISBN (하이픈 및 소문자 x 포함)
    resp2 = await client.post(
        "/api/v1/library/books",
        json={
            "title": "Academic Book (X 체크디지트)",
            "author": "Author",
            "isbn": "0-12-000030-x",
        },
    )
    assert resp2.status_code == 201
    data2 = resp2.json()
    assert data2["isbn"] == "9780120000302"


@pytest.mark.asyncio
async def test_create_book_with_hyphenated_isbn13(client: AsyncClient):
    """하이픈이 포함된 13자리 ISBN 등록 시 하이픈이 제거되고 13자리 숫자로 저장됨"""
    resp = await client.post(
        "/api/v1/library/books",
        json={
            "title": "클린 아키텍처",
            "author": "로버트 마틴",
            "isbn": "978-89-6626-247-2",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["isbn"] == "9788966262472"


@pytest.mark.asyncio
async def test_create_book_with_none_or_blank_isbn(
    client: AsyncClient, db_session: AsyncSession
):
    """ISBN이 없거나 빈 문자열인 경우 None(NULL)으로 저장됨"""
    # None 전달
    resp_none = await client.post(
        "/api/v1/library/books",
        json={
            "title": "독립출판물 1",
            "author": "독립작가",
            "isbn": None,
        },
    )
    assert resp_none.status_code == 201
    b_none_id = resp_none.json()["bookId"]
    assert resp_none.json()["isbn"] is None

    # 공백 문자열 전달
    resp_blank = await client.post(
        "/api/v1/library/books",
        json={
            "title": "독립출판물 2",
            "author": "독립작가",
            "isbn": "   ",
        },
    )
    assert resp_blank.status_code == 201
    b_blank_id = resp_blank.json()["bookId"]
    assert resp_blank.json()["isbn"] is None

    # DB 컬럼이 실제 NULL인지 확인
    b_none = (
        await db_session.execute(select(LibraryBook).where(LibraryBook.id == b_none_id))
    ).scalar_one()
    assert b_none.isbn is None

    b_blank = (
        await db_session.execute(
            select(LibraryBook).where(LibraryBook.id == b_blank_id)
        )
    ).scalar_one()
    assert b_blank.isbn is None


@pytest.mark.asyncio
async def test_create_book_with_invalid_isbn_rejected(client: AsyncClient):
    """체크디지트가 잘못되었거나 형식이 부적합한 ISBN은 요청 검증 오류(400 Bad Request) 거부"""
    # 1. 13자리 체크디지트 오류
    r1 = await client.post(
        "/api/v1/library/books",
        json={"title": "잘못된 도서", "author": "저자", "isbn": "9781234567890"},
    )
    assert r1.status_code == 400
    assert r1.json()["code"] == "INVALID_SEARCH_PARAMETER"

    # 2. 10자리 체크디지트 오류
    r2 = await client.post(
        "/api/v1/library/books",
        json={"title": "잘못된 도서", "author": "저자", "isbn": "8934972460"},
    )
    assert r2.status_code == 400
    assert r2.json()["code"] == "INVALID_SEARCH_PARAMETER"

    # 3. 비정상 길이
    r3 = await client.post(
        "/api/v1/library/books",
        json={"title": "잘못된 도서", "author": "저자", "isbn": "12345"},
    )
    assert r3.status_code == 400
    assert r3.json()["code"] == "INVALID_SEARCH_PARAMETER"


@pytest.mark.asyncio
async def test_update_book_isbn_normalization(client: AsyncClient):
    """도서 수정(PATCH) 시에도 동일하게 ISBN 정규화 및 오류 검증이 동작함"""
    create_resp = await client.post(
        "/api/v1/library/books",
        json={"title": "원래 도서", "author": "저자"},
    )
    book_id = create_resp.json()["bookId"]

    # 1. 유효한 10자리 ISBN으로 수정 -> 13자리로 변환
    patch_resp = await client.patch(
        f"/api/v1/library/books/{book_id}",
        json={
            "title": "원래 도서",
            "author": "저자",
            "isbn": "0-12-000030-x",
            "readingStatus": "READING",
        },
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["isbn"] == "9780120000302"

    # 2. 잘못된 체크디지트로 수정 시도 -> 400 거부
    patch_fail = await client.patch(
        f"/api/v1/library/books/{book_id}",
        json={
            "title": "원래 도서",
            "author": "저자",
            "isbn": "9781234567890",
            "readingStatus": "READING",
        },
    )
    assert patch_fail.status_code == 400
    assert patch_fail.json()["code"] == "INVALID_SEARCH_PARAMETER"


@pytest.mark.asyncio
async def test_duplicate_isbn_conflict_between_isbn10_and_isbn13(client: AsyncClient):
    """동일 도서를 ISBN-10으로 먼저 등록한 후 ISBN-13으로 재등록 시 409 Conflict 발생"""
    # 1. 10자리 ISBN으로 등록 (사피엔스: 8934972467 -> 9788934972464로 저장됨)
    r1 = await client.post(
        "/api/v1/library/books",
        json={
            "title": "사피엔스 (10자리)",
            "author": "유발 하라리",
            "isbn": "8934972467",
        },
    )
    assert r1.status_code == 201

    # 2. 동일 도서를 13자리 ISBN으로 중복 등록 시도
    r2 = await client.post(
        "/api/v1/library/books",
        json={
            "title": "사피엔스 (13자리)",
            "author": "유발 하라리",
            "isbn": "9788934972464",
        },
    )
    assert r2.status_code == 409
    assert r2.json()["code"] == "BOOK_ALREADY_REGISTERED"

    # 3. 하이픈 포함 13자리로 시도해도 동일하게 차단
    r3 = await client.post(
        "/api/v1/library/books",
        json={
            "title": "사피엔스 (하이픈 13자리)",
            "author": "유발 하라리",
            "isbn": "978-89-349-7246-4",
        },
    )
    assert r3.status_code == 409
    assert r3.json()["code"] == "BOOK_ALREADY_REGISTERED"


# ==============================================================================
# 3. 검색 API 테스트: X 체크디지트 및 ISBN-10 정규화 검색
# ==============================================================================


@pytest.mark.asyncio
async def test_search_by_isbn10_with_x_digit(client: AsyncClient):
    """끝자리가 'X' 또는 'x'인 10자리 ISBN으로 검색 시 국립중앙도서관에 13자리로 조회"""
    with patch(
        "app.routers.search.client.lookup_by_isbn", new_callable=AsyncMock
    ) as mock_lookup:
        mock_lookup.return_value = ExternalBook(
            title="Academic Research",
            author="Author",
            isbn="9780120000302",
        )
        # 소문자 x 및 하이픈으로 검색
        resp = await client.get("/api/v1/books/search?isbn=0-12-000030-x")
        assert resp.status_code == 200
        data = resp.json()
        assert data["alreadyRegistered"] is False
        assert data["book"] is not None
        assert data["book"]["isbn"] == "9780120000302"

        # 국립중앙도서관에는 정규화된 13자리로 호출되었는지 확인
        mock_lookup.assert_called_once_with("9780120000302")


@pytest.mark.asyncio
async def test_search_already_registered_book_using_isbn10(
    client: AsyncClient, db_session: AsyncSession
):
    """내 서재에 13자리로 등록된 도서를 10자리 ISBN으로 검색했을 때 기등록 상태로 즉시 탐지"""
    # 1. 13자리 도서 등록
    shelf = Shelf(member_id=TEST_MEMBER_ID, name="기본 책장", is_default=True)
    db_session.add(shelf)
    await db_session.flush()

    book = LibraryBook(
        member_id=TEST_MEMBER_ID,
        shelf_id=shelf.id,
        shelf_rank="A",
        title="사피엔스",
        author="유발 하라리",
        isbn="9788934972464",
        genre=GenreType.LITERATURE,
        reading_status=BookReadingStatus.READING,
    )
    db_session.add(book)
    await db_session.commit()

    # 2. 10자리 ISBN으로 검색 (8934972467 -> 정규화되어 9788934972464로 DB 매칭)
    resp = await client.get("/api/v1/books/search?isbn=8934972467")
    assert resp.status_code == 200
    data = resp.json()
    assert data["alreadyRegistered"] is True
    assert data["libraryBook"]["title"] == "사피엔스"
    assert data["libraryBook"]["isbn"] == "9788934972464"
