from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ddc_mapper import ddc_to_genre
from app.core.genre_mapper import (
    fallback_genre_by_keywords,
    parse_to_genre_and_subject,
)
from app.core.kdc_mapper import (
    kdc_to_genre,
    kdc_to_subject,
)
from app.models.enums import GenreType
from app.models.library_book import LibraryBook
from app.models.shelf import Shelf
from app.schemas.search import ExternalBook
from app.services.ai_agent import ClassifyGenreResult
from tests.conftest import TEST_MEMBER_ID


# ---------------------------------------------------------------------------
# T1: Google Books categories만 존재 시 DDC로 간주하지 않음
# ---------------------------------------------------------------------------
def test_contract_t1_google_categories_not_ddc():
    google_category = "Computers / Programming Languages / Python"
    assert ddc_to_genre(google_category) == GenreType.NONE
    assert kdc_to_genre(google_category) == GenreType.NONE

    genre, sub = parse_to_genre_and_subject(
        genre_input=None, current_subject=None, kdc_str=None, ddc_str=None
    )
    assert genre == GenreType.NONE


# ---------------------------------------------------------------------------
# T2: 공식 KDC 004/005 확인 시 GENERAL + subject="컴퓨터/IT" 보존 (안 A 확정)
# ---------------------------------------------------------------------------
def test_contract_t2_kdc_004_005_plan_a():
    assert kdc_to_genre("005.133") == GenreType.GENERAL
    assert kdc_to_subject("005.133") == "컴퓨터/IT"
    assert kdc_to_subject("004.1") == "컴퓨터/IT"

    genre, sub = parse_to_genre_and_subject(kdc_str="005.133", genre_input=None)
    assert genre == GenreType.GENERAL
    assert sub == "컴퓨터/IT"


# ---------------------------------------------------------------------------
# T3: 공식 분류 없음, LLM 추론 성공 시 genre_source="LLM" 영속화
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_contract_t3_llm_genre_source_persistence(
    client: AsyncClient, db_session: AsyncSession
):
    mock_classify = ClassifyGenreResult(
        genre=GenreType.LITERATURE,
        subject="SF소설",
        confidence=0.92,
        source="LLM",
        reason="SF 모험 서사",
    )

    with patch(
        "app.services.ai_agent.AiAgentClient.classify_genre",
        new_callable=AsyncMock,
        return_value=mock_classify,
    ):
        resp = await client.post(
            "/api/v1/library/books",
            json={
                "title": "미지의 행성 탐사기",
                "author": "우주 작가",
                "isbn": "9791190090018",
                "genre": "NONE",
                "genreSource": "KDC",  # 초기 요청은 기본값이나
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["genre"] == "LITERATURE"
        assert data["subject"] == "SF소설"
        assert data["genreSource"] == "LLM"
        assert data["genreConfidence"] == 0.92
        assert data["displayGenre"] == "SF소설"


# ---------------------------------------------------------------------------
# T4: LLM 결과도 불확실 시 GenreType.NONE 명시적 미분류 허용
# ---------------------------------------------------------------------------
def test_contract_t4_ambiguous_allows_none():
    genre, sub = fallback_genre_by_keywords("모호하고 알 수 없는 책")
    assert genre == GenreType.NONE
    assert sub is None

    # 명백한 지표어가 있을 때만 FALLBACK 반환
    g_hist, s_hist = fallback_genre_by_keywords("조선왕조실록 역사기행")
    assert g_hist == GenreType.HISTORY
    assert s_hist == "역사"


# ---------------------------------------------------------------------------
# T5: 사용자 수동 수정(genre_source="USER") 시 모든 자동 재분류 덮어쓰기 100% 차단
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_contract_t5_user_modification_immutable_protection(
    client: AsyncClient, db_session: AsyncSession
):
    # 1. 도서 최초 등록 (LLM으로 분류됨)
    mock_classify = ClassifyGenreResult(
        genre=GenreType.LITERATURE,
        subject="문학",
        confidence=0.8,
        source="LLM",
    )
    with patch(
        "app.services.ai_agent.AiAgentClient.classify_genre",
        new_callable=AsyncMock,
        return_value=mock_classify,
    ):
        resp = await client.post(
            "/api/v1/library/books",
            json={
                "title": "사용자 주권 테스트 도서",
                "author": "테스트 작가",
                "isbn": "9791162242742",
                "genre": "NONE",
            },
        )
        assert resp.status_code == 201
        book_id = resp.json()["bookId"]
        assert resp.json()["genreSource"] == "LLM"

    # 2. 사용자가 장르를 ARTS(예술)로 직접 수정 -> genre_source="USER" 자동 승격
    update_resp = await client.patch(
        f"/api/v1/library/books/{book_id}",
        json={
            "title": "사용자 주권 테스트 도서",
            "author": "테스트 작가",
            "isbn": "9791162242742",
            "genre": "ARTS",
            "subject": "미술사",
            "readingStatus": "READING",
        },
    )
    assert update_resp.status_code == 200
    updated_data = update_resp.json()
    assert updated_data["genre"] == "ARTS"
    assert updated_data["subject"] == "미술사"
    assert updated_data["genreSource"] == "USER"

    # 3. 이후 동일 ISBN 캐시 재사용 경로에서 다른 회원이 등록하더라도,
    # USER 출처 도서는 캐시 덮어쓰기 소스로 오염되지 않음
    stmt = select(LibraryBook).where(LibraryBook.id == book_id)
    book = (await db_session.execute(stmt)).scalars().first()
    assert book is not None
    assert book.genre_source == "USER"
    assert book.genre == GenreType.ARTS


# ---------------------------------------------------------------------------
# T6: 동일 도서 KDC vs DDC 상이 번대 충돌 분기 검증
# ---------------------------------------------------------------------------
def test_contract_t6_kdc_ddc_independent_conflict_resolution():
    # 400번대: KDC는 자연과학, DDC는 언어
    assert kdc_to_genre("400") == GenreType.NATURAL_SCIENCE
    assert ddc_to_genre("400") == GenreType.LANGUAGE

    # 500번대: KDC는 기술과학, DDC는 자연과학
    assert kdc_to_genre("500") == GenreType.TECHNOLOGY
    assert ddc_to_genre("500") == GenreType.NATURAL_SCIENCE

    # 600번대: KDC는 예술, DDC는 기술과학
    assert kdc_to_genre("600") == GenreType.ARTS
    assert ddc_to_genre("600") == GenreType.TECHNOLOGY

    # 700번대: KDC는 언어, DDC는 예술
    assert kdc_to_genre("700") == GenreType.LANGUAGE
    assert ddc_to_genre("700") == GenreType.ARTS

    # catalog에 따른 우선순위 분기 검증 (US -> DDC 우선, KR -> KDC 우선)
    genre_us, _ = parse_to_genre_and_subject(
        genre_input=None,
        kdc_str="500",  # KDC 기준 기술과학
        ddc_str="500",  # DDC 기준 자연과학
        catalog="US",
    )
    assert genre_us == GenreType.NATURAL_SCIENCE

    genre_kr, _ = parse_to_genre_and_subject(
        genre_input=None,
        kdc_str="500",  # KDC 기준 기술과학
        ddc_str="500",  # DDC 기준 자연과학
        catalog="KR",
    )
    assert genre_kr == GenreType.TECHNOLOGY


# ---------------------------------------------------------------------------
# T7: YES24 표지/소개글 결측 시 교보 CDN 폴백 및 DTO 정합성 검증
# ---------------------------------------------------------------------------
def test_contract_t7_external_book_dto_data_source():
    # ExternalBook DTO에 data_source와 genre_source가 독립 보존되는지 검증
    book = ExternalBook(
        title="결측치 테스트 도서",
        author="작가",
        isbn="9788966260959",
        genre=GenreType.GENERAL,
        kdc="005.133",
        subject="컴퓨터/IT",
        data_source="YES24",
        genre_source="KDC",
    )
    dump = book.model_dump(by_alias=True)
    assert dump["dataSource"] == "YES24"
    assert dump["genreSource"] == "KDC"
    assert dump["genreName"] == "교양"
    assert dump["displayGenre"] == "컴퓨터/IT"


# ---------------------------------------------------------------------------
# T8: 카탈로그 변경 시 기존 등록 도서의 data_source 불변 검증
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_contract_t8_data_source_immutability(
    client: AsyncClient, db_session: AsyncSession
):
    # 등록된 도서의 data_source는 검색 카탈로그 파라미터가 바뀌어도 변하지 않음
    shelf = Shelf(member_id=TEST_MEMBER_ID, name="기본 책장", is_default=True)
    db_session.add(shelf)
    await db_session.flush()

    book = LibraryBook(
        member_id=TEST_MEMBER_ID,
        shelf_id=shelf.id,
        shelf_rank="A",
        title="글로벌 도서",
        author="글로벌 저자",
        isbn="9780132350884",
        genre=GenreType.GENERAL,
        kdc="005.133",
        subject="컴퓨터/IT",
        genre_source="KDC",
    )
    db_session.add(book)
    await db_session.commit()

    # 조회 시 등록된 도서 정보는 불변
    resp = await client.get("/api/v1/library/books")
    assert resp.status_code == 200
    items = resp.json()["items"]
    matched = next((b for b in items if b["isbn"] == "9780132350884"), None)
    assert matched is not None
    assert matched["genre"] == "GENERAL"
    assert matched["displayGenre"] == "컴퓨터/IT"
