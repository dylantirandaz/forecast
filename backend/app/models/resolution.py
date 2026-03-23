"""Resolution and Score models."""

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .forecast import ForecastRun
    from .question import ForecastingQuestion


class Resolution(Base):
    __tablename__ = "resolutions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("forecasting_questions.id", ondelete="CASCADE"),
        nullable=False,
    )
    forecast_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("forecast_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    actual_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    actual_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    brier_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    log_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    calibration_bucket: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    question: Mapped["ForecastingQuestion"] = relationship(
        "ForecastingQuestion", back_populates="resolutions"
    )
    forecast_run: Mapped[Optional["ForecastRun"]] = relationship(
        "ForecastRun", back_populates="resolutions"
    )

    def __repr__(self) -> str:
        return f"<Resolution(id={self.id}, brier_score={self.brier_score})>"


class Score(Base):
    """Aggregate scoring record for tracking forecaster/model performance."""

    __tablename__ = "scores"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    model_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("model_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    period_start: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    period_end: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    total_questions: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    mean_brier_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    mean_log_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    calibration_error: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    resolution_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sharpness: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<Score(id={self.id}, mean_brier={self.mean_brier_score})>"
