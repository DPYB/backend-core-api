import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, BigIntPK


class Terms(Base):
    """약관 원문 엔티티 (member.terms 테이블)"""

    __tablename__ = "terms"
    __table_args__ = (
        CheckConstraint(
            "expired_at IS NULL OR expired_at > effective_at",
            name="ck_terms_effective_period",
        ),
        Index(
            "uk_terms_active_code",
            "code",
            unique=True,
            postgresql_where=text("expired_at IS NULL AND deleted_at IS NULL"),
            sqlite_where=text("expired_at IS NULL AND deleted_at IS NULL"),
        ),
        {"schema": "member"},
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # TERMS_OF_SERVICE, PRIVACY, AI_ANALYSIS
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    effective_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expired_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

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

    agreements: Mapped[list["MemberAgreement"]] = relationship(
        "MemberAgreement", back_populates="terms"
    )


class MemberAgreement(Base):
    """약관 동의 및 철회 이력 엔티티 (member.member_agreements 테이블)"""

    __tablename__ = "member_agreements"
    __table_args__ = (
        Index(
            "ix_member_agreements_member_terms",
            "member_id",
            "terms_id",
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        {"schema": "member"},
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    member_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    terms_id: Mapped[int] = mapped_column(
        BigIntPK, ForeignKey("member.terms.id"), nullable=False
    )
    action: Mapped[str] = mapped_column(
        String(20), default="AGREE", nullable=False
    )  # AGREE, WITHDRAW
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

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

    terms: Mapped["Terms"] = relationship("Terms", back_populates="agreements")
