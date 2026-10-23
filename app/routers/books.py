import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import (
    DemoAccountProtectedException,
    GuestReadOnlyModeException,
)
from app.core.security import get_current_member_id
from app.db.session import get_db
from app.schemas.library_book import (
    BookCoverPresignedUrlData,
    BookCoverPresignedUrlRequest,
    BookCoverPresignedUrlResponse,
    CreateLibraryBookRequest,
    CreateLibraryBookResponse,
    LibraryBookDetailResponse,
    LibraryBookPageResponse,
    MoveBookShelfRequest,
    MoveBookShelfResponse,
    ReorderBookRequest,
    ReorderBookResponse,
    ShelfPlacementsResponse,
    ShelfPlacementsUpdateRequest,
    UpdateLibraryBookRequest,
    UpdateLibraryBookResponse,
    UpdateProgressRequest,
    UpdateProgressResponse,
)
from app.services.book_service import BookService
from app.services.storage_service import StorageService

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


@router.post(
    "/cover/presigned-url",
    response_model=BookCoverPresignedUrlResponse,
)
async def get_book_cover_presigned_url(
    request: BookCoverPresignedUrlRequest,
    member_id: uuid.UUID = Depends(get_current_member_id),
):
    """
    도서 직접 등록용 커스텀 표지 Cloudflare R2 Presigned PUT URL 발급
    - 게스트/데모 계정은 악의적 스토리지 점유 방지를 위해 발급이 차단됩니다 (403 Forbidden).
    - 반환된 uploadUrl로 클라이언트가 직접 R2 버킷에 PUT 요청하여 바이너리를 업로드합니다.
    """
    sub_str = str(member_id)
    if sub_str == settings.DEMO_MEMBER_ID:
        raise DemoAccountProtectedException(
            "데모 계정 보호 정책에 의해 도서 표지 업로드 URL을 발급받을 수 없습니다."
        )
    if sub_str == settings.GUEST_MEMBER_ID or sub_str.startswith("guest-"):
        raise GuestReadOnlyModeException(
            "체험 모드(게스트)에서는 도서 표지 업로드 URL을 발급받을 수 없습니다."
        )

    res = StorageService.generate_book_cover_presigned_url(
        member_id=member_id,
        content_type=request.content_type,
    )
    return BookCoverPresignedUrlResponse(
        status="success",
        data=BookCoverPresignedUrlData(**res),
    )


@router.get("", response_model=LibraryBookPageResponse)
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


@router.put("/shelf-placements", response_model=ShelfPlacementsResponse)
async def update_shelf_placements(
    request: ShelfPlacementsUpdateRequest,
    member_id: uuid.UUID = Depends(get_current_member_id),
    db: AsyncSession = Depends(get_db),
) -> ShelfPlacementsResponse:
    """
    선반별 도서 단/순서 일괄 업데이트
    - 3D 서재 드래그 앤 드롭 완료 시 도서의 선반 단(shelf_tier)과 단 내 순서(shelf_order)를 일괄 영속화합니다.
    - 단일 격리 트랜잭션 내에서 회원 소유권을 일괄 검증하며 타인 도서 조작 시 403 Forbidden으로 차단합니다.
    """
    return await BookService.update_shelf_placements(
        db=db,
        member_id=member_id,
        request=request,
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
