import math
import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ShelfAccessDeniedException,
    ShelfNotFoundException,
)
from app.core.security import get_current_member_id
from app.db.session import get_db
from app.models.library_book import LibraryBook
from app.models.shelf import Shelf
from app.schemas.common import PaginatedResponse
from app.schemas.library_book import LibraryBookItemResponse
from app.schemas.shelf import (
    CreateShelfRequest,
    CreateShelfResponse,
    ShelfListResponse,
    UpdateShelfRequest,
    UpdateShelfResponse,
)
from app.services.shelf_service import ShelfService

router = APIRouter(prefix="/api/v1/library/shelves", tags=["Shelf"])


@router.post(
    "", response_model=CreateShelfResponse, status_code=status.HTTP_201_CREATED
)
async def create_shelf(
    request: CreateShelfRequest,
    member_id: uuid.UUID = Depends(get_current_member_id),
    db: AsyncSession = Depends(get_db),
):
    return await ShelfService.create_shelf(db, member_id, request.name)


@router.get("", response_model=ShelfListResponse)
async def list_shelves(
    member_id: uuid.UUID = Depends(get_current_member_id),
    db: AsyncSession = Depends(get_db),
):
    return await ShelfService.get_shelves(db, member_id)


@router.patch("/{shelf_id}", response_model=UpdateShelfResponse)
async def update_shelf(
    shelf_id: int,
    request: UpdateShelfRequest,
    member_id: uuid.UUID = Depends(get_current_member_id),
    db: AsyncSession = Depends(get_db),
):
    return await ShelfService.update_shelf(db, member_id, shelf_id, request.name)


@router.delete("/{shelf_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_shelf(
    shelf_id: int,
    member_id: uuid.UUID = Depends(get_current_member_id),
    db: AsyncSession = Depends(get_db),
):
    await ShelfService.delete_shelf(db, member_id, shelf_id)


@router.get(
    "/{shelf_id}/books", response_model=PaginatedResponse[LibraryBookItemResponse]
)
async def get_shelf_books(
    shelf_id: int,
    page: int = Query(0, ge=0),
    size: int = Query(20, ge=1, le=100),
    member_id: uuid.UUID = Depends(get_current_member_id),
    db: AsyncSession = Depends(get_db),
):
    # 책장 소유권 확인
    shelf_stmt = select(Shelf).where(Shelf.id == shelf_id, Shelf.deleted_at.is_(None))
    shelf = (await db.execute(shelf_stmt)).scalars().first()
    if not shelf:
        raise ShelfNotFoundException("책장을 찾을 수 없습니다.")
    if shelf.member_id != member_id:
        raise ShelfAccessDeniedException("해당 책장에 대한 접근 권한이 없습니다.")

    # 총 개수
    count_stmt = select(func.count(LibraryBook.id)).where(
        LibraryBook.shelf_id == shelf_id,
        LibraryBook.deleted_at.is_(None),
    )
    total_elements = (await db.execute(count_stmt)).scalar() or 0
    total_pages = math.ceil(total_elements / size) if total_elements > 0 else 0

    # 페이징 조회 (shelf_rank ASC 고정)
    books_stmt = (
        select(LibraryBook)
        .where(
            LibraryBook.shelf_id == shelf_id,
            LibraryBook.deleted_at.is_(None),
        )
        .order_by(LibraryBook.shelf_rank.asc())
        .offset(page * size)
        .limit(size)
    )
    books = (await db.execute(books_stmt)).scalars().all()

    items = [
        LibraryBookItemResponse(
            book_id=b.id,
            shelf_id=b.shelf_id,
            shelf_rank=b.shelf_rank,
            title=b.title,
            author=b.author,
            isbn=b.isbn,
            genre=b.genre,
            kdc=b.kdc,
            subject=b.subject,
            publisher=b.publisher,
            cover_url=b.cover_url,
            reading_status=b.reading_status,
            current_page=b.current_page,
            total_pages=b.total_pages,
            created_at=b.created_at,
        )
        for b in books
    ]

    return PaginatedResponse[LibraryBookItemResponse](
        items=items,
        page=page,
        size=size,
        total_elements=total_elements,
        total_pages=total_pages,
        has_previous=page > 0,
        has_next=page < (total_pages - 1),
    )
