import asyncio
import logging
import re
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidSearchParameterException
from app.core.isbn import normalize_isbn
from app.core.kdc_mapper import parse_to_genre_and_subject
from app.core.security import get_optional_member_id
from app.db.session import get_db
from app.models.library_book import LibraryBook
from app.schemas.library_book import LibraryBookDetailResponse
from app.schemas.search import (
    BookSearchItem,
    BookSearchResponse,
    ExternalBook,
    SearchLibraryBookDetail,
)
from app.services.book_service import BookService
from app.services.national_library import NationalLibraryClient
from app.services.yes24 import Yes24Client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/books", tags=["Book Discovery"])
client = NationalLibraryClient()
yes24_client = Yes24Client()

ISBN_REGEX = re.compile(r"^(?:[0-9]{9}[0-9Xx]|[0-9]{13})$")


@router.get("/search", response_model=BookSearchResponse)
async def search_book(
    isbn: str | None = Query(None, description="10자리 또는 13자리 ISBN"),
    query: str | None = Query(None, description="도서명 또는 검색 키워드"),
    limit: int = Query(10, ge=1, le=20, description="최대 반환 도서 수"),
    member_id: uuid.UUID | None = Depends(get_optional_member_id),
    db: AsyncSession = Depends(get_db),
):
    """
    도서 검색 API (ISBN 단건 검색 및 YES24 키워드 통합 검색 지원).
    - isbn 제공 시: 국립중앙도서관 정식 서지정보 및 내 서재 등록 여부 반환
    - query 제공 시: YES24 Open API를 통해 단행본 도서 후보 목록(표지, 쪽수, 소개글) 반환 + 내 서재 기등록 여부(isRegistered) 매핑 + 원본 query 에코
    """
    if isbn is not None:
        clean_isbn = isbn.strip()
        cleaned_no_hyphen = re.sub(r"[-\s]", "", clean_isbn).upper()
        if not cleaned_no_hyphen or not ISBN_REGEX.match(cleaned_no_hyphen):
            raise InvalidSearchParameterException(
                "올바른 10자리 또는 13자리 숫자 ISBN을 입력해주세요."
            )
        try:
            norm_isbn = normalize_isbn(clean_isbn)
            if not norm_isbn:
                raise ValueError()
        except ValueError:
            raise InvalidSearchParameterException(
                "올바른 10자리 또는 13자리 숫자 ISBN을 입력해주세요."
            )
        return await _search_by_isbn(db, norm_isbn, member_id, query_str=clean_isbn)

    search_keyword = (query or "").strip()
    if not search_keyword:
        raise InvalidSearchParameterException(
            "올바른 10자리 또는 13자리 숫자 ISBN 또는 검색 키워드를 입력해주세요."
        )

    clean_digits = re.sub(r"[-\s]", "", search_keyword).upper()
    if ISBN_REGEX.match(clean_digits):
        try:
            norm_isbn = normalize_isbn(clean_digits)
            if norm_isbn:
                return await _search_by_isbn(
                    db, norm_isbn, member_id, query_str=search_keyword
                )
        except ValueError:
            pass

    # 1. YES24 키워드 검색 우선 시도
    yes24_items = await yes24_client.search_books(
        query=search_keyword, page=1, page_size=limit
    )
    if yes24_items:
        # 내 서재 등록 여부(is_registered) 일괄 매핑
        if member_id:
            isbns = [it.isbn for it in yes24_items if it.isbn]
            if isbns:
                reg_stmt = select(LibraryBook.isbn).where(
                    LibraryBook.member_id == member_id,
                    LibraryBook.isbn.in_(isbns),
                    LibraryBook.deleted_at.is_(None),
                )
                registered_isbns = set((await db.execute(reg_stmt)).scalars().all())
                for it in yes24_items:
                    if it.isbn in registered_isbns:
                        it.is_registered = True

        return BookSearchResponse(
            query=search_keyword,
            total=len(yes24_items),
            items=yes24_items,
            already_registered=any(it.is_registered for it in yes24_items),
            library_book=None,
            book=None,
        )

    # 2. YES24 미연동 또는 미검색 시: 로컬 서재 및 전체 도서 풀 fallback
    if member_id:
        stmt = (
            select(LibraryBook)
            .where(
                LibraryBook.member_id == member_id,
                LibraryBook.deleted_at.is_(None),
                or_(
                    LibraryBook.title.ilike(f"%{search_keyword}%"),
                    LibraryBook.author.ilike(f"%{search_keyword}%"),
                    LibraryBook.subject.ilike(f"%{search_keyword}%"),
                ),
            )
            .limit(limit)
        )
        result = await db.execute(stmt)
        matched_member_book = result.scalars().first()
        if matched_member_book:
            return BookSearchResponse(
                query=search_keyword,
                total=1,
                items=[],
                already_registered=True,
                library_book=SearchLibraryBookDetail(
                    book_id=matched_member_book.id,
                    shelf_id=matched_member_book.shelf_id,
                    shelf_rank=matched_member_book.shelf_rank,
                    title=matched_member_book.title,
                    author=matched_member_book.author,
                    isbn=matched_member_book.isbn,
                    genre=matched_member_book.genre,
                    kdc=matched_member_book.kdc,
                    subject=matched_member_book.subject,
                    publisher=matched_member_book.publisher,
                    published_date=matched_member_book.published_date.isoformat()
                    if matched_member_book.published_date
                    else None,
                    total_pages=matched_member_book.total_pages,
                    cover_url=matched_member_book.cover_url,
                    reading_status=matched_member_book.reading_status,
                    current_page=matched_member_book.current_page,
                    description=matched_member_book.description,
                    genre_source=matched_member_book.genre_source,
                ),
                book=None,
            )

    # 전체 도서 풀에서 일치 도서 검색
    global_stmt = (
        select(LibraryBook)
        .where(
            LibraryBook.deleted_at.is_(None),
            or_(
                LibraryBook.title.ilike(f"%{search_keyword}%"),
                LibraryBook.author.ilike(f"%{search_keyword}%"),
            ),
        )
        .limit(1)
    )
    res = await db.execute(global_stmt)
    matched_book = res.scalars().first()
    if matched_book:
        return BookSearchResponse(
            query=search_keyword,
            total=1,
            items=[],
            already_registered=False,
            library_book=None,
            book=ExternalBook(
                title=matched_book.title,
                author=matched_book.author,
                isbn=matched_book.isbn,
                genre=matched_book.genre,
                kdc=matched_book.kdc,
                subject=matched_book.subject,
                publisher=matched_book.publisher,
                published_date=matched_book.published_date.isoformat()
                if matched_book.published_date
                else None,
                total_pages=matched_book.total_pages,
                cover_url=matched_book.cover_url,
                description=matched_book.description,
                genre_source=matched_book.genre_source,
            ),
        )

    return BookSearchResponse(
        query=search_keyword,
        total=0,
        items=[],
        already_registered=False,
        library_book=None,
        book=None,
    )


async def _search_by_isbn(
    db: AsyncSession,
    clean_isbn: str,
    member_id: uuid.UUID | None,
    query_str: str | None = None,
) -> BookSearchResponse:
    display_query = query_str or clean_isbn
    # 1. 내 서재에 이미 등록되어 있는지 확인
    registered_book = None
    if member_id:
        stmt = select(LibraryBook).where(
            LibraryBook.member_id == member_id,
            LibraryBook.isbn == clean_isbn,
            LibraryBook.deleted_at.is_(None),
        )
        result = await db.execute(stmt)
        registered_book = result.scalars().first()

    if registered_book:
        return BookSearchResponse(
            query=display_query,
            total=1,
            items=[],
            already_registered=True,
            library_book=SearchLibraryBookDetail(
                book_id=registered_book.id,
                shelf_id=registered_book.shelf_id,
                shelf_rank=registered_book.shelf_rank,
                title=registered_book.title,
                author=registered_book.author,
                isbn=registered_book.isbn,
                genre=registered_book.genre,
                kdc=registered_book.kdc,
                subject=registered_book.subject,
                publisher=registered_book.publisher,
                published_date=registered_book.published_date.isoformat()
                if registered_book.published_date
                else None,
                total_pages=registered_book.total_pages,
                cover_url=registered_book.cover_url,
                reading_status=registered_book.reading_status,
                current_page=registered_book.current_page,
                description=registered_book.description,
                genre_source=registered_book.genre_source,
                genre_confidence=registered_book.genre_confidence,
            ),
            book=None,
        )

    # 2. 미등록 도서인 경우 YES24 + 국립중앙도서관 API 병렬(asyncio.gather) 조회
    #    - YES24: 상세 줄거리(description), 실쪽수(total_pages), 고화질 표지(cover_url), 상품링크(link)
    #    - 국립도서관: 정식 KDC 분류기호(kdc), 세부 주제어(subject), 대분류(genre)
    async def fetch_yes24() -> BookSearchItem | None:
        try:
            return await yes24_client.lookup_by_isbn(clean_isbn)
        except Exception as e:
            logger.warning(f"YES24 lookup_by_isbn 예외 발생: {e} (ISBN: {clean_isbn})")
            return None

    async def fetch_nl() -> ExternalBook | None:
        try:
            return await client.lookup_by_isbn(clean_isbn)
        except Exception as e:
            logger.warning(
                f"국립중앙도서관 lookup_by_isbn 예외 발생: {e} (ISBN: {clean_isbn})"
            )
            return None

    yes24_item, nl_book = await asyncio.gather(fetch_yes24(), fetch_nl())

    external_book: ExternalBook | None = None
    if yes24_item and nl_book:
        # 양쪽 모두 성공 시: YES24(소개글, 쪽수, 표지, 링크) + 국립도서관(KDC, 장르, 주제어) 융합
        external_book = ExternalBook(
            title=yes24_item.title or nl_book.title,
            author=yes24_item.author or nl_book.author,
            isbn=clean_isbn,
            genre=nl_book.genre,
            kdc=nl_book.kdc,
            subject=nl_book.subject,
            publisher=yes24_item.publisher or nl_book.publisher,
            published_date=yes24_item.published_date or nl_book.published_date,
            total_pages=yes24_item.total_pages or nl_book.total_pages,
            cover_url=yes24_item.cover_url or nl_book.cover_url,
            side_cover_url=yes24_item.side_cover_url or nl_book.side_cover_url,
            description=yes24_item.description or nl_book.description,
            genre_source=nl_book.genre_source or "KDC",
            genre_confidence=None,
            link=yes24_item.link,
        )
    elif yes24_item:
        # YES24만 성공 시: 소개글/표지/쪽수 확보 및 KDC 매퍼로 1차 장르 추론
        inferred_genre, inferred_subject = parse_to_genre_and_subject(
            genre_input=None,
            current_subject=None,
            title=yes24_item.title,
        )
        external_book = ExternalBook(
            title=yes24_item.title,
            author=yes24_item.author,
            isbn=clean_isbn,
            genre=inferred_genre,
            kdc=None,
            subject=inferred_subject,
            publisher=yes24_item.publisher,
            published_date=yes24_item.published_date,
            total_pages=yes24_item.total_pages,
            cover_url=yes24_item.cover_url,
            side_cover_url=yes24_item.side_cover_url,
            description=yes24_item.description,
            genre_source="KDC",
            genre_confidence=None,
            link=yes24_item.link,
        )
    elif nl_book:
        # 국립도서관만 성공 시
        external_book = nl_book

    return BookSearchResponse(
        query=display_query,
        total=1 if external_book else 0,
        items=[],
        already_registered=False,
        library_book=None,
        book=external_book,
    )


@router.get(
    "/{book_id}",
    response_model=LibraryBookDetailResponse,
    summary="도서 단건 상세 조회 (AI 에이전트 및 통합 클라이언트 호환 별칭)",
)
async def get_book_by_id(
    book_id: int,
    member_id: uuid.UUID | None = Depends(get_optional_member_id),
    db: AsyncSession = Depends(get_db),
):
    return await BookService.get_book_detail_optional_member(db, book_id, member_id)
