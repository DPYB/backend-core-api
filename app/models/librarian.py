import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Uuid,
    func,
    text,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, BigIntPK
from app.models.enums import LibrarianType
from app.models.librarian_level import LibrarianLevel
from app.models.librarian_type_info import LibrarianTypeInfo


class Librarian(Base):
    __tablename__ = "librarian"
    __table_args__ = (
        Index(
            "ix_librarian_member_id",
            "member_id",
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        Index(
            "uk_librarian_member_type",
            "member_id",
            "type",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        Index(
            "uk_librarian_member_representative",
            "member_id",
            unique=True,
            postgresql_where=text("is_representative = true AND deleted_at IS NULL"),
            sqlite_where=text("is_representative = 1 AND deleted_at IS NULL"),
        ),
        {"schema": "core"},
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    member_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    type: Mapped[LibrarianType] = mapped_column(
        SAEnum(
            LibrarianType, name="librarian_type", schema="core", inherit_schema=True
        ),
        ForeignKey("core.librarian_type_info.type"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    level: Mapped[int] = mapped_column(
        Integer, ForeignKey("core.librarian_level.level"), default=1, nullable=False
    )
    experience: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    is_representative: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
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

    type_info: Mapped["LibrarianTypeInfo"] = relationship("LibrarianTypeInfo")
    level_info: Mapped["LibrarianLevel"] = relationship("LibrarianLevel")
