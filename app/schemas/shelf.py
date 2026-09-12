from datetime import datetime

from pydantic import Field

from app.schemas.common import CamelModel


class CreateShelfRequest(CamelModel):
    name: str = Field(..., min_length=1, max_length=50, description="책장 이름")


class CreateShelfResponse(CamelModel):
    shelf_id: int
    name: str
    is_default: bool
    created_at: datetime


class UpdateShelfRequest(CamelModel):
    name: str = Field(..., min_length=1, max_length=50, description="새 책장 이름")


class UpdateShelfResponse(CamelModel):
    shelf_id: int
    name: str
    is_default: bool
    updated_at: datetime


class ShelfItemResponse(CamelModel):
    shelf_id: int
    name: str
    is_default: bool
    book_count: int
    created_at: datetime


class ShelfListResponse(CamelModel):
    shelves: list[ShelfItemResponse]
