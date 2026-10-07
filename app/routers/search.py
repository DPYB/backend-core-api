import re
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidSearchParameterException
from app.core.security import get_optional_member_id
from app.db.session import get_db
from app.models.library_book import LibraryBook
from app.schemas.library_book import LibraryBookDetailResponse
from app.schemas.search import (
    BookSearchResponse,
    ExternalBook,
    SearchLibraryBookDetail,
)
from app.services.book_service import BookService
from app.services.national_library import NationalLibraryClient
from app.services.yes24 import Yes24Client

router = APIRouter(prefix="/api/v1/books", tags=["Book Discovery"])
client = NationalLibraryClient()
yes24_client = Yes24Client()

ISBN_REGEX = re.compile(r"^(?:[0-9]{10}|[0-9]{13})$")


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
        if not clean_isbn or not ISBN_REGEX.match(clean_isbn):
            raise InvalidSearchParameterException(
                "올바른 10자리 또는 13자리 숫자 ISBN을 입력해주세요."
            )
        return await _search_by_isbn(db, clean_isbn, member_id)

    search_keyword = (query or "").strip()
    if not search_keyword:
        raise InvalidSearchParameterException(
            "올바른 10자리 또는 13자리 숫자 ISBN 또는 검색 키워드를 입력해주세요."
        )

    clean_digits = re.sub(r"[^0-9X]", "", search_keyword)
    if ISBN_REGEX.match(clean_digits):
        return await _search_by_isbn(db, clean_digits, member_id)

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
    db: AsyncSession, clean_isbn: str, member_id: uuid.UUID | None
) -> BookSearchResponse:
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
            query=clean_isbn,
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
            ),
            book=None,
        )

    # 2. 미등록 도서인 경우 국립중앙도서관 API 조회 (장애/타임아웃 시 graceful fallback)
    try:
        external_book = await client.lookup_by_isbn(clean_isbn)
    except Exception:
        external_book = None

    return BookSearchResponse(
        query=clean_isbn,
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
