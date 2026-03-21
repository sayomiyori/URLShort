from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class URL(Base):
    __tablename__ = "url"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    short_code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    original_url: Mapped[str] = mapped_column(Text, nullable=False)
    custom_alias: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    click_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    owner_api_key: Mapped[str | None] = mapped_column(String(128), nullable=True)

    clicks: Mapped[list["Click"]] = relationship(
        "Click",
        back_populates="url",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_url_created_at", "created_at"),
    )
