from datetime import date, datetime

from pydantic import Field

from app.schemas.common import CamelModel


class MemberProfileResponse(CamelModel):
    """회원 본인 프로필 응답"""

    member_id: str
    email: str
    nickname: str
    profile_image_url: str | None = None
    birth_date: date | None = None
    gender: str | None = None
    status: str
    provider: str | None = None
    created_at: datetime


class UpdateProfileRequest(CamelModel):
    """회원 프로필 수정 요청"""

    nickname: str | None = Field(
        None, min_length=2, max_length=50, description="새 닉네임"
    )
    profile_image_url: str | None = Field(None, description="프로필 이미지 URL")
    birth_date: date | None = Field(None, description="생년월일 (YYYY-MM-DD)")
    gender: str | None = Field(None, description="성별 (MALE, FEMALE)")
