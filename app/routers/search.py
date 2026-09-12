import re
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidSearchParameterException
from app.core.security import get_current_member_id
from app.db.session import get_db
from app.models.library_book import LibraryBook
from app.schemas.search import (
    BookSearchResponse,
    SearchLibraryBookDetail,
)
from app.services.national_library import NationalLibraryClient

router = APIRouter(prefix="/api/v1/books", tags=["Book Discovery"])
client = NationalLibraryClient()

ISBN_REGEX = re.compile(r"^(?:[0-9]{10}|[0-9]{13})$")


@router.get("/search", response_model=BookSearchResponse)
async def search_book_by_isbn(
    isbn: str = Query(..., description="10자리 또는 13자리 ISBN"),
    member_id: uuid.UUID = Depends(get_current_member_id),
    db: AsyncSession = Depends(get_db),
):
    if not isbn or not ISBN_REGEX.match(isbn.strip()):
        raise InvalidSearchParameterException(
            "올바른 10자리 또는 13자리 숫자 ISBN을 입력해주세요."
        )

    clean_isbn = isbn.strip()

    # 1. 내 서재에 이미 등록되어 있는지 확인
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

    # 2. 미등록 도서인 경우 국립중앙도서관 API 조회
    external_book = await client.lookup_by_isbn(clean_isbn)

    return BookSearchResponse(
        already_registered=False,
        library_book=None,
        book=external_book,
    )
