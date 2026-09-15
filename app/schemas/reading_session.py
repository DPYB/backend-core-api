from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.models.enums import BookReadingStatus
from app.schemas.common import CamelModel


class CreateReadingSessionRequest(CamelModel):
    book_id: int | None = Field(
        default=None, description="대상 도서 ID (미선택 시 자유 독서)"
    )
    duration_minutes: int = Field(
        ...,
        ge=1,
        le=1440,
        description="스톱워치 독서 소요 시간 (분)",
    )
    start_page: int | None = Field(default=None, ge=0, description="독서 시작 페이지")
    end_page: int | None = Field(default=None, ge=0, description="독서 종료 페이지")
    weather: str | None = Field(
        default=None, max_length=50, description="독서 당시 날씨 condition"
    )


class ReadingSessionResponse(CamelModel):
    id: int
    member_id: UUID
    book_id: int | None = None
    duration_minutes: int
    start_page: int | None = None
    end_page: int | None = None
    weather: str | None = None
    created_at: datetime
    book_title: str | None = None
    updated_current_page: int | None = None
    book_reading_status: BookReadingStatus | None = None
