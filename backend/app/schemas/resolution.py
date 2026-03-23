"""Schemas for question resolution and scoring."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ResolutionCreate(BaseModel):
    """Schema for resolving a question."""

    question_id: UUID = Field(..., description="Question being resolved")
    outcome: bool = Field(
        ..., description="Whether the event occurred (binary questions)"
    )
    outcome_value: float | None = Field(
        None, description="Numeric outcome value if applicable"
    )
    resolution_notes: str = Field(
        ...,
        min_length=10,
        max_length=5000,
        description="Explanation of how the resolution was determined",
    )
    source_url: str | None = Field(
        None,
        max_length=2000,
        description="URL confirming the resolution",
    )

    model_config = ConfigDict(from_attributes=True)


class ResolutionResponse(BaseModel):
    """Full resolution response."""

    id: UUID
    question_id: UUID
    outcome: bool
    outcome_value: float | None = None
    resolution_notes: str
    source_url: str | None = None
    resolved_at: datetime

    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ScoreResponse(BaseModel):
    """Scoring results for a forecast run after resolution."""

    forecast_run_id: UUID
    question_id: UUID
    final_probability: float = Field(..., ge=0.0, le=1.0)
    outcome: bool
    brier_score: float = Field(
        ...,
        ge=0.0,
        le=2.0,
        description="Brier score (lower is better)",
    )
    log_score: float = Field(
        ..., description="Logarithmic scoring rule value"
    )
    resolution_delta: float = Field(
        ...,
        description="Difference between final probability and outcome (0 or 1)",
    )

    model_config = ConfigDict(from_attributes=True)

    @field_validator("log_score")
    @classmethod
    def log_score_not_positive(cls, v: float) -> float:
        if v > 0:
            raise ValueError("log_score should be non-positive")
        return v
