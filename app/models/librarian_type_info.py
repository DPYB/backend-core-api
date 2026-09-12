from datetime import datetime

from sqlalchemy import DateTime, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import LibrarianType


class LibrarianTypeInfo(Base):
    __tablename__ = "librarian_type_info"
    __table_args__ = {"schema": "core"}

    type: Mapped[LibrarianType] = mapped_column(
        SAEnum(
            LibrarianType, name="librarian_type", schema="core", inherit_schema=True
        ),
        primary_key=True,
    )
    image_url: Mapped[str] = mapped_column(Text, nullable=False)
    clicked_image_url: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
