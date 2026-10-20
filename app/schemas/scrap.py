from datetime import datetime

from pydantic import Field, computed_field, field_validator

from app.core.exceptions import InvalidScrapDataException
from app.schemas.common import CamelModel, PaginatedResponse


class ScrapImagePresignedUrlRequest(CamelModel):
    """스크랩 이미지 Presigned URL 발급 요청"""

    content_type: str = Field(
        default="image/webp",
        description="업로드할 이미지 Content-Type (image/webp, image/jpeg, image/png, image/gif)",
    )


class ScrapImagePresignedUrlResponse(CamelModel):
    """스크랩 이미지 Presigned URL 발급 응답"""

    presigned_url: str = Field(..., description="Cloudflare R2 Presigned PUT URL")
    image_url: str = Field(..., description="최종 CDN 이미지 접근 URL")
    expires_in: int = Field(default=600, description="Presigned URL 유효 시간 (초)")


class CreateScrapRequest(CamelModel):
    sentence: str = Field(..., description="스크랩 문장")
    page_number: int | None = Field(None, ge=1, description="페이지 번호")
    scrap_image_url: str = Field(
        "", max_length=2_000_000, description="스크랩 이미지 URL 또는 Base64 Data URL"
    )
    memo: str | None = Field(None, description="메모")

    @field_validator("sentence")
    @classmethod
    def validate_sentence(cls, v: str) -> str:
        if not v or not v.strip():
            raise InvalidScrapDataException("스크랩 문장은 공백일 수 없습니다.")
        return v.strip()

    @field_validator("scrap_image_url")
    @classmethod
    def validate_url(cls, v: str | None) -> str:
        if v is None:
            return ""
        val = v.strip()
        if len(val) > 2_000_000:
            raise ValueError("스크랩 이미지 데이터 크기는 2MB를 초과할 수 없습니다.")
        return val


class CreateScrapResponse(CamelModel):
    scrap_id: int
    book_id: int
    sentence: str
    page_number: int | None = None
    scrap_image_url: str
    memo: str | None = None
    created_at: datetime


class ScrapResponse(CamelModel):
    scrap_id: int
    book_id: int
    sentence: str
    page_number: int | None = None
    scrap_image_url: str
    memo: str | None = None
    created_at: datetime


class ScrapPageResponse(PaginatedResponse[ScrapResponse]):
    @computed_field
    @property
    def scraps(self) -> list[ScrapResponse]:
        """프론트엔드(frontend-reader-web) 및 레거시 클라이언트 호환 필드"""
        return self.items


class ScrapDetailResponse(CamelModel):
    scrap_id: int
    book_id: int
    sentence: str
    page_number: int | None = None
    scrap_image_url: str
    memo: str | None = None
    created_at: datetime
    updated_at: datetime


class UpdateScrapRequest(CamelModel):
    sentence: str = Field(..., description="스크랩 문장")
    page_number: int | None = Field(None, ge=1, description="페이지 번호")
    scrap_image_url: str = Field(
        "", max_length=2_000_000, description="스크랩 이미지 URL 또는 Base64 Data URL"
    )
    memo: str | None = Field(None, description="메모")

    @field_validator("sentence")
    @classmethod
    def validate_sentence(cls, v: str) -> str:
        if not v or not v.strip():
            raise InvalidScrapDataException("스크랩 문장은 공백일 수 없습니다.")
        return v.strip()

    @field_validator("scrap_image_url")
    @classmethod
    def validate_url(cls, v: str | None) -> str:
        if v is None:
            return ""
        val = v.strip()
        if len(val) > 2_000_000:
            raise ValueError("스크랩 이미지 데이터 크기는 2MB를 초과할 수 없습니다.")
        return val


class UpdateScrapResponse(CamelModel):
    scrap_id: int
    book_id: int
    sentence: str
    page_number: int | None = None
    scrap_image_url: str
    memo: str | None = None
    updated_at: datetime
