import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_authenticated_member_id
from app.db.session import get_db
from app.schemas.reading_session import (
    CreateReadingSessionRequest,
    ReadingSessionResponse,
)
from app.services.reading_session_service import ReadingSessionService

router = APIRouter(prefix="/api/v1/reading-sessions", tags=["reading-sessions"])


@router.post(
    "",
    response_model=ReadingSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="스톱워치 독서 세션 기록 저장 및 도서 진도율 자동 동기화",
)
async def create_reading_session(
    request: CreateReadingSessionRequest,
    member_id: uuid.UUID = Depends(get_authenticated_member_id),
    db: AsyncSession = Depends(get_db),
):
    return await ReadingSessionService.create_session(db, member_id, request)
