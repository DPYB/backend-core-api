from datetime import datetime

from pydantic import Field, computed_field, field_validator

from app.core.exceptions import InvalidScrapDataException
from app.schemas.common import CamelModel, PaginatedResponse


class CreateScrapRequest(CamelModel):
    sentence: str = Field(..., description="스크랩 문장")
    page_number: int | None = Field(None, ge=1, description="페이지 번호")
    scrap_image_url: str = Field(..., description="스크랩 이미지 URL")
    memo: str | None = Field(None, description="메모")

    @field_validator("sentence")
    @classmethod
    def validate_sentence(cls, v: str) -> str:
        if not v or not v.strip():
            raise InvalidScrapDataException("스크랩 문장은 공백일 수 없습니다.")
        return v.strip()

    @field_validator("scrap_image_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not v or not v.strip():
            raise InvalidScrapDataException("스크랩 이미지 URL은 필수입니다.")
        return v.strip()


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
    scrap_image_url: str = Field(..., description="스크랩 이미지 URL")
    memo: str | None = Field(None, description="메모")

    @field_validator("sentence")
    @classmethod
    def validate_sentence(cls, v: str) -> str:
        if not v or not v.strip():
            raise InvalidScrapDataException("스크랩 문장은 공백일 수 없습니다.")
        return v.strip()

    @field_validator("scrap_image_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not v or not v.strip():
            raise InvalidScrapDataException("스크랩 이미지 URL은 필수입니다.")
        return v.strip()


class UpdateScrapResponse(CamelModel):
    scrap_id: int
    book_id: int
    sentence: str
    page_number: int | None = None
    scrap_image_url: str
    memo: str | None = None
    updated_at: datetime
