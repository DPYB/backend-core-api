from pydantic import computed_field

from app.core.kdc_mapper import GENRE_KOREAN_NAMES
from app.models.enums import BookReadingStatus, GenreType
from app.schemas.common import CamelModel


class ExternalBook(CamelModel):
    title: str
    author: str
    isbn: str | None = None
    genre: GenreType = GenreType.NONE
    kdc: str | None = None
    subject: str | None = None
    publisher: str | None = None
    published_date: str | None = None
    total_pages: int | None = None
    cover_url: str | None = None

    @computed_field
    @property
    def genre_name(self) -> str:
        return GENRE_KOREAN_NAMES.get(self.genre, "기타/미분류")


class SearchLibraryBookDetail(CamelModel):
    book_id: int
    shelf_id: int
    shelf_rank: str
    title: str
    author: str
    isbn: str | None = None
    genre: GenreType = GenreType.NONE
    kdc: str | None = None
    subject: str | None = None
    publisher: str | None = None
    published_date: str | None = None
    total_pages: int | None = None
    cover_url: str | None = None
    reading_status: BookReadingStatus = BookReadingStatus.PLANNED
    current_page: int = 0

    @computed_field
    @property
    def genre_name(self) -> str:
        return GENRE_KOREAN_NAMES.get(self.genre, "기타/미분류")

    @computed_field
    @property
    def progress(self) -> float:
        if self.total_pages and self.total_pages > 0:
            return round((self.current_page / self.total_pages) * 100, 1)
        return 0.0


class BookSearchResponse(CamelModel):
    already_registered: bool
    library_book: SearchLibraryBookDetail | None = None
    book: ExternalBook | None = None
