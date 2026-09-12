from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LibrarianLevel(Base):
    __tablename__ = "librarian_level"
    __table_args__ = {"schema": "core"}

    level: Mapped[int] = mapped_column(Integer, primary_key=True)
    required_experience: Mapped[int] = mapped_column(
        BigInteger, unique=True, nullable=False
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
