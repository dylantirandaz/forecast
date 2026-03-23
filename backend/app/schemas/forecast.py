"""Schemas for forecasts and forecast updates."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ForecastRunCreate(BaseModel):
    """Schema for initiating a new forecast run."""

    question_id: UUID = Field(..., description="Question being forecast")
    scenario_id: UUID | None = Field(
        None, description="Optional scenario context"
    )
    initial_probability: float = Field(
        ..., ge=0.0, le=1.0, description="Starting probability estimate"
    )
    rationale: str = Field(
        ...,
        min_length=10,
        max_length=5000,
        description="Reasoning behind the initial estimate",
    )
    methodology: str | None = Field(
        None,
        max_length=500,
        description="Methodology used (e.g. base-rate, model, expert)",
    )

    model_config = ConfigDict(from_attributes=True)


class ForecastRunResponse(BaseModel):
    """Full forecast run response."""

    id: UUID
    question_id: UUID
    scenario_id: UUID | None = None
    initial_probability: float = Field(..., ge=0.0, le=1.0)
    current_probability: float = Field(..., ge=0.0, le=1.0)
    rationale: str
    methodology: str | None = None
    update_count: int = Field(0, ge=0)

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ForecastUpdateCreate(BaseModel):
    """Schema for submitting a forecast update."""

    forecast_run_id: UUID = Field(..., description="Parent forecast run")
    new_probability: float = Field(
        ..., ge=0.0, le=1.0, description="Updated probability"
    )
    previous_probability: float = Field(
        ..., ge=0.0, le=1.0, description="Probability before this update"
    )
    reason: str = Field(
        ...,
        min_length=5,
        max_length=5000,
        description="Reason for the update",
    )
    evidence_ids: list[UUID] = Field(
        default_factory=list,
        description="Evidence items motivating the update",
    )

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def probability_must_change(self) -> ForecastUpdateCreate:
        if self.new_probability == self.previous_probability:
            raise ValueError(
                "new_probability must differ from previous_probability"
            )
        return self


class ForecastUpdateResponse(BaseModel):
    """Response for a single forecast update."""

    id: UUID
    forecast_run_id: UUID
    new_probability: float = Field(..., ge=0.0, le=1.0)
    previous_probability: float = Field(..., ge=0.0, le=1.0)
    reason: str
    evidence_ids: list[UUID] = Field(default_factory=list)

    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ForecastHistory(BaseModel):
    """Chronological list of forecast updates for a run."""

    forecast_run_id: UUID
    question_id: UUID
    initial_probability: float = Field(..., ge=0.0, le=1.0)
    current_probability: float = Field(..., ge=0.0, le=1.0)
    updates: list[ForecastUpdateResponse] = Field(default_factory=list)
    update_count: int = Field(0, ge=0)

    model_config = ConfigDict(from_attributes=True)

    @field_validator("updates")
    @classmethod
    def sort_updates_chronologically(
        cls, v: list[ForecastUpdateResponse]
    ) -> list[ForecastUpdateResponse]:
        return sorted(v, key=lambda u: u.created_at)
