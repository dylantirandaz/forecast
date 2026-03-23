"""Schemas for comparing forecasts across scenarios."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .scenario import ScenarioIntensity


class ScenarioForecastSummary(BaseModel):
    """Forecast summary for a single scenario within a comparison."""

    scenario_id: UUID
    scenario_name: str
    intensity: ScenarioIntensity
    current_probability: float = Field(..., ge=0.0, le=1.0)
    initial_probability: float = Field(..., ge=0.0, le=1.0)
    probability_change: float = Field(
        ..., description="Delta from initial to current probability"
    )
    update_count: int = Field(0, ge=0)
    last_updated: datetime

    model_config = ConfigDict(from_attributes=True)


class ScenarioComparisonRequest(BaseModel):
    """Request to compare forecasts across scenarios for a question."""

    question_id: UUID = Field(..., description="Question to compare scenarios for")
    scenario_ids: list[UUID] = Field(
        ...,
        min_length=2,
        description="At least two scenario IDs to compare",
    )

    model_config = ConfigDict(from_attributes=True)

    @field_validator("scenario_ids")
    @classmethod
    def unique_scenarios(cls, v: list[UUID]) -> list[UUID]:
        if len(set(v)) != len(v):
            raise ValueError("scenario_ids must be unique")
        return v


class ScenarioComparisonResponse(BaseModel):
    """Response containing per-scenario forecast summaries."""

    question_id: UUID
    question_title: str
    scenarios: list[ScenarioForecastSummary] = Field(
        ..., description="Per-scenario forecast summaries"
    )
    spread: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Range between highest and lowest current probability",
    )
    mean_probability: float = Field(
        ..., ge=0.0, le=1.0, description="Mean probability across scenarios"
    )

    model_config = ConfigDict(from_attributes=True)
