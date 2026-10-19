import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import (
    DemoAccountProtectedException,
    GuestReadOnlyModeException,
)
from app.core.security import get_current_member_id
from app.db.session import get_db
from app.schemas.member import (
    MemberProfileResponse,
    ProfileImagePresignedUrlRequest,
    ProfileImagePresignedUrlResponse,
    UpdateProfileRequest,
)
from app.services.member_service import MemberService
from app.services.storage_service import StorageService

router = APIRouter(tags=["users"])


@router.get(
    "/api/v1/users/me",
    response_model=MemberProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="내 프로필 조회",
)
@router.get(
    "/api/v1/members/me",
    response_model=MemberProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="내 프로필 조회 (별칭)",
    include_in_schema=False,
)
async def get_my_profile(
    member_id: uuid.UUID = Depends(get_current_member_id),
    db: AsyncSession = Depends(get_db),
) -> MemberProfileResponse:
    """현재 인증된 회원의 프로필 정보를 조회합니다."""
    return await MemberService.get_profile(db, member_id)


@router.post(
    "/api/v1/users/me/profile-image/presigned-url",
    response_model=ProfileImagePresignedUrlResponse,
    status_code=status.HTTP_200_OK,
    summary="프로필 이미지 업로드용 Presigned URL 발급",
)
@router.post(
    "/api/v1/members/me/profile-image/presigned-url",
    response_model=ProfileImagePresignedUrlResponse,
    status_code=status.HTTP_200_OK,
    summary="프로필 이미지 업로드용 Presigned URL 발급 (별칭)",
    include_in_schema=False,
)
async def create_profile_image_presigned_url(
    req: ProfileImagePresignedUrlRequest,
    member_id: uuid.UUID = Depends(get_current_member_id),
) -> ProfileImagePresignedUrlResponse:
    """
    Cloudflare R2 스토리지에 프로필 이미지를 직접 업로드할 수 있는 10분 유효기간의 Presigned PUT URL을 발급합니다.
    - 허용 Content-Type: image/webp, image/jpeg, image/png, image/gif
    - 게스트 및 데모 계정은 정책상 발급이 제한됩니다.
    """
    sub_str = str(member_id)
    if sub_str == settings.DEMO_MEMBER_ID:
        raise DemoAccountProtectedException(
            "데모 계정 보호 정책에 의해 프로필 사진 업로드 URL을 발급받을 수 없습니다."
        )
    if sub_str == settings.GUEST_MEMBER_ID or sub_str.startswith("guest-"):
        raise GuestReadOnlyModeException(
            "체험 모드(게스트)에서는 프로필 사진 업로드 URL을 발급받을 수 없습니다."
        )

    res = StorageService.generate_profile_image_presigned_url(
        member_id=member_id,
        content_type=req.content_type,
    )
    return ProfileImagePresignedUrlResponse(
        presigned_url=res["presigned_url"],
        image_url=res["image_url"],
        expires_in=res["expires_in"],
    )


@router.patch(
    "/api/v1/users/me",
    response_model=MemberProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="내 프로필 수정",
)
@router.patch(
    "/api/v1/members/me",
    response_model=MemberProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="내 프로필 수정 (별칭)",
    include_in_schema=False,
)
async def update_my_profile(
    req: UpdateProfileRequest,
    member_id: uuid.UUID = Depends(get_current_member_id),
    db: AsyncSession = Depends(get_db),
) -> MemberProfileResponse:
    """회원의 닉네임, 프로필 사진, 생년월일, 성별을 수정합니다."""
    return await MemberService.update_profile(db, member_id, req)


@router.delete(
    "/api/v1/users/me",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="회원 탈퇴",
)
@router.delete(
    "/api/v1/members/me",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="회원 탈퇴 (별칭)",
    include_in_schema=False,
)
async def withdraw(
    member_id: uuid.UUID = Depends(get_current_member_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    회원 탈퇴를 처리하고, 소속된 모든 서재 도서, 스크랩, 독서기록, 사서 데이터를 일괄 소프트 삭제합니다.
    """
    await MemberService.withdraw_member(db, member_id)
