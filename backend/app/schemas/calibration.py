"""Schemas for calibration analysis and calibration runs."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CalibrationBucket(BaseModel):
    """A single calibration bucket (e.g. 0.2-0.3 predicted range)."""

    bucket_lower: float = Field(..., ge=0.0, le=1.0)
    bucket_upper: float = Field(..., ge=0.0, le=1.0)
    predicted_mean: float = Field(
        ..., ge=0.0, le=1.0, description="Mean predicted probability in bucket"
    )
    observed_frequency: float = Field(
        ..., ge=0.0, le=1.0, description="Observed outcome frequency in bucket"
    )
    count: int = Field(
        ..., ge=0, description="Number of forecasts in this bucket"
    )

    model_config = ConfigDict(from_attributes=True)

    @field_validator("bucket_upper")
    @classmethod
    def upper_ge_lower(cls, v: float, info) -> float:
        lower = info.data.get("bucket_lower")
        if lower is not None and v < lower:
            raise ValueError("bucket_upper must be >= bucket_lower")
        return v


class CalibrationMetrics(BaseModel):
    """Aggregate calibration metrics across all forecasts."""

    brier_score: float = Field(
        ...,
        ge=0.0,
        le=2.0,
        description="Mean Brier score across resolved questions",
    )
    log_score: float = Field(
        ..., description="Mean logarithmic score (non-positive)"
    )
    calibration_data: list[CalibrationBucket] = Field(
        ..., description="Per-bucket calibration data"
    )
    sharpness: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Sharpness (variance of predicted probabilities)",
    )
    total_forecasts: int = Field(
        ..., ge=0, description="Number of resolved forecasts analysed"
    )
    overconfidence_index: float = Field(
        0.0,
        description="Positive means overconfident, negative means underconfident",
    )

    model_config = ConfigDict(from_attributes=True)

    @field_validator("calibration_data")
    @classmethod
    def must_have_buckets(
        cls, v: list[CalibrationBucket]
    ) -> list[CalibrationBucket]:
        if not v:
            raise ValueError("calibration_data must contain at least one bucket")
        return v


class CalibrationScope(str, enum.Enum):
    global_ = "global"
    domain_specific = "domain_specific"
    target_specific = "target_specific"
    scenario_specific = "scenario_specific"


class CalibrationMethod(str, enum.Enum):
    platt_scaling = "platt_scaling"
    isotonic_regression = "isotonic_regression"
    histogram_binning = "histogram_binning"
    none = "none"


class CalibrationRunCreate(BaseModel):
    """Schema for creating a calibration run."""

    name: str = Field(
        ..., min_length=1, max_length=255, description="Calibration run name"
    )
    scope: CalibrationScope = Field(
        ..., description="Scope of calibration"
    )
    domain: str | None = Field(
        None, max_length=255, description="Domain (e.g. housing_supply, prices)"
    )
    target_metric: str | None = Field(
        None, max_length=255, description="Target metric being calibrated"
    )
    method: CalibrationMethod = Field(
        ..., description="Calibration method to apply"
    )
    n_forecasts: int = Field(
        ..., ge=1, description="Number of forecasts used for calibration"
    )
    calibration_params: dict[str, Any] | None = Field(
        None, description="Stored calibration transform parameters"
    )
    bucket_data: dict[str, Any] | None = Field(
        None, description="Reliability diagram data"
    )

    model_config = ConfigDict(from_attributes=True)


class CalibrationRunResponse(BaseModel):
    """Full calibration run response."""

    id: UUID
    name: str
    scope: CalibrationScope
    domain: str | None = None
    target_metric: str | None = None
    method: CalibrationMethod
    n_forecasts: int
    pre_calibration_brier: float | None = None
    post_calibration_brier: float | None = None
    pre_calibration_log_score: float | None = None
    post_calibration_log_score: float | None = None
    calibration_params: dict[str, Any] | None = None
    bucket_data: dict[str, Any] | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
