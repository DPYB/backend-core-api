from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ScrapCreateDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    sentence: str
    page_number: int | None = None
    memo: str | None = None
    scrap_image_url: str | None = None


class ScrapResponseDto(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    sentence: str
    page_number: int | None = None
    memo: str | None = None
    scrap_image_url: str | None = None


class RecordCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    book_id: int = Field(..., description="대상 도서 식별자")
    title: str = Field(
        ..., min_length=1, max_length=255, description="독서 감상평 제목"
    )
    content: str = Field(..., min_length=1, description="독서 감상평 본문")
    rating: int | None = Field(default=None, ge=1, le=5, description="별점 (1~5)")
    read_at: datetime | None = Field(default=None, description="완독 일시")
    weather: str | None = Field(
        default=None, max_length=50, description="작성 당시 날씨"
    )
    scraps: list[ScrapCreateDto] = Field(
        default_factory=list, description="함께 저장할 문장 스크랩 목록"
    )


class RecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    member_id: UUID
    book_id: int
    title: str
    content: str
    rating: int | None = None
    read_at: datetime | None = None
    weather: str | None = None
    created_at: datetime
    scraps: list[ScrapResponseDto] = []
