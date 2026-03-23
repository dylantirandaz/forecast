"""ForecastRun and ForecastUpdate models."""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, BaseModel

if TYPE_CHECKING:
    from .evidence import EvidenceItem
    from .model_version import ModelVersion
    from .question import ForecastingQuestion
    from .resolution import Resolution
    from .scenario import Scenario


class ForecastStatus(str, enum.Enum):
    draft = "draft"
    published = "published"
    superseded = "superseded"


class ForecastRun(Base):
    """A single forecast run linking a question, scenario, and model version."""

    __tablename__ = "forecast_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("forecasting_questions.id", ondelete="CASCADE"),
        nullable=False,
    )
    scenario_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scenarios.id", ondelete="SET NULL"),
        nullable=True,
    )
    model_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("model_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    prior_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    posterior_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    prior_distribution: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB, nullable=True
    )
    posterior_distribution: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB, nullable=True
    )
    confidence_lower: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    confidence_upper: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[ForecastStatus] = mapped_column(
        Enum(ForecastStatus, name="forecast_status_enum", create_constraint=True),
        default=ForecastStatus.draft,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    question: Mapped["ForecastingQuestion"] = relationship(
        "ForecastingQuestion", back_populates="forecast_runs"
    )
    scenario: Mapped[Optional["Scenario"]] = relationship(
        "Scenario", back_populates="forecast_runs"
    )
    model_version: Mapped[Optional["ModelVersion"]] = relationship(
        "ModelVersion", back_populates="forecast_runs"
    )
    updates: Mapped[list["ForecastUpdate"]] = relationship(
        "ForecastUpdate", back_populates="forecast_run", cascade="all, delete-orphan"
    )
    resolutions: Mapped[list["Resolution"]] = relationship(
        "Resolution", back_populates="forecast_run"
    )

    def __repr__(self) -> str:
        return f"<ForecastRun(id={self.id}, status={self.status})>"


class ForecastUpdate(Base):
    """An individual Bayesian update step within a forecast run."""

    __tablename__ = "forecast_updates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    forecast_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("forecast_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    update_order: Mapped[int] = mapped_column(Integer, nullable=False)
    prior_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    posterior_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    evidence_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evidence_items.id", ondelete="SET NULL"),
        nullable=True,
    )
    weight_applied: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    shift_applied: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    forecast_run: Mapped["ForecastRun"] = relationship(
        "ForecastRun", back_populates="updates"
    )
    evidence_item: Mapped[Optional["EvidenceItem"]] = relationship(
        "EvidenceItem", back_populates="forecast_updates"
    )

    def __repr__(self) -> str:
        return f"<ForecastUpdate(id={self.id}, order={self.update_order})>"
