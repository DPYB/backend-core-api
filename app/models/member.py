import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Index, String, Text, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, BigIntPK


class Member(Base):
    """회원 정보 엔티티 (member.members 테이블)"""

    __tablename__ = "members"
    __table_args__ = (
        Index("ix_members_member_id", "member_id", unique=True),
        Index(
            "uq_members_email_active",
            "email",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        Index(
            "ix_members_provider",
            "provider",
            "provider_id",
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        {"schema": "member"},
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    member_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), default=uuid.uuid4, nullable=False
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    nickname: Mapped[str] = mapped_column(String(255), nullable=False)
    profile_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # MALE, FEMALE
    status: Mapped[str] = mapped_column(
        String(20), default="ACTIVE", nullable=False
    )  # ACTIVE, WITHDRAWN
    provider: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # GOOGLE, KAKAO
    provider_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

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
