from datetime import datetime

from pydantic import Field

from app.models.enums import LibrarianType
from app.schemas.common import CamelModel


class LibrarianTypeItemResponse(CamelModel):
    type: LibrarianType
    default_name: str = Field(description="기본 표시명 (블루, 슈빌, 누디, 게코)")
    species: str = Field(
        description="동물 종 (러시안 블루, 넙적부리황새, 갯민숭달팽이, 게코 도마뱀)"
    )
    mbti: str = Field(description="MBTI (INTJ, ISTP, INFP, ENFJ)")
    genres: list[str] = Field(description="담당 도서 장르 목록")
    description: str = Field(description="사서 특징 및 페르소나 설명")
    ending_style: str = Field(description="종결 어미 (~냥, ~두둥, ~누누, ~크크)")
    image_url: str
    clicked_image_url: str


class LibrarianTypeListResponse(CamelModel):
    types: list[LibrarianTypeItemResponse]


class AcquireLibrarianRequest(CamelModel):
    type: LibrarianType
    name: str | None = Field(
        None, max_length=50, description="사서 이름 (생략 시 기본 표시명 자동 지정)"
    )


class AcquireLibrarianResponse(CamelModel):
    librarian_id: int
    type: LibrarianType
    name: str
    level: int
    experience: int
    is_representative: bool
    created_at: datetime


class LibrarianResponse(CamelModel):
    librarian_id: int
    type: LibrarianType
    name: str
    default_name: str | None = None
    species: str | None = None
    level: int
    experience: int
    is_representative: bool
    image_url: str | None = None
    clicked_image_url: str | None = None
    created_at: datetime


class RenameLibrarianRequest(CamelModel):
    name: str = Field(..., min_length=1, max_length=50, description="새 이름")


class RenameLibrarianResponse(CamelModel):
    librarian_id: int
    name: str
    updated_at: datetime


class RepresentativeLibrarianResponse(CamelModel):
    librarian_id: int
    type: LibrarianType
    name: str
    default_name: str | None = None
    species: str | None = None
    mbti: str | None = None
    genres: list[str] = Field(default_factory=list)
    description: str | None = None
    ending_style: str | None = None
    level: int
    experience: int
    is_representative: bool
    image_url: str | None = None
    clicked_image_url: str | None = None
    updated_at: datetime | None = None
