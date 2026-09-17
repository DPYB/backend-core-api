from datetime import datetime
from uuid import UUID

from pydantic import Field, model_validator

from app.models.enums import BookReadingStatus
from app.schemas.common import CamelModel


class CreateReadingSessionRequest(CamelModel):
    book_id: int | None = Field(
        default=None, description="대상 도서 ID (미선택 시 자유 독서)"
    )
    duration_seconds: int | None = Field(
        default=None, ge=1, description="독서 집중 시간 (초 단위)"
    )
    duration_minutes: int | None = Field(
        default=None, ge=1, le=1440, description="스톱워치 독서 소요 시간 (분 단위)"
    )
    start_time: datetime | None = Field(default=None, description="세션 시작 시각")
    end_time: datetime | None = Field(default=None, description="세션 종료 시각")
    start_page: int | None = Field(default=None, ge=0, description="독서 시작 페이지")
    end_page: int | None = Field(default=None, ge=0, description="독서 종료 페이지")
    memo: str | None = Field(default=None, description="당시 한 줄 감상/메모")
    weather: str | None = Field(
        default=None, max_length=50, description="독서 당시 날씨 condition"
    )

    @model_validator(mode="before")
    @classmethod
    def resolve_duration_and_pages(cls, data: object) -> object:
        if isinstance(data, dict):
            # duration_seconds 또는 duration (초 단위) 호환
            if "duration_seconds" not in data and "durationSeconds" not in data:
                if "duration" in data:
                    data["duration_seconds"] = data["duration"]
                elif "duration_minutes" in data or "durationMinutes" in data:
                    mins = data.get("duration_minutes") or data.get("durationMinutes")
                    if mins is not None:
                        data["duration_seconds"] = int(mins) * 60

            # duration_minutes 호환
            if "duration_minutes" not in data and "durationMinutes" not in data:
                secs = data.get("duration_seconds") or data.get("durationSeconds")
                if secs is not None:
                    data["duration_minutes"] = max(1, int(secs) // 60)

            # page_number / pageNumber -> end_page 매핑 호환
            if "end_page" not in data and "endPage" not in data:
                pn = data.get("page_number") or data.get("pageNumber")
                if pn is not None:
                    data["end_page"] = pn

        return data


class ReadingSessionResponse(CamelModel):
    id: int
    member_id: UUID
    book_id: int | None = None
    duration_seconds: int
    duration_minutes: int
    start_time: datetime | None = None
    end_time: datetime | None = None
    start_page: int | None = None
    end_page: int | None = None
    memo: str | None = None
    weather: str | None = None
    created_at: datetime
    updated_at: datetime | None = None
    book_title: str | None = None
    updated_current_page: int | None = None
    progress: float | None = None
    book_reading_status: BookReadingStatus | None = None


class BookReadingSessionListResponse(CamelModel):
    book_id: int
    total_duration_seconds: int = Field(description="해당 도서의 누적 독서 시간 (초)")
    total_duration_minutes: int = Field(description="해당 도서의 누적 독서 시간 (분)")
    session_count: int = Field(description="해당 도서의 총 세션 수")
    sessions: list[ReadingSessionResponse] = Field(
        description="독서 세션 목록 (최신순)"
    )
