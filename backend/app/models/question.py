"""ForecastingQuestion model."""

import enum
import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Date, DateTime, Enum, Float, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, BaseModel

if TYPE_CHECKING:
    from .evidence import EvidenceScore
    from .forecast import ForecastRun
    from .resolution import Resolution


class TargetType(str, enum.Enum):
    binary = "binary"
    continuous = "continuous"
    categorical = "categorical"


class QuestionStatus(str, enum.Enum):
    active = "active"
    resolved = "resolved"
    retired = "retired"


class ForecastingQuestion(BaseModel):
    __tablename__ = "forecasting_questions"

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    target_type: Mapped[TargetType] = mapped_column(
        Enum(TargetType, name="target_type_enum", create_constraint=True),
        nullable=False,
    )
    target_metric: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    unit_of_analysis: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    forecast_horizon_months: Mapped[Optional[int]] = mapped_column(nullable=True)
    resolution_criteria: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[QuestionStatus] = mapped_column(
        Enum(QuestionStatus, name="question_status_enum", create_constraint=True),
        default=QuestionStatus.active,
        nullable=False,
    )
    resolution_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    resolution_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Relationships
    forecast_runs: Mapped[list["ForecastRun"]] = relationship(
        "ForecastRun", back_populates="question", cascade="all, delete-orphan"
    )
    evidence_scores: Mapped[list["EvidenceScore"]] = relationship(
        "EvidenceScore", back_populates="question", cascade="all, delete-orphan"
    )
    resolutions: Mapped[list["Resolution"]] = relationship(
        "Resolution", back_populates="question", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<ForecastingQuestion(id={self.id}, title='{self.title}', status={self.status})>"
