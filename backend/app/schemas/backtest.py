"""Schemas for backtesting forecasts against historical data."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BacktestCreate(BaseModel):
    """Schema for initiating a backtest."""

    question_id: UUID = Field(..., description="Question to backtest")
    forecast_run_id: UUID = Field(..., description="Forecast run to evaluate")
    historical_start: datetime = Field(
        ..., description="Start of the historical window"
    )
    historical_end: datetime = Field(
        ..., description="End of the historical window"
    )
    step_months: int = Field(
        3,
        ge=1,
        le=60,
        description="Step size in months for rolling evaluation",
    )

    model_config = ConfigDict(from_attributes=True)

    @field_validator("historical_end")
    @classmethod
    def end_after_start(cls, v: datetime, info) -> datetime:
        start = info.data.get("historical_start")
        if start is not None and v <= start:
            raise ValueError("historical_end must be after historical_start")
        return v


class BacktestResultSummary(BaseModel):
    """Aggregate summary of backtest results."""

    total_periods: int = Field(..., ge=1)
    correct_direction: int = Field(..., ge=0)
    mean_absolute_error: float = Field(..., ge=0.0)
    root_mean_squared_error: float = Field(..., ge=0.0)
    brier_score: float = Field(..., ge=0.0, le=2.0)
    calibration_score: float = Field(
        ..., ge=0.0, le=1.0, description="How well-calibrated the forecasts were"
    )

    model_config = ConfigDict(from_attributes=True)


class BacktestResponse(BaseModel):
    """Full backtest response."""

    id: UUID
    question_id: UUID
    forecast_run_id: UUID
    historical_start: datetime
    historical_end: datetime
    step_months: int
    summary: BacktestResultSummary
    period_results: list[dict[str, float | str | None]] = Field(
        default_factory=list,
        description="Per-period results with date and metrics",
    )

    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
