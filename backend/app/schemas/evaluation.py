"""Pydantic v2 schemas for evaluation and historical replay."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums (mirror the SQLAlchemy enums for serialisation)
# ---------------------------------------------------------------------------
from enum import StrEnum


class QuestionDomain(StrEnum):
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


class QuestionType(StrEnum):
    binary = "binary"
    continuous = "continuous"
    multi = "multi"


class EvalRunStatus(StrEnum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


# ---------------------------------------------------------------------------
# HistoricalQuestion
# ---------------------------------------------------------------------------

class HistoricalQuestionCreate(BaseModel):
    question_text: str = Field(..., min_length=10)
    domain: QuestionDomain
    question_type: QuestionType = QuestionType.binary
    open_date: datetime
    close_date: datetime
    resolve_date: datetime
    resolution_criteria: str = Field(..., min_length=5)
    resolved_value: float
    forecast_cutoff_days: list[int] = Field(default=[90, 30, 7])
    metadata: dict | None = Field(default_factory=dict, alias="metadata_")
    difficulty: str | None = None
    source_platform: str | None = None
    source_url: str | None = None


class HistoricalQuestionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    question_text: str
    domain: QuestionDomain
    question_type: QuestionType
    open_date: datetime
    close_date: datetime
    resolve_date: datetime
    resolution_criteria: str
    resolved_value: float
    forecast_cutoff_days: list[int]
    difficulty: str | None = None
    source_platform: str | None = None
    source_url: str | None = None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# HistoricalEvidence
# ---------------------------------------------------------------------------

class HistoricalEvidenceCreate(BaseModel):
    question_id: UUID
    published_at: datetime
    source: str
    title: str = Field(..., max_length=500)
    content: str
    url: str | None = None
    source_type: str
    source_quality_score: float | None = None
    metadata: dict | None = Field(default_factory=dict, alias="metadata_")


class HistoricalEvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    question_id: UUID
    published_at: datetime
    source: str
    title: str
    content: str
    url: str | None = None
    source_type: str
    source_quality_score: float | None = None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# EvaluationSet
# ---------------------------------------------------------------------------

class EvaluationSetCreate(BaseModel):
    name: str = Field(..., max_length=200)
    description: str | None = None
    domains_included: list[str] = Field(default_factory=list)
    difficulty_mix: dict = Field(default_factory=dict)
    num_questions: int = 0
    question_ids: list[UUID] = Field(default_factory=list)
    metadata: dict | None = Field(default_factory=dict, alias="metadata_")


class EvaluationSetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None = None
    domains_included: list[str]
    difficulty_mix: dict
    num_questions: int
    question_ids: list[UUID]
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# EvalRun
# ---------------------------------------------------------------------------

class EvalRunCreate(BaseModel):
    name: str = Field(..., max_length=200)
    description: str | None = None
    evaluation_set_id: UUID | None = None
    model_config_: dict = Field(default_factory=dict, alias="model_config")
    ablation_flags: dict = Field(default_factory=dict)
    cutoff_days: list[int] = Field(default=[90, 30, 7])


class EvalRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None = None
    evaluation_set_id: UUID | None = None
    ablation_flags: dict
    cutoff_days: list[int]
    status: EvalRunStatus
    mean_brier_score: float | None = None
    mean_log_score: float | None = None
    calibration_error: float | None = None
    sharpness: float | None = None
    total_questions: int | None = None
    total_cost_usd: float | None = None
    total_latency_ms: int | None = None
    results_by_domain: dict = Field(default_factory=dict)
    results_by_horizon: dict = Field(default_factory=dict)
    results_by_difficulty: dict = Field(default_factory=dict)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class EvalRunSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    status: EvalRunStatus
    mean_brier_score: float | None = None
    mean_log_score: float | None = None
    calibration_error: float | None = None
    total_questions: int | None = None
    total_cost_usd: float | None = None
    created_at: datetime


# ---------------------------------------------------------------------------
# EvalPrediction
# ---------------------------------------------------------------------------

class EvalPredictionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    eval_run_id: UUID
    question_id: UUID
    cutoff_days: int
    cutoff_date: datetime
    predicted_probability: float
    predicted_mean: float | None = None
    predicted_std: float | None = None
    confidence_lower: float | None = None
    confidence_upper: float | None = None
    actual_value: float
    brier_score: float | None = None
    log_score: float | None = None
    evidence_count: int = 0
    base_rate_used: float | None = None
    model_tier_used: str | None = None
    cost_usd: float | None = None
    latency_ms: int | None = None
    rationale: str | None = None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Evaluation metrics & analytics schemas
# ---------------------------------------------------------------------------

class EvalMetrics(BaseModel):
    """Aggregated metrics for a set of predictions."""
    brier_score: float | None = None
    log_score: float | None = None
    calibration_error: float | None = None
    sharpness: float | None = None
    n_questions: int = 0


class EvalDomainBreakdown(BaseModel):
    """Metrics broken down by question domain."""
    breakdown: dict[str, EvalMetrics] = Field(default_factory=dict)


class EvalHorizonBreakdown(BaseModel):
    """Metrics broken down by forecast horizon (cutoff days)."""
    breakdown: dict[str, EvalMetrics] = Field(default_factory=dict)


class CalibrationBin(BaseModel):
    """A single bin in a calibration curve."""
    predicted_mean: float
    observed_mean: float
    count: int


class CalibrationCurveData(BaseModel):
    """Full calibration curve data."""
    bins: list[CalibrationBin] = Field(default_factory=list)
    n_total: int = 0
    calibration_error: float | None = None


class EvalComparisonRequest(BaseModel):
    """Request to compare multiple eval runs."""
    eval_run_ids: list[UUID] = Field(..., min_length=2)


class EvalRunComparisonEntry(BaseModel):
    """One entry in a comparison response."""
    run_id: UUID
    name: str
    status: EvalRunStatus
    mean_brier_score: float | None = None
    mean_log_score: float | None = None
    calibration_error: float | None = None
    total_questions: int | None = None
    total_cost_usd: float | None = None
    brier_delta: float | None = None
    log_score_delta: float | None = None
    calibration_delta: float | None = None


class EvalComparisonResponse(BaseModel):
    """Response comparing multiple eval runs."""
    baseline_run_id: UUID
    runs: list[EvalRunComparisonEntry] = Field(default_factory=list)
