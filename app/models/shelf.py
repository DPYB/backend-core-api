import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Index, String, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, BigIntPK

if TYPE_CHECKING:
    from app.models.library_book import LibraryBook


class Shelf(Base):
    __tablename__ = "shelf"
    __table_args__ = (
        Index("ix_shelf_member_id", "member_id"),
        Index(
            "uk_shelf_member_default",
            "member_id",
            unique=True,
            postgresql_where=text("is_default = true AND deleted_at IS NULL"),
            sqlite_where=text("is_default = 1 AND deleted_at IS NULL"),
        ),
        {"schema": "core"},
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    member_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    books: Mapped[list["LibraryBook"]] = relationship(
        "LibraryBook", back_populates="shelf", cascade="all"
    )
