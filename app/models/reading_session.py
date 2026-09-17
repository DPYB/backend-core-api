import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, BigIntPK


class ReadingSession(Base):
    """독서 세션 로그 엔티티 (record.reading_sessions)"""

    __tablename__ = "reading_sessions"
    __table_args__ = (
        Index("ix_reading_sessions_member_id", "member_id", "created_at"),
        Index("ix_reading_sessions_book_id", "book_id", "created_at"),
        Index("idx_reading_sessions_member_month", "member_id", "end_time"),
        Index("idx_reading_sessions_book", "book_id"),
        {"schema": "record"},
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    member_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    book_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    start_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    end_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    start_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    memo: Mapped[str | None] = mapped_column(Text, nullable=True)
    weather: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
