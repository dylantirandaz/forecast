"""Schemas for base-rate analysis."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BaseRateCompute(BaseModel):
    """Input parameters for computing a base rate."""

    question_id: UUID = Field(..., description="Question to compute base rate for")
    reference_class: str = Field(
        ...,
        min_length=5,
        max_length=500,
        description="Description of the reference class",
    )
    time_horizon_years: float = Field(
        ...,
        gt=0.0,
        le=100.0,
        description="Time horizon in years for the base rate",
    )
    geographic_scope: str = Field(
        "nyc",
        max_length=100,
        description="Geographic scope (e.g. nyc, us, global)",
    )
    dataset_sources: list[str] = Field(
        default_factory=list,
        description="Data sources used for the computation",
    )
    adjustments: dict[str, float] = Field(
        default_factory=dict,
        description="Named adjustment factors to apply",
    )

    model_config = ConfigDict(from_attributes=True)

    @field_validator("adjustments")
    @classmethod
    def adjustments_within_range(
        cls, v: dict[str, float]
    ) -> dict[str, float]:
        for name, factor in v.items():
            if not -1.0 <= factor <= 1.0:
                raise ValueError(
                    f"Adjustment '{name}' must be between -1.0 and 1.0, got {factor}"
                )
        return v


class BaseRateResponse(BaseModel):
    """Response containing computed base-rate information."""

    id: UUID
    question_id: UUID
    reference_class: str
    base_rate: float = Field(
        ..., ge=0.0, le=1.0, description="Computed base rate probability"
    )
    adjusted_rate: float = Field(
        ..., ge=0.0, le=1.0, description="Base rate after adjustments"
    )
    sample_size: int = Field(
        ..., ge=0, description="Number of reference-class events in sample"
    )
    time_horizon_years: float
    geographic_scope: str
    dataset_sources: list[str] = Field(default_factory=list)
    adjustments: dict[str, float] = Field(default_factory=dict)
    confidence_interval_lower: float = Field(..., ge=0.0, le=1.0)
    confidence_interval_upper: float = Field(..., ge=0.0, le=1.0)

    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
