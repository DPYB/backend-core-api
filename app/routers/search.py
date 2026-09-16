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

router = APIRouter(prefix="/api/v1/books", tags=["Book Discovery"])
client = NationalLibraryClient()

ISBN_REGEX = re.compile(r"^(?:[0-9]{10}|[0-9]{13})$")


@router.get("/search", response_model=BookSearchResponse)
async def search_book(
    isbn: str | None = Query(None, description="10자리 또는 13자리 ISBN"),
    query: str | None = Query(None, description="도서명 또는 검색 키워드"),
    limit: int = Query(5, ge=1, le=20, description="최대 반환 도서 수"),
    member_id: uuid.UUID | None = Depends(get_optional_member_id),
    db: AsyncSession = Depends(get_db),
):
    """
    도서 검색 API (ISBN 단건 검색 및 키워드 통합 검색 지원).
    - isbn 제공 시: 국립중앙도서관 정식 서지정보 및 내 서재 등록 여부 반환
    - query 제공 시: 내 서재 및 도서 풀에서 일치 도서 검색
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

    # 일반 키워드 검색 (회원 서재 우선 검색)
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
            ),
        )

    return BookSearchResponse(
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
            ),
            book=None,
        )

    # 2. 미등록 도서인 경우 국립중앙도서관 API 조회 (장애/타임아웃 시 graceful fallback)
    try:
        external_book = await client.lookup_by_isbn(clean_isbn)
    except Exception:
        external_book = None

    return BookSearchResponse(
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
