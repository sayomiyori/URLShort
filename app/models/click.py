from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Click(Base):
    __tablename__ = "click"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    url_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("url.id", ondelete="CASCADE"),
        nullable=False,
    )
    clicked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    ip_address: Mapped[str] = mapped_column(String(45), nullable=False)
    user_agent: Mapped[str] = mapped_column(Text, nullable=False)
    referer: Mapped[str | None] = mapped_column(Text, nullable=True)
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    city: Mapped[str | None] = mapped_column(String(128), nullable=True)
    device_type: Mapped[str] = mapped_column(String(32), nullable=False)

    url: Mapped["URL"] = relationship("URL", back_populates="clicks")

    __table_args__ = (
        Index("ix_click_url_id_clicked_at", "url_id", "clicked_at"),
    )
