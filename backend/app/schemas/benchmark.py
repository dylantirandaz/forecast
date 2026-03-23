"""Schemas for benchmark submissions to external platforms."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BenchmarkStatus(str, enum.Enum):
    draft = "draft"
    submitted = "submitted"
    scored = "scored"
    invalidated = "invalidated"


class BenchmarkSubmissionCreate(BaseModel):
    """Schema for creating a benchmark submission."""

    benchmark_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Name of the benchmark (e.g. forecastbench, metaculus_bot_tournament)",
    )
    submission_date: datetime = Field(
        ..., description="Date/time of submission"
    )
    submission_payload: dict[str, Any] | None = Field(
        None, description="The actual submission data"
    )
    experiment_run_id: UUID | None = Field(
        None, description="Experiment run that generated this submission"
    )
    model_version_id: UUID | None = Field(
        None, description="Model version used"
    )
    config: dict[str, Any] | None = Field(
        None, description="Configuration used for the submission"
    )
    notes: str | None = Field(
        None, max_length=5000, description="Additional notes"
    )

    model_config = ConfigDict(from_attributes=True)


class BenchmarkSubmissionResponse(BaseModel):
    """Full benchmark submission response."""

    id: UUID
    benchmark_name: str
    submission_date: datetime
    submission_payload: dict[str, Any] | None = None
    experiment_run_id: UUID | None = None
    model_version_id: UUID | None = None
    config: dict[str, Any] | None = None
    scores: dict[str, Any] | None = None
    status: BenchmarkStatus
    notes: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BenchmarkExportPayload(BaseModel):
    """Formatted payload for submission to ForecastBench or Metaculus."""

    benchmark_name: str = Field(
        ..., description="Target benchmark platform"
    )
    questions: list[dict[str, Any]] = Field(
        ..., description="List of question predictions in platform-specific format"
    )
    model_name: str = Field(
        ..., description="Name / identifier for the model being submitted"
    )
    model_version: str | None = Field(
        None, description="Version string for the model"
    )
    submission_metadata: dict[str, Any] | None = Field(
        None, description="Additional metadata required by the platform"
    )

    model_config = ConfigDict(from_attributes=True)
