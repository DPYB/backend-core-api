import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidFilterParameterException
from app.core.security import get_current_member_id
from app.db.session import get_db
from app.schemas.scrap import (
    CreateScrapRequest,
    CreateScrapResponse,
    ScrapDetailResponse,
    ScrapPageResponse,
    UpdateScrapRequest,
    UpdateScrapResponse,
)
from app.services.scrap_service import ScrapService

router = APIRouter(prefix="/api/v1/library", tags=["Scrap"])


@router.post(
    "/books/{book_id}/scraps",
    response_model=CreateScrapResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_scrap(
    book_id: int,
    request: CreateScrapRequest,
    member_id: uuid.UUID = Depends(get_current_member_id),
    db: AsyncSession = Depends(get_db),
):
    return await ScrapService.create_scrap(db, member_id, book_id, request)


@router.get(
    "/books/{book_id}/scraps",
    response_model=ScrapPageResponse,
)
async def get_book_scraps(
    book_id: int,
    page: int = Query(0, ge=0),
    size: int = Query(20, ge=1, le=100),
    member_id: uuid.UUID = Depends(get_current_member_id),
    db: AsyncSession = Depends(get_db),
):
    return await ScrapService.get_book_scraps(db, member_id, book_id, page, size)


@router.get(
    "/scraps",
    response_model=ScrapPageResponse,
)
async def get_scraps_by_query(
    book_id: int | None = Query(None, alias="bookId"),
    page: int = Query(0, ge=0),
    size: int = Query(20, ge=1, le=100),
    member_id: uuid.UUID = Depends(get_current_member_id),
    db: AsyncSession = Depends(get_db),
):
    if book_id is None:
        raise InvalidFilterParameterException("bookId 쿼리 파라미터가 필요합니다.")
    return await ScrapService.get_book_scraps(db, member_id, book_id, page, size)


@router.get("/scraps/{scrap_id}", response_model=ScrapDetailResponse)
async def get_scrap(
    scrap_id: int,
    member_id: uuid.UUID = Depends(get_current_member_id),
    db: AsyncSession = Depends(get_db),
):
    return await ScrapService.get_scrap_detail(db, member_id, scrap_id)


@router.patch("/scraps/{scrap_id}", response_model=UpdateScrapResponse)
async def update_scrap(
    scrap_id: int,
    request: UpdateScrapRequest,
    member_id: uuid.UUID = Depends(get_current_member_id),
    db: AsyncSession = Depends(get_db),
):
    return await ScrapService.update_scrap(db, member_id, scrap_id, request)


@router.delete("/scraps/{scrap_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scrap(
    scrap_id: int,
    member_id: uuid.UUID = Depends(get_current_member_id),
    db: AsyncSession = Depends(get_db),
):
    await ScrapService.delete_scrap(db, member_id, scrap_id)
