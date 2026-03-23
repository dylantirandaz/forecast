"""BenchmarkSubmission model for external benchmark tracking."""

import enum
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class BenchmarkStatus(str, enum.Enum):
    draft = "draft"
    submitted = "submitted"
    scored = "scored"
    invalidated = "invalidated"


class BenchmarkSubmission(Base):
    """A submission to an external benchmark (e.g. ForecastBench, Metaculus)."""

    __tablename__ = "benchmark_submissions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    benchmark_name: Mapped[str] = mapped_column(String(255), nullable=False)
    submission_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    submission_payload: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB, nullable=True
    )
    experiment_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("experiment_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    model_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("model_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    config: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    scores: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    status: Mapped[BenchmarkStatus] = mapped_column(
        Enum(
            BenchmarkStatus,
            name="benchmark_status_enum",
            create_constraint=True,
        ),
        default=BenchmarkStatus.draft,
        nullable=False,
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
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
        return f"<BenchmarkSubmission(id={self.id}, benchmark='{self.benchmark_name}', status={self.status})>"
