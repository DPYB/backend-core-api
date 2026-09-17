from typing import Any

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
        """프론트엔드가 genreName을 렌더링하더라도 세부 주제(Subject)가 있으면 1순위 노출"""
        if self.subject and self.subject.strip():
            return self.subject.strip()
        return GENRE_KOREAN_NAMES.get(self.genre, "기타/미분류")

    @computed_field
    @property
    def display_genre(self) -> str:
        """사용자 화면 표시용 우선 라벨 (세부 주제 subject 우선, 없을 때 대분류 genreName)"""
        return self.subject or self.genre_name


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
        """프론트엔드가 genreName을 렌더링하더라도 세부 주제(Subject)가 있으면 1순위 노출"""
        if self.subject and self.subject.strip():
            return self.subject.strip()
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


class BookSearchResponse(CamelModel):
    already_registered: bool
    library_book: SearchLibraryBookDetail | None = None
    book: ExternalBook | None = None

    @computed_field
    @property
    def books(self) -> list[dict[str, Any]]:
        """AI 에이전트(backend-ai-agent) 및 범용 검색 클라이언트 호환 리스트"""
        if self.library_book:
            return [
                {
                    "book_id": str(self.library_book.book_id),
                    "title": self.library_book.title,
                    "author": self.library_book.author,
                    "isbn": self.library_book.isbn or "",
                    "publisher": self.library_book.publisher or "",
                    "cover_url": self.library_book.cover_url,
                    "reading_status": self.library_book.reading_status.value,
                    "display_genre": self.library_book.display_genre,
                }
            ]
        if self.book:
            return [
                {
                    "book_id": "",
                    "title": self.book.title,
                    "author": self.book.author,
                    "isbn": self.book.isbn or "",
                    "publisher": self.book.publisher or "",
                    "cover_url": self.book.cover_url,
                    "reading_status": "PLANNED",
                    "display_genre": self.book.display_genre,
                }
            ]
        return []
