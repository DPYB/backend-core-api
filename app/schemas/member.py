from datetime import date, datetime

from pydantic import Field

from app.models.enums import LibrarianType
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
    librarian_type: LibrarianType | None = None
    librarian_name: str | None = None
    librarian_default_name: str | None = None
    created_at: datetime


class UpdateProfileRequest(CamelModel):
    """회원 프로필 수정 요청"""

    nickname: str | None = Field(
        None, min_length=2, max_length=50, description="새 닉네임"
    )
    profile_image_url: str | None = Field(None, description="프로필 이미지 URL")
    birth_date: date | None = Field(None, description="생년월일 (YYYY-MM-DD)")
    gender: str | None = Field(None, description="성별 (MALE, FEMALE)")


class ProfileImagePresignedUrlRequest(CamelModel):
    """프로필 이미지 Presigned URL 발급 요청"""

    content_type: str = Field(
        default="image/webp",
        description="업로드할 이미지 Content-Type (image/webp, image/jpeg, image/png, image/gif)",
    )


class ProfileImagePresignedUrlResponse(CamelModel):
    """프로필 이미지 Presigned URL 발급 응답"""

    presigned_url: str = Field(..., description="Cloudflare R2 Presigned PUT URL")
    image_url: str = Field(..., description="최종 CDN 이미지 접근 URL")
    expires_in: int = Field(default=600, description="Presigned URL 유효 시간 (초)")
