from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.models.enums import GenreType, LibrarianType
from app.schemas.common import CamelModel


class LibrarianReportInfo(CamelModel):
    type: LibrarianType
    name: str = Field(description="사서 이름 (예: 블루)")
    level: int = Field(default=1)
    report_title: str = Field(
        description="리포트 타이틀 (예: 블루 사서의 월간 독서 리포트)"
    )


class MonthlyOverview(CamelModel):
    completed_books_count: int = Field(description="이번 달 완독 권수")
    total_pages_read: int = Field(description="이번 달 누적 독서 페이지")
    total_duration_minutes: int = Field(description="이번 달 총 독서 시간 (분)")
    goal_books_count: int = Field(default=3, description="이번 달 목표 권수")
    goal_achievement_rate: float = Field(description="목표 달성률 (%)")


class ReadingHabits(CamelModel):
    weekday_distribution: dict[str, int] = Field(
        description="요일별 독서 횟수 (MON, TUE, ...)"
    )
    time_distribution: dict[str, int] = Field(
        description="시간대별 독서 횟수 (dawn, day, evening, night)"
    )
    weather_distribution: dict[str, int] = Field(
        description="날씨별 독서 횟수 (clear, rainy, cloudy, snowy, ...)"
    )
    avg_completion_days: float | None = Field(
        default=None, description="평균 완독 소요 기간 (일)"
    )
    longest_streak_days: int = Field(
        default=0, description="해당 월 최장 연속 독서일 (Streak)"
    )


class GenrePreferenceItem(CamelModel):
    genre: GenreType
    genre_name: str
    count: int
    percentage: float


class WeatherPreferenceItem(CamelModel):
    weather: str
    session_count: int
    top_genre: GenreType | None = None
    top_genre_name: str | None = None
    preferred_book_title: str | None = None


class ReadingPreferences(CamelModel):
    top_genres: list[GenrePreferenceItem] = Field(default_factory=list)
    top_subjects: list[str] = Field(
        default_factory=list, description="주요 세부 주제 태그"
    )
    weather_preferences: list[WeatherPreferenceItem] = Field(
        default_factory=list, description="날씨별 선호 장르 및 도서"
    )


class GenreBalanceItem(CamelModel):
    genre: GenreType
    genre_name: str
    count: int
    percentage: float


class ReadingBalance(CamelModel):
    genre_breakdown: list[GenreBalanceItem] = Field(default_factory=list)
    dominant_genre: str | None = Field(default=None, description="가장 편중된 장르명")
    is_biased: bool = Field(default=False, description="편독 여부 (특정 장르 >= 60%)")
    diversity_score: int = Field(default=0, description="장르 다양성 점수 (0~100)")
    unread_genres: list[str] = Field(
        default_factory=list, description="이번 달 읽지 않은 KDC 대분류 목록"
    )


class ScrappedBookItem(CamelModel):
    book_id: int
    title: str
    author: str
    cover_url: str | None = None
    display_genre: str | None = None
    scrap_count: int


class FeaturedRecordItem(CamelModel):
    record_id: int
    book_id: int
    title: str
    content_snippet: str
    rating: int | None = None
    weather: str | None = None
    created_at: datetime


class ReportBookSummary(CamelModel):
    book_id: int
    title: str
    author: str
    cover_url: str | None = None
    display_genre: str | None = None
    current_page: int
    total_pages: int | None = None
    completed_at: datetime | None = None


class ReadingTraces(CamelModel):
    most_scrapped_books: list[ScrappedBookItem] = Field(default_factory=list)
    featured_records: list[FeaturedRecordItem] = Field(default_factory=list)
    completed_books: list[ReportBookSummary] = Field(default_factory=list)
    reading_books: list[ReportBookSummary] = Field(default_factory=list)


class MonthlyReportStatsResponse(CamelModel):
    year: int
    month: int
    member_id: UUID
    librarian: LibrarianReportInfo
    overview: MonthlyOverview
    habits: ReadingHabits
    preferences: ReadingPreferences
    balance: ReadingBalance
    traces: ReadingTraces
