import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_authenticated_member_id
from app.db.session import get_db
from app.schemas.reading_session import (
    BookReadingSessionListResponse,
    CreateReadingSessionRequest,
    ReadingSessionResponse,
)
from app.services.reading_session_service import ReadingSessionService

router = APIRouter(tags=["reading-sessions"])


@router.post(
    "/api/v1/reading-sessions",
    response_model=ReadingSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="스톱워치 독서 세션 기록 저장 및 도서 진도율 자동 동기화 (기존 레거시 경로)",
)
async def create_reading_session(
    request: CreateReadingSessionRequest,
    member_id: uuid.UUID = Depends(get_authenticated_member_id),
    db: AsyncSession = Depends(get_db),
):
    return await ReadingSessionService.create_session(db, member_id, request)


@router.post(
    "/api/v1/books/{book_id}/reading-sessions",
    response_model=ReadingSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="특정 도서의 독서 세션 기록 저장 및 도서 진도율 자동 동기화",
)
@router.post(
    "/api/v1/library/books/{book_id}/reading-sessions",
    response_model=ReadingSessionResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
async def create_book_reading_session(
    book_id: int,
    request: CreateReadingSessionRequest,
    member_id: uuid.UUID = Depends(get_authenticated_member_id),
    db: AsyncSession = Depends(get_db),
):
    return await ReadingSessionService.create_session(
        db, member_id, request, book_id_override=book_id
    )


@router.get(
    "/api/v1/books/{book_id}/reading-sessions",
    response_model=BookReadingSessionListResponse,
    status_code=status.HTTP_200_OK,
    summary="특정 도서의 독서 세션 목록 및 누적 독서 시간 조회",
)
@router.get(
    "/api/v1/library/books/{book_id}/reading-sessions",
    response_model=BookReadingSessionListResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
async def get_book_reading_sessions(
    book_id: int,
    member_id: uuid.UUID = Depends(get_authenticated_member_id),
    db: AsyncSession = Depends(get_db),
):
    return await ReadingSessionService.get_book_sessions(db, member_id, book_id)
