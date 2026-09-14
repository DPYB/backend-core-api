import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, BigIntPK
from app.models.enums import BookReadingStatus, GenreType

if TYPE_CHECKING:
    from app.models.scrap import Scrap
    from app.models.shelf import Shelf


class LibraryBook(Base):
    __tablename__ = "library_book"
    __table_args__ = (
        Index(
            "uk_library_book_shelf_rank",
            "shelf_id",
            "shelf_rank",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        Index(
            "uk_library_book_member_isbn",
            "member_id",
            "isbn",
            unique=True,
            postgresql_where=text("isbn IS NOT NULL AND deleted_at IS NULL"),
            sqlite_where=text("isbn IS NOT NULL AND deleted_at IS NULL"),
        ),
        {"schema": "core"},
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    member_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    shelf_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("core.shelf.id", ondelete="RESTRICT"), nullable=False
    )
    shelf_rank: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    author: Mapped[str] = mapped_column(String(100), nullable=False)
    isbn: Mapped[str | None] = mapped_column(String(13), nullable=True)
    genre: Mapped[GenreType] = mapped_column(
        SAEnum(GenreType, name="genre_type", schema="core", inherit_schema=True),
        default=GenreType.NONE,
        nullable=False,
    )
    kdc: Mapped[str | None] = mapped_column(String(20), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(100), nullable=True)
    publisher: Mapped[str | None] = mapped_column(String(100), nullable=True)
    published_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    cover_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    reading_status: Mapped[BookReadingStatus] = mapped_column(
        SAEnum(
            BookReadingStatus,
            name="book_reading_status",
            schema="core",
            inherit_schema=True,
        ),
        default=BookReadingStatus.PLANNED,
        nullable=False,
    )
    total_pages: Mapped[int | None] = mapped_column(Integer, nullable=True)
    current_page: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    shelf: Mapped["Shelf"] = relationship("Shelf", back_populates="books")
    scraps: Mapped[list["Scrap"]] = relationship(
        "Scrap", back_populates="book", cascade="all, delete-orphan"
    )
