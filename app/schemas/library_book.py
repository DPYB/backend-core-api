from datetime import date, datetime

from pydantic import Field, computed_field, model_validator

from app.core.exceptions import InvalidReorderTargetException
from app.core.kdc_mapper import (
    GENRE_KOREAN_NAMES,
    parse_to_genre_and_subject,
)
from app.models.enums import BookReadingStatus, GenreType
from app.schemas.common import CamelModel, PaginatedResponse


class CreateLibraryBookRequest(CamelModel):
    title: str = Field(..., min_length=1, max_length=200)
    author: str = Field(..., min_length=1, max_length=100)
    isbn: str | None = Field(None, max_length=13)
    genre: GenreType = GenreType.NONE
    kdc: str | None = Field(None, max_length=20)
    subject: str | None = Field(None, max_length=100)
    publisher: str | None = Field(None, max_length=100)
    published_date: date | None = None
    cover_url: str | None = None
    reading_status: BookReadingStatus = BookReadingStatus.PLANNED
    total_pages: int | None = Field(None, ge=1)
    current_page: int = Field(0, ge=0)
    shelf_id: int | None = None

    @model_validator(mode="before")
    @classmethod
    def parse_genre_and_subject(cls, data: object) -> object:
        if isinstance(data, dict):
            raw_genre = data.get("genre", GenreType.NONE)
            raw_subject = data.get("subject")
            raw_kdc = data.get("kdc")

            parsed_genre, inferred_subject = parse_to_genre_and_subject(
                raw_genre, current_subject=raw_subject, kdc_str=raw_kdc
            )
            data["genre"] = parsed_genre
            data["subject"] = inferred_subject
        return data


class CreateLibraryBookResponse(CamelModel):
    book_id: int
    shelf_id: int
    shelf_rank: str
    title: str
    author: str
    isbn: str | None = None
    genre: GenreType
    kdc: str | None = None
    subject: str | None = None
    publisher: str | None = None
    published_date: date | None = None
    cover_url: str | None = None
    reading_status: BookReadingStatus
    current_page: int
    total_pages: int | None = None
    created_at: datetime
    completed_at: datetime | None = None

    @computed_field
    @property
    def genre_name(self) -> str:
        return GENRE_KOREAN_NAMES.get(self.genre, "기타/미분류")

    @computed_field
    @property
    def display_genre(self) -> str:
        """사용자 화면 표시용 우선 라벨 (세부 주제 subject 우선, 없을 때 대분류 genreName)"""
        return self.subject or self.genre_name

    @computed_field
    @property
    def progress(self) -> float:
        if self.total_pages and self.total_pages > 0:
            return round((self.current_page / self.total_pages) * 100, 1)
        return 0.0


class LibraryBookItemResponse(CamelModel):
    book_id: int
    shelf_id: int
    shelf_rank: str
    title: str
    author: str
    isbn: str | None = None
    genre: GenreType
    kdc: str | None = None
    subject: str | None = None
    publisher: str | None = None
    cover_url: str | None = None
    reading_status: BookReadingStatus
    current_page: int
    total_pages: int | None = None
    created_at: datetime
    completed_at: datetime | None = None

    @computed_field
    @property
    def genre_name(self) -> str:
        return GENRE_KOREAN_NAMES.get(self.genre, "기타/미분류")

    @computed_field
    @property
    def display_genre(self) -> str:
        """사용자 화면 표시용 우선 라벨 (세부 주제 subject 우선, 없을 때 대분류 genreName)"""
        return self.subject or self.genre_name

    @computed_field
    @property
    def progress(self) -> float:
        if self.total_pages and self.total_pages > 0:
            return round((self.current_page / self.total_pages) * 100, 1)
        return 0.0


class LibraryBookPageResponse(PaginatedResponse[LibraryBookItemResponse]):
    @computed_field
    @property
    def books(self) -> list[LibraryBookItemResponse]:
        """프론트엔드(frontend-reader-web) 및 레거시 클라이언트 호환 필드"""
        return self.items


class LibraryBookDetailResponse(CamelModel):
    book_id: int
    shelf_id: int
    shelf_rank: str
    title: str
    author: str
    isbn: str | None = None
    genre: GenreType
    kdc: str | None = None
    subject: str | None = None
    publisher: str | None = None
    published_date: date | None = None
    cover_url: str | None = None
    reading_status: BookReadingStatus
    current_page: int
    total_pages: int | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None

    @computed_field
    @property
    def genre_name(self) -> str:
        return GENRE_KOREAN_NAMES.get(self.genre, "기타/미분류")

    @computed_field
    @property
    def display_genre(self) -> str:
        """사용자 화면 표시용 우선 라벨 (세부 주제 subject 우선, 없을 때 대분류 genreName)"""
        return self.subject or self.genre_name

    @computed_field
    @property
    def progress(self) -> float:
        if self.total_pages and self.total_pages > 0:
            return round((self.current_page / self.total_pages) * 100, 1)
        return 0.0


class UpdateLibraryBookRequest(CamelModel):
    title: str = Field(..., min_length=1, max_length=200)
    author: str = Field(..., min_length=1, max_length=100)
    isbn: str | None = Field(None, max_length=13)
    genre: GenreType = GenreType.NONE
    kdc: str | None = Field(None, max_length=20)
    subject: str | None = Field(None, max_length=100)
    publisher: str | None = Field(None, max_length=100)
    published_date: date | None = None
    cover_url: str | None = None
    reading_status: BookReadingStatus
    total_pages: int | None = Field(None, ge=1)

    @model_validator(mode="before")
    @classmethod
    def parse_genre_and_subject(cls, data: object) -> object:
        if isinstance(data, dict):
            raw_genre = data.get("genre", GenreType.NONE)
            raw_subject = data.get("subject")
            raw_kdc = data.get("kdc")

            parsed_genre, inferred_subject = parse_to_genre_and_subject(
                raw_genre, current_subject=raw_subject, kdc_str=raw_kdc
            )
            data["genre"] = parsed_genre
            data["subject"] = inferred_subject
        return data


class UpdateLibraryBookResponse(CamelModel):
    book_id: int
    shelf_id: int
    shelf_rank: str
    title: str
    author: str
    isbn: str | None = None
    genre: GenreType
    kdc: str | None = None
    subject: str | None = None
    publisher: str | None = None
    published_date: date | None = None
    cover_url: str | None = None
    reading_status: BookReadingStatus
    current_page: int
    total_pages: int | None = None
    updated_at: datetime
    completed_at: datetime | None = None

    @computed_field
    @property
    def genre_name(self) -> str:
        return GENRE_KOREAN_NAMES.get(self.genre, "기타/미분류")

    @computed_field
    @property
    def display_genre(self) -> str:
        """사용자 화면 표시용 우선 라벨 (세부 주제 subject 우선, 없을 때 대분류 genreName)"""
        return self.subject or self.genre_name

    @computed_field
    @property
    def progress(self) -> float:
        if self.total_pages and self.total_pages > 0:
            return round((self.current_page / self.total_pages) * 100, 1)
        return 0.0


class ReorderBookRequest(CamelModel):
    before_book_id: int | None = None
    after_book_id: int | None = None

    @model_validator(mode="after")
    def validate_targets(self):
        has_before = self.before_book_id is not None
        has_after = self.after_book_id is not None
        if (has_before and has_after) or (not has_before and not has_after):
            raise InvalidReorderTargetException(
                "beforeBookId 또는 afterBookId 중 정확히 하나만 제공되어야 합니다."
            )
        return self


class ReorderBookResponse(CamelModel):
    book_id: int
    shelf_id: int
    shelf_rank: str
    updated_at: datetime


class MoveBookShelfRequest(CamelModel):
    target_shelf_id: int = Field(..., description="이동할 대상 책장 ID")


class MoveBookShelfResponse(CamelModel):
    book_id: int
    shelf_id: int
    shelf_rank: str
    updated_at: datetime


class UpdateProgressRequest(CamelModel):
    current_page: int = Field(..., ge=0, description="현재 읽은 페이지 수")


class UpdateProgressResponse(CamelModel):
    book_id: int
    current_page: int
    total_pages: int | None = None
    progress: float
    reading_status: BookReadingStatus
    completed_at: datetime | None = None
    updated_at: datetime
