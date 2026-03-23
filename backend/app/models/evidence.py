"""EvidenceItem and EvidenceScore models."""

import enum
import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Date, DateTime, Enum, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .forecast import ForecastUpdate
    from .question import ForecastingQuestion


class SourceType(str, enum.Enum):
    official_data = "official_data"
    research = "research"
    news = "news"
    expert = "expert"
    model_output = "model_output"


class DirectionalEffect(str, enum.Enum):
    positive = "positive"
    negative = "negative"
    neutral = "neutral"
    ambiguous = "ambiguous"


class EvidenceItem(Base):
    __tablename__ = "evidence_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    source_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source_type: Mapped[SourceType] = mapped_column(
        Enum(SourceType, name="source_type_enum", create_constraint=True),
        nullable=False,
    )
    content_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    published_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    scores: Mapped[list["EvidenceScore"]] = relationship(
        "EvidenceScore", back_populates="evidence_item", cascade="all, delete-orphan"
    )
    forecast_updates: Mapped[list["ForecastUpdate"]] = relationship(
        "ForecastUpdate", back_populates="evidence_item"
    )

    def __repr__(self) -> str:
        return f"<EvidenceItem(id={self.id}, title='{self.title}')>"


class EvidenceScore(Base):
    __tablename__ = "evidence_scores"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    evidence_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evidence_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("forecasting_questions.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_credibility: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    recency_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    domain_relevance: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    redundancy_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    directional_effect: Mapped[Optional[DirectionalEffect]] = mapped_column(
        Enum(
            DirectionalEffect,
            name="directional_effect_enum",
            create_constraint=True,
        ),
        nullable=True,
    )
    expected_magnitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    uncertainty: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    composite_weight: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    scored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    evidence_item: Mapped["EvidenceItem"] = relationship(
        "EvidenceItem", back_populates="scores"
    )
    question: Mapped["ForecastingQuestion"] = relationship(
        "ForecastingQuestion", back_populates="evidence_scores"
    )

    def __repr__(self) -> str:
        return f"<EvidenceScore(id={self.id}, composite_weight={self.composite_weight})>"
