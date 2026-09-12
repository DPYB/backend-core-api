import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_member_id
from app.db.session import get_db
from app.schemas.librarian import (
    AcquireLibrarianRequest,
    AcquireLibrarianResponse,
    LibrarianResponse,
    LibrarianTypeListResponse,
    RenameLibrarianRequest,
    RenameLibrarianResponse,
    RepresentativeLibrarianResponse,
)
from app.services.librarian_service import LibrarianService

router = APIRouter(prefix="/api/v1", tags=["Librarian"])


@router.get("/librarian-types", response_model=LibrarianTypeListResponse)
async def get_librarian_types(
    db: AsyncSession = Depends(get_db),
):
    return await LibrarianService.get_librarian_types(db)


@router.post(
    "/librarians",
    response_model=AcquireLibrarianResponse,
    status_code=status.HTTP_201_CREATED,
)
async def acquire_librarian(
    request: AcquireLibrarianRequest,
    member_id: uuid.UUID = Depends(get_current_member_id),
    db: AsyncSession = Depends(get_db),
):
    return await LibrarianService.acquire_librarian(db, member_id, request)


@router.get("/librarians", response_model=list[LibrarianResponse])
async def get_my_librarians(
    member_id: uuid.UUID = Depends(get_current_member_id),
    db: AsyncSession = Depends(get_db),
):
    return await LibrarianService.get_my_librarians(db, member_id)


# 주의: /librarians/representative 경로는 /librarians/{librarian_id} 보다 위에 정의
@router.get(
    "/librarians/representative",
    response_model=RepresentativeLibrarianResponse,
)
async def get_representative_librarian(
    member_id: uuid.UUID = Depends(get_current_member_id),
    db: AsyncSession = Depends(get_db),
):
    return await LibrarianService.get_representative_librarian(db, member_id)


@router.patch(
    "/librarians/{librarian_id}/representative",
    response_model=RepresentativeLibrarianResponse,
)
async def set_representative_librarian(
    librarian_id: int,
    member_id: uuid.UUID = Depends(get_current_member_id),
    db: AsyncSession = Depends(get_db),
):
    return await LibrarianService.set_representative_librarian(
        db, member_id, librarian_id
    )


@router.patch(
    "/librarians/{librarian_id}",
    response_model=RenameLibrarianResponse,
)
async def rename_librarian(
    librarian_id: int,
    request: RenameLibrarianRequest,
    member_id: uuid.UUID = Depends(get_current_member_id),
    db: AsyncSession = Depends(get_db),
):
    return await LibrarianService.rename_librarian(
        db, member_id, librarian_id, request.name
    )


@router.delete(
    "/librarians/{librarian_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_librarian(
    librarian_id: int,
    member_id: uuid.UUID = Depends(get_current_member_id),
    db: AsyncSession = Depends(get_db),
):
    await LibrarianService.delete_librarian(db, member_id, librarian_id)
