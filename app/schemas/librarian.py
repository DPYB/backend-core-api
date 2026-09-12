from datetime import datetime

from pydantic import Field

from app.models.enums import LibrarianType
from app.schemas.common import CamelModel


class LibrarianTypeItemResponse(CamelModel):
    type: LibrarianType
    image_url: str
    clicked_image_url: str


class LibrarianTypeListResponse(CamelModel):
    types: list[LibrarianTypeItemResponse]


class AcquireLibrarianRequest(CamelModel):
    type: LibrarianType
    name: str = Field(..., min_length=1, max_length=50, description="사서 이름")


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
    level: int
    experience: int
    is_representative: bool
    image_url: str | None = None
    clicked_image_url: str | None = None
    updated_at: datetime | None = None
