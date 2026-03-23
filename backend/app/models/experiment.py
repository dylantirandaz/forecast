"""ExperimentRun model for ablation, benchmark, and comparison experiments."""

import enum
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class ExperimentType(str, enum.Enum):
    ablation = "ablation"
    benchmark = "benchmark"
    calibration_study = "calibration_study"
    model_comparison = "model_comparison"


class ExperimentStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class ExperimentRun(Base):
    """A single experiment run (ablation, benchmark, calibration study, or model comparison)."""

    __tablename__ = "experiment_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    experiment_type: Mapped[ExperimentType] = mapped_column(
        Enum(
            ExperimentType,
            name="experiment_type_enum",
            create_constraint=True,
        ),
        nullable=False,
    )
    config: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    ablation_flags: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB, nullable=True
    )
    model_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("model_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[ExperimentStatus] = mapped_column(
        Enum(
            ExperimentStatus,
            name="experiment_status_enum",
            create_constraint=True,
        ),
        default=ExperimentStatus.pending,
        nullable=False,
    )
    results: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    total_cost_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_questions: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    mean_brier_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    mean_log_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
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

    def __repr__(self) -> str:
        return f"<ExperimentRun(id={self.id}, name='{self.name}', type={self.experiment_type}, status={self.status})>"
