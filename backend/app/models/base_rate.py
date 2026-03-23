"""BaseRate model."""

import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class BaseRate(Base):
    __tablename__ = "base_rates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    target_metric: Mapped[str] = mapped_column(String(255), nullable=False)
    geography: Mapped[str] = mapped_column(
        String(100), default="nyc", nullable=False
    )
    period_start: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    period_end: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    mean_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    median_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    std_dev: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    percentile_10: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    percentile_90: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sample_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    data_source: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    methodology_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<BaseRate(id={self.id}, metric='{self.target_metric}', geography='{self.geography}')>"
