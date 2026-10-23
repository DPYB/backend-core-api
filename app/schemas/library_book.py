from datetime import date, datetime

from pydantic import Field, computed_field, field_validator, model_validator

from app.core.exceptions import InvalidReorderTargetException
from app.core.genre_mapper import (
    GENRE_KOREAN_NAMES,
    parse_to_genre_and_subject,
)
from app.core.isbn import normalize_isbn
from app.core.kdc_mapper import (
    parse_to_date,
)
from app.models.enums import BookReadingStatus, GenreType, LibrarianType
from app.schemas.common import CamelModel, PaginatedResponse

ALLOWED_GENRE_SOURCES: set[str] = {
    "KDC",
    "DDC",
    "LLM",
    "FALLBACK",
    "USER",
    "KDC_FALLBACK",
}


class BookCoverPresignedUrlRequest(CamelModel):
    """도서 직접 등록용 커스텀 표지 Presigned URL 발급 요청"""

    content_type: str = Field(
        default="image/webp",
        description="업로드할 이미지 Content-Type (image/webp, image/jpeg, image/png, image/gif)",
    )


class BookCoverPresignedUrlData(CamelModel):
    """도서 표지 Presigned URL 상세 데이터"""

    upload_url: str = Field(
        ..., description="Cloudflare R2 다이렉트 업로드용 Presigned PUT URL"
    )
    public_url: str = Field(..., description="최종 CDN 이미지 접근 URL")
    key: str = Field(..., description="R2 스토리지 객체 키")
    expires_in: int = Field(default=600, description="Presigned URL 유효 시간 (초)")

    @computed_field  # type: ignore[misc]
    @property
    def presigned_url(self) -> str:
        """기존 스토리지 DTO 및 클라이언트 호환 필드"""
        return self.upload_url

    @computed_field  # type: ignore[misc]
    @property
    def image_url(self) -> str:
        """기존 스토리지 DTO 및 클라이언트 호환 필드"""
        return self.public_url


class BookCoverPresignedUrlResponse(CamelModel):
    """도서 표지 Presigned URL 발급 응답"""

    status: str = Field(default="success", description="응답 상태")
    data: BookCoverPresignedUrlData = Field(..., description="Presigned URL 데이터")


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
    description: str | None = None
    genre_source: str = "KDC"
    genre_confidence: float | None = None
    reading_status: BookReadingStatus = BookReadingStatus.PLANNED
    total_pages: int | None = Field(None, ge=1)
    current_page: int = Field(0, ge=0)
    shelf_id: int | None = None

    @field_validator("genre_source", mode="before")
    @classmethod
    def validate_genre_source(cls, v: object) -> str:
        if v is None or (isinstance(v, str) and not v.strip()):
            return "KDC"
        val = str(v).strip().upper()
        if val not in ALLOWED_GENRE_SOURCES:
            raise ValueError(
                f"유효하지 않은 장르 출처(genre_source)입니다: {v}. 허용 값: {sorted(ALLOWED_GENRE_SOURCES)}"
            )
        return val

    @field_validator("isbn", mode="before")
    @classmethod
    def validate_and_normalize_isbn(cls, v: object) -> str | None:
        if v is None:
            return None
        return normalize_isbn(str(v))

    @field_validator("published_date", mode="before")
    @classmethod
    def validate_published_date(cls, v: object) -> date | None:
        return parse_to_date(v)

    @model_validator(mode="before")
    @classmethod
    def parse_genre_and_subject(cls, data: object) -> object:
        if isinstance(data, dict):
            raw_genre = data.get("genre", GenreType.NONE)
            raw_subject = data.get("subject")
            raw_kdc = data.get("kdc")
            raw_title = data.get("title")

            parsed_genre, inferred_subject = parse_to_genre_and_subject(
                raw_genre,
                current_subject=raw_subject,
                kdc_str=raw_kdc,
                title=raw_title,
            )
            data["genre"] = parsed_genre
            data["subject"] = inferred_subject
        return data


class CreateLibraryBookResponse(CamelModel):
    book_id: int
    shelf_id: int
    shelf_rank: str
    shelf_tier: int = 0
    shelf_order: int = 0
    title: str
    author: str
    isbn: str | None = None
    genre: GenreType
    kdc: str | None = None
    subject: str | None = None
    publisher: str | None = None
    published_date: date | None = None
    cover_url: str | None = None
    description: str | None = None
    genre_source: str = "KDC"
    genre_confidence: float | None = None
    reading_status: BookReadingStatus
    current_page: int
    total_pages: int | None = None
    created_at: datetime
    completed_at: datetime | None = None

    @computed_field
    @property
    def genre_name(self) -> str:
        """대분류 한글명 본연의 값 반환 (교양, 철학, 문학, 기술과학 등)"""
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
    shelf_tier: int = 0
    shelf_order: int = 0
    title: str
    author: str
    isbn: str | None = None
    genre: GenreType
    kdc: str | None = None
    subject: str | None = None
    publisher: str | None = None
    cover_url: str | None = None
    description: str | None = None
    genre_source: str = "KDC"
    genre_confidence: float | None = None
    reading_status: BookReadingStatus
    current_page: int
    total_pages: int | None = None
    created_at: datetime
    completed_at: datetime | None = None

    @computed_field
    @property
    def genre_name(self) -> str:
        """대분류 한글명 본연의 값 반환 (교양, 철학, 문학, 기술과학 등)"""
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
    shelf_tier: int = 0
    shelf_order: int = 0
    title: str
    author: str
    isbn: str | None = None
    genre: GenreType
    kdc: str | None = None
    subject: str | None = None
    publisher: str | None = None
    published_date: date | None = None
    cover_url: str | None = None
    description: str | None = None
    genre_source: str = "KDC"
    genre_confidence: float | None = None
    reading_status: BookReadingStatus
    current_page: int
    total_pages: int | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None

    @computed_field
    @property
    def genre_name(self) -> str:
        """대분류 한글명 본연의 값 반환 (교양, 철학, 문학, 기술과학 등)"""
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
    description: str | None = None
    genre_source: str | None = None
    genre_confidence: float | None = None
    reading_status: BookReadingStatus
    total_pages: int | None = Field(None, ge=1)

    @field_validator("genre_source", mode="before")
    @classmethod
    def validate_genre_source(cls, v: object) -> str | None:
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        val = str(v).strip().upper()
        if val not in ALLOWED_GENRE_SOURCES:
            raise ValueError(
                f"유효하지 않은 장르 출처(genre_source)입니다: {v}. 허용 값: {sorted(ALLOWED_GENRE_SOURCES)}"
            )
        return val

    @field_validator("isbn", mode="before")
    @classmethod
    def validate_and_normalize_isbn(cls, v: object) -> str | None:
        if v is None:
            return None
        return normalize_isbn(str(v))

    @field_validator("published_date", mode="before")
    @classmethod
    def validate_published_date(cls, v: object) -> date | None:
        return parse_to_date(v)

    @model_validator(mode="before")
    @classmethod
    def parse_genre_and_subject(cls, data: object) -> object:
        if isinstance(data, dict):
            raw_genre = data.get("genre", GenreType.NONE)
            raw_subject = data.get("subject")
            raw_kdc = data.get("kdc")
            raw_title = data.get("title")

            parsed_genre, inferred_subject = parse_to_genre_and_subject(
                raw_genre,
                current_subject=raw_subject,
                kdc_str=raw_kdc,
                title=raw_title,
            )
            data["genre"] = parsed_genre
            data["subject"] = inferred_subject
        return data


class UpdateLibraryBookResponse(CamelModel):
    book_id: int
    shelf_id: int
    shelf_rank: str
    shelf_tier: int = 0
    shelf_order: int = 0
    title: str
    author: str
    isbn: str | None = None
    genre: GenreType
    kdc: str | None = None
    subject: str | None = None
    publisher: str | None = None
    published_date: date | None = None
    cover_url: str | None = None
    description: str | None = None
    genre_source: str = "KDC"
    genre_confidence: float | None = None
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


class ShelfPlacementsUpdateRequest(CamelModel):
    """선반별 도서 단/순서 일괄 업데이트 요청"""

    librarian_type: LibrarianType | None = Field(
        None, description="사서 타입 (선택 사항)"
    )
    assignments: dict[str, list[int]] = Field(
        ...,
        description="선반 단(키: 문자열 '0', '1' 등)별 도서 ID 목록 매핑",
    )

    @field_validator("assignments", mode="before")
    @classmethod
    def validate_assignments(cls, v: object) -> dict[str, list[int]]:
        if not isinstance(v, dict):
            raise ValueError("assignments는 객체(dict) 형태여야 합니다.")
        normalized: dict[str, list[int]] = {}
        for k, ids in v.items():
            str_key = str(k).strip()
            try:
                tier_idx = int(str_key)
                if tier_idx < 0:
                    raise ValueError(f"선반 단 번호는 0 이상이어야 합니다: {k}")
            except (ValueError, TypeError) as e:
                raise ValueError(
                    f"선반 단 번호가 유효한 0 이상의 정수가 아닙니다: {k}"
                ) from e
            if not isinstance(ids, list):
                raise ValueError(f"선반 {k}의 도서 목록은 배열이어야 합니다.")
            converted_ids: list[int] = []
            for bid in ids:
                try:
                    int_bid = int(bid)
                    if int_bid <= 0:
                        raise ValueError(f"유효한 도서 ID(양의 정수)여야 합니다: {bid}")
                    converted_ids.append(int_bid)
                except (ValueError, TypeError) as e:
                    raise ValueError(
                        f"유효한 도서 ID(양의 정수)여야 합니다: {bid}"
                    ) from e
            normalized[str_key] = converted_ids
        return normalized


class ShelfPlacementsResponse(CamelModel):
    """선반별 도서 단/순서 일괄 업데이트 응답"""

    status: str = Field(default="success", description="처리 상태")
    updated_count: int = Field(..., description="배치가 갱신된 도서 건수")
