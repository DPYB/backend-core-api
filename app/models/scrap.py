from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, BigIntPK

if TYPE_CHECKING:
    from app.models.library_book import LibraryBook


class Scrap(Base):
    __tablename__ = "scrap"
    __table_args__ = (
        Index("ix_scrap_book_id", "book_id"),
        {"schema": "core"},
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    book_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("core.library_book.id", ondelete="CASCADE"),
        nullable=False,
    )
    sentence: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scrap_image_url: Mapped[str] = mapped_column(Text, nullable=False)
    memo: Mapped[str | None] = mapped_column(Text, nullable=True)
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

    book: Mapped["LibraryBook"] = relationship("LibraryBook", back_populates="scraps")
