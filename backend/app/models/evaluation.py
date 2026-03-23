"""Evaluation and historical replay models."""
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Index,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, BaseModel, TimestampMixin


class QuestionDomain(str, enum.Enum):
    macro = "macro"
    politics = "politics"
    technology = "technology"
    business = "business"
    science = "science"
    housing = "housing"
    energy = "energy"
    health = "health"
    geopolitics = "geopolitics"
    other = "other"


class QuestionType(str, enum.Enum):
    binary = "binary"
    continuous = "continuous"
    multi = "multi"


class EvalRunStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class HistoricalQuestion(BaseModel):
    __tablename__ = "historical_questions"

    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[QuestionDomain] = mapped_column(
        Enum(QuestionDomain, name="question_domain_enum", create_constraint=True)
    )
    question_type: Mapped[QuestionType] = mapped_column(
        Enum(QuestionType, name="question_type_eval_enum", create_constraint=True)
    )
    open_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    close_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    resolve_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    resolution_criteria: Mapped[str] = mapped_column(Text, nullable=False)
    resolved_value: Mapped[float] = mapped_column(Float, nullable=False)
    forecast_cutoff_days: Mapped[list] = mapped_column(
        JSONB, default=[90, 30, 7]
    )
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default={})
    difficulty: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )
    source_platform: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    source_url: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )

    # Relationships
    evidence_items: Mapped[list["HistoricalEvidence"]] = relationship(
        back_populates="question", cascade="all, delete-orphan"
    )
    eval_predictions: Mapped[list["EvalPrediction"]] = relationship(
        back_populates="question", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_hist_q_domain", "domain"),
        Index("ix_hist_q_type", "question_type"),
        Index("ix_hist_q_resolve", "resolve_date"),
    )


class HistoricalEvidence(BaseModel):
    __tablename__ = "historical_evidence"

    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("historical_questions.id", ondelete="CASCADE"),
        nullable=False,
    )
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    source: Mapped[str] = mapped_column(String(200), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_quality_score: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default={})

    # Relationships
    question: Mapped["HistoricalQuestion"] = relationship(
        back_populates="evidence_items"
    )

    __table_args__ = (
        Index("ix_hist_ev_question", "question_id"),
        Index("ix_hist_ev_published", "published_at"),
    )


class EvaluationSet(BaseModel):
    __tablename__ = "evaluation_sets"

    name: Mapped[str] = mapped_column(
        String(200), nullable=False, unique=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    domains_included: Mapped[list] = mapped_column(JSONB, default=[])
    difficulty_mix: Mapped[dict] = mapped_column(JSONB, default={})
    num_questions: Mapped[int] = mapped_column(Integer, default=0)
    question_ids: Mapped[list] = mapped_column(JSONB, default=[])
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default={})


class EvalRun(BaseModel):
    __tablename__ = "eval_runs"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    evaluation_set_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evaluation_sets.id"),
        nullable=True,
    )
    model_config_: Mapped[dict] = mapped_column(
        "model_config", JSONB, default={}
    )
    ablation_flags: Mapped[dict] = mapped_column(JSONB, default={})
    cutoff_days: Mapped[list] = mapped_column(JSONB, default=[90, 30, 7])
    status: Mapped[EvalRunStatus] = mapped_column(
        Enum(
            EvalRunStatus,
            name="eval_run_status_enum",
            create_constraint=True,
        ),
        default=EvalRunStatus.pending,
    )

    # Aggregate results
    mean_brier_score: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    mean_log_score: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    calibration_error: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    sharpness: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_questions: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    total_cost_usd: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    total_latency_ms: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )

    results_by_domain: Mapped[dict] = mapped_column(JSONB, default={})
    results_by_horizon: Mapped[dict] = mapped_column(JSONB, default={})
    results_by_difficulty: Mapped[dict] = mapped_column(JSONB, default={})
    full_results: Mapped[dict] = mapped_column(JSONB, default={})

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    predictions: Mapped[list["EvalPrediction"]] = relationship(
        back_populates="eval_run", cascade="all, delete-orphan"
    )
    evaluation_set: Mapped["EvaluationSet | None"] = relationship()

    __table_args__ = (Index("ix_eval_run_status", "status"),)


class EvalPrediction(BaseModel):
    __tablename__ = "eval_predictions"

    eval_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("eval_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("historical_questions.id", ondelete="CASCADE"),
        nullable=False,
    )
    cutoff_days: Mapped[int] = mapped_column(Integer, nullable=False)
    cutoff_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    predicted_probability: Mapped[float] = mapped_column(
        Float, nullable=False
    )
    predicted_mean: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    predicted_std: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    confidence_lower: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    confidence_upper: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )

    actual_value: Mapped[float] = mapped_column(Float, nullable=False)

    brier_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    log_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    evidence_count: Mapped[int] = mapped_column(Integer, default=0)
    base_rate_used: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    model_tier_used: Mapped[str | None] = mapped_column(
        String(10), nullable=True
    )
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    pipeline_trace: Mapped[dict] = mapped_column(JSONB, default={})

    # Relationships
    eval_run: Mapped["EvalRun"] = relationship(back_populates="predictions")
    question: Mapped["HistoricalQuestion"] = relationship(
        back_populates="eval_predictions"
    )

    __table_args__ = (
        UniqueConstraint(
            "eval_run_id",
            "question_id",
            "cutoff_days",
            name="uq_eval_pred",
        ),
        Index("ix_eval_pred_run", "eval_run_id"),
        Index("ix_eval_pred_question", "question_id"),
    )
