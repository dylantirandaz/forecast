"""Schemas for experiment runs (ablation, benchmark, calibration study, model comparison)."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ExperimentStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class ExperimentType(str, enum.Enum):
    ablation = "ablation"
    benchmark = "benchmark"
    calibration_study = "calibration_study"
    model_comparison = "model_comparison"


class AblationFlags(BaseModel):
    """Feature flags for ablation experiments."""

    use_base_rates: bool = Field(True, description="Include base-rate anchoring")
    use_evidence_scoring: bool = Field(True, description="Include evidence scoring")
    use_recency_weighting: bool = Field(
        True, description="Apply recency weighting to evidence"
    )
    use_novelty_filter: bool = Field(
        False, description="Filter redundant / low-novelty evidence"
    )
    use_calibration: bool = Field(True, description="Apply post-hoc calibration")
    calibration_scope: str = Field(
        "global",
        description="Scope for calibration: global, domain_specific, target_specific, scenario_specific",
    )
    model_tier: str = Field(
        "A", description="Model tier to use: A, B, or C"
    )
    use_disagreement_second_pass: bool = Field(
        False, description="Run a second pass when model disagreement is high"
    )
    use_voi_gating: bool = Field(
        False, description="Use value-of-information gating for evidence collection"
    )
    evidence_weighting: str = Field(
        "credibility",
        description="Evidence weighting strategy: credibility, uniform, recency_only",
    )

    model_config = ConfigDict(from_attributes=True)


class ExperimentCreate(BaseModel):
    """Schema for creating a new experiment run."""

    name: str = Field(
        ..., min_length=1, max_length=255, description="Experiment name"
    )
    description: str | None = Field(
        None, max_length=5000, description="Detailed description"
    )
    experiment_type: ExperimentType = Field(
        ..., description="Type of experiment"
    )
    config: dict[str, Any] | None = Field(
        None, description="Full experiment configuration"
    )
    ablation_flags: AblationFlags | None = Field(
        None, description="Ablation feature flags (for ablation experiments)"
    )
    model_version_id: UUID | None = Field(
        None, description="Optional model version to use"
    )

    model_config = ConfigDict(from_attributes=True)


class ExperimentResponse(BaseModel):
    """Full experiment run response."""

    id: UUID
    name: str
    description: str | None = None
    experiment_type: ExperimentType
    config: dict[str, Any] | None = None
    ablation_flags: dict[str, Any] | None = None
    model_version_id: UUID | None = None
    status: ExperimentStatus
    results: dict[str, Any] | None = None
    total_cost_usd: float | None = None
    total_questions: int | None = None
    mean_brier_score: float | None = None
    mean_log_score: float | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExperimentComparisonResponse(BaseModel):
    """Comparison of multiple experiment runs with score deltas."""

    experiments: list[ExperimentResponse] = Field(
        ..., description="List of experiment runs being compared"
    )
    score_deltas: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Pairwise score deltas between experiments (brier, log_score, cost)",
    )
    baseline_experiment_id: UUID | None = Field(
        None, description="ID of the baseline experiment for delta computation"
    )

    model_config = ConfigDict(from_attributes=True)
