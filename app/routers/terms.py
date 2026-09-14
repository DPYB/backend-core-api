import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_member_id
from app.db.session import get_db
from app.schemas.terms import (
    TermsAgreementRequest,
    TermsAgreementResponse,
    TermsResponse,
)
from app.services.terms_service import TermsService

router = APIRouter(prefix="/api/v1/terms", tags=["terms"])


@router.get(
    "",
    response_model=list[TermsResponse],
    status_code=status.HTTP_200_OK,
    summary="활성 약관 목록 조회",
)
async def list_terms(
    db: AsyncSession = Depends(get_db),
) -> list[TermsResponse]:
    """현재 유효한 약관 3종(이용약관, 개인정보, AI분석동의 등) 목록을 조회합니다."""
    return await TermsService.get_active_terms(db)


@router.post(
    "/agreements",
    response_model=TermsAgreementResponse,
    status_code=status.HTTP_200_OK,
    summary="약관 동의 또는 철회 등록",
)
async def record_term_agreement(
    req: TermsAgreementRequest,
    member_id: uuid.UUID = Depends(get_current_member_id),
    db: AsyncSession = Depends(get_db),
) -> TermsAgreementResponse:
    """회원의 약관 동의 또는 철회 이력을 기록합니다."""
    return await TermsService.record_agreement(db, member_id, req.terms_id, req.action)
