import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_member_id
from app.db.session import get_db
from app.schemas.member import MemberProfileResponse, UpdateProfileRequest
from app.services.member_service import MemberService

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.get(
    "/me",
    response_model=MemberProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="내 프로필 조회",
)
async def get_my_profile(
    member_id: uuid.UUID = Depends(get_current_member_id),
    db: AsyncSession = Depends(get_db),
) -> MemberProfileResponse:
    """현재 인증된 회원의 프로필 정보를 조회합니다."""
    return await MemberService.get_profile(db, member_id)


@router.patch(
    "/me",
    response_model=MemberProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="내 프로필 수정",
)
async def update_my_profile(
    req: UpdateProfileRequest,
    member_id: uuid.UUID = Depends(get_current_member_id),
    db: AsyncSession = Depends(get_db),
) -> MemberProfileResponse:
    """회원의 닉네임, 프로필 사진, 생년월일, 성별을 수정합니다."""
    return await MemberService.update_profile(db, member_id, req)


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="회원 탈퇴",
)
async def withdraw(
    member_id: uuid.UUID = Depends(get_current_member_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    회원 탈퇴를 처리하고, 소속된 모든 서재 도서, 스크랩, 독서기록, 사서 데이터를 일괄 소프트 삭제합니다.
    """
    await MemberService.withdraw_member(db, member_id)
