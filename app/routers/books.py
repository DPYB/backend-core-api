import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_member_id
from app.db.session import get_db
from app.schemas.common import PaginatedResponse
from app.schemas.library_book import (
    CreateLibraryBookRequest,
    CreateLibraryBookResponse,
    LibraryBookDetailResponse,
    LibraryBookItemResponse,
    MoveBookShelfRequest,
    MoveBookShelfResponse,
    ReorderBookRequest,
    ReorderBookResponse,
    UpdateLibraryBookRequest,
    UpdateLibraryBookResponse,
    UpdateProgressRequest,
    UpdateProgressResponse,
)
from app.services.book_service import BookService

router = APIRouter(prefix="/api/v1/library/books", tags=["Library Book"])


@router.post(
    "", response_model=CreateLibraryBookResponse, status_code=status.HTTP_201_CREATED
)
async def create_book(
    request: CreateLibraryBookRequest,
    member_id: uuid.UUID = Depends(get_current_member_id),
    db: AsyncSession = Depends(get_db),
):
    return await BookService.create_book(db, member_id, request)


@router.get("", response_model=PaginatedResponse[LibraryBookItemResponse])
async def list_books(
    shelf_id: int | None = Query(None, alias="shelfId"),
    author: str | None = Query(None),
    reading_status: str | None = Query(None, alias="readingStatus"),
    genre: str | None = Query(None),
    sort_by: str = Query("SHELF_ORDER", alias="sortBy"),
    sort_order: str = Query("ASC", alias="sortOrder"),
    page: int = Query(0, ge=0),
    size: int = Query(20, ge=1, le=100),
    member_id: uuid.UUID = Depends(get_current_member_id),
    db: AsyncSession = Depends(get_db),
):
    return await BookService.get_books(
        db=db,
        member_id=member_id,
        shelf_id=shelf_id,
        author=author,
        reading_status=reading_status,
        genre=genre,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        size=size,
    )


@router.get("/{book_id}", response_model=LibraryBookDetailResponse)
async def get_book(
    book_id: int,
    member_id: uuid.UUID = Depends(get_current_member_id),
    db: AsyncSession = Depends(get_db),
):
    return await BookService.get_book_detail(db, member_id, book_id)


@router.patch("/{book_id}", response_model=UpdateLibraryBookResponse)
async def update_book(
    book_id: int,
    request: UpdateLibraryBookRequest,
    member_id: uuid.UUID = Depends(get_current_member_id),
    db: AsyncSession = Depends(get_db),
):
    return await BookService.update_book(db, member_id, book_id, request)


@router.delete("/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_book(
    book_id: int,
    member_id: uuid.UUID = Depends(get_current_member_id),
    db: AsyncSession = Depends(get_db),
):
    await BookService.delete_book(db, member_id, book_id)


@router.patch("/{book_id}/order", response_model=ReorderBookResponse)
async def reorder_book(
    book_id: int,
    request: ReorderBookRequest,
    member_id: uuid.UUID = Depends(get_current_member_id),
    db: AsyncSession = Depends(get_db),
):
    return await BookService.reorder_book(
        db,
        member_id,
        book_id,
        request.before_book_id,
        request.after_book_id,
    )


@router.patch("/{book_id}/shelf", response_model=MoveBookShelfResponse)
async def move_book_shelf(
    book_id: int,
    request: MoveBookShelfRequest,
    member_id: uuid.UUID = Depends(get_current_member_id),
    db: AsyncSession = Depends(get_db),
):
    return await BookService.move_book_shelf(
        db, member_id, book_id, request.target_shelf_id
    )


@router.patch("/{book_id}/progress", response_model=UpdateProgressResponse)
async def update_progress(
    book_id: int,
    request: UpdateProgressRequest,
    member_id: uuid.UUID = Depends(get_current_member_id),
    db: AsyncSession = Depends(get_db),
):
    return await BookService.update_progress(
        db, member_id, book_id, request.current_page
    )
