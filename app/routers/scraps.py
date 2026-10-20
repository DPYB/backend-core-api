import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import (
    DemoAccountProtectedException,
    GuestReadOnlyModeException,
    InvalidFilterParameterException,
)
from app.core.security import get_current_member_id
from app.db.session import get_db
from app.schemas.scrap import (
    CreateScrapRequest,
    CreateScrapResponse,
    ScrapDetailResponse,
    ScrapImagePresignedUrlRequest,
    ScrapImagePresignedUrlResponse,
    ScrapPageResponse,
    UpdateScrapRequest,
    UpdateScrapResponse,
)
from app.services.scrap_service import ScrapService
from app.services.storage_service import StorageService

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


@router.post(
    "/scraps/presigned-url",
    response_model=ScrapImagePresignedUrlResponse,
)
async def get_scrap_image_presigned_url(
    request: ScrapImagePresignedUrlRequest,
    member_id: uuid.UUID = Depends(get_current_member_id),
):
    """
    스크랩 이미지 업로드용 Cloudflare R2 Presigned PUT URL 발급
    - 게스트/데모 계정은 악의적 스토리지 점유 방지를 위해 발급이 차단됩니다 (403 Forbidden).
    - 반환된 presignedUrl로 클라이언트가 직접 R2 버킷에 PUT 요청하여 바이너리를 업로드합니다.
    """
    sub_str = str(member_id)
    if sub_str == settings.DEMO_MEMBER_ID:
        raise DemoAccountProtectedException(
            "데모 계정 보호 정책에 의해 스크랩 사진 업로드 URL을 발급받을 수 없습니다."
        )
    if sub_str == settings.GUEST_MEMBER_ID or sub_str.startswith("guest-"):
        raise GuestReadOnlyModeException(
            "체험 모드(게스트)에서는 스크랩 사진 업로드 URL을 발급받을 수 없습니다."
        )

    res = StorageService.generate_scrap_image_presigned_url(
        member_id=member_id,
        content_type=request.content_type,
    )
    return ScrapImagePresignedUrlResponse(**res)


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
