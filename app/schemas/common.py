from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

T = TypeVar("T")


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class ErrorResponse(BaseModel):
    code: str
    message: str


class PaginatedResponse(CamelModel, Generic[T]):
    items: list[T]
    page: int
    size: int
    total_elements: int
    total_pages: int
    has_previous: bool
    has_next: bool
