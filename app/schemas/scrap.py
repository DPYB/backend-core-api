from datetime import datetime

from pydantic import Field, field_validator

from app.core.exceptions import InvalidScrapDataException
from app.schemas.common import CamelModel


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
