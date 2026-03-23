"""BacktestRun and BacktestForecast models."""

import enum
import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import Date, DateTime, Enum, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .model_version import ModelVersion
    from .question import ForecastingQuestion


class BacktestStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class BacktestRun(Base):
    __tablename__ = "backtest_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    model_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("model_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    targets: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    config: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    status: Mapped[BacktestStatus] = mapped_column(
        Enum(
            BacktestStatus,
            name="backtest_status_enum",
            create_constraint=True,
        ),
        default=BacktestStatus.pending,
        nullable=False,
    )
    results_summary: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    model_version: Mapped[Optional["ModelVersion"]] = relationship(
        "ModelVersion", back_populates="backtest_runs"
    )
    forecasts: Mapped[list["BacktestForecast"]] = relationship(
        "BacktestForecast",
        back_populates="backtest_run",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<BacktestRun(id={self.id}, name='{self.name}', status={self.status})>"


class BacktestForecast(Base):
    __tablename__ = "backtest_forecasts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    backtest_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("backtest_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    question_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("forecasting_questions.id", ondelete="SET NULL"),
        nullable=True,
    )
    forecast_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    cutoff_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    predicted_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    predicted_distribution: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB, nullable=True
    )
    actual_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    backtest_run: Mapped["BacktestRun"] = relationship(
        "BacktestRun", back_populates="forecasts"
    )
    question: Mapped[Optional["ForecastingQuestion"]] = relationship(
        "ForecastingQuestion"
    )

    def __repr__(self) -> str:
        return f"<BacktestForecast(id={self.id}, predicted={self.predicted_value}, actual={self.actual_value})>"
