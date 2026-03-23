"""Schemas for scenarios attached to forecasting questions."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ScenarioIntensity(StrEnum):
    """Intensity/severity level of a scenario."""

    MINIMAL = "minimal"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    EXTREME = "extreme"


class ScenarioCreate(BaseModel):
    """Schema for creating a new scenario."""

    question_id: UUID = Field(..., description="Parent question ID")
    name: str = Field(
        ..., min_length=3, max_length=200, description="Scenario name"
    )
    description: str | None = Field(
        None, max_length=5000, description="Detailed scenario description"
    )
    intensity: ScenarioIntensity = Field(
        ScenarioIntensity.MODERATE, description="Scenario intensity level"
    )
    assumptions: list[str] = Field(
        default_factory=list, description="Key assumptions for this scenario"
    )
    probability: float | None = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Prior probability assigned to this scenario",
    )

    model_config = ConfigDict(from_attributes=True)

    @field_validator("assumptions")
    @classmethod
    def strip_assumptions(cls, v: list[str]) -> list[str]:
        return [a.strip() for a in v if a.strip()]


class ScenarioUpdate(BaseModel):
    """Schema for updating an existing scenario."""

    name: str | None = Field(None, min_length=3, max_length=200)
    description: str | None = Field(None, max_length=5000)
    intensity: ScenarioIntensity | None = None
    assumptions: list[str] | None = None
    probability: float | None = Field(None, ge=0.0, le=1.0)

    model_config = ConfigDict(from_attributes=True)

    @field_validator("assumptions")
    @classmethod
    def strip_assumptions(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        return [a.strip() for a in v if a.strip()]


class ScenarioResponse(BaseModel):
    """Full scenario response."""

    id: UUID
    question_id: UUID
    name: str
    description: str | None = None
    intensity: ScenarioIntensity
    assumptions: list[str] = Field(default_factory=list)
    probability: float | None = Field(None, ge=0.0, le=1.0)

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
