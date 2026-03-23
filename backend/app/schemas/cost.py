"""Schemas for cost tracking and cost-performance analysis."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class OperationType(str, enum.Enum):
    forecast_run = "forecast_run"
    evidence_scoring = "evidence_scoring"
    base_rate_compute = "base_rate_compute"
    backtest_run = "backtest_run"
    experiment_run = "experiment_run"
    llm_call = "llm_call"
    data_ingestion = "data_ingestion"


class CostLogCreate(BaseModel):
    """Schema for creating a cost log entry."""

    operation_type: OperationType = Field(
        ..., description="Type of operation that incurred this cost"
    )
    reference_id: UUID | None = Field(
        None, description="ID of the entity that triggered this cost"
    )
    reference_type: str | None = Field(
        None,
        max_length=100,
        description="Type of the reference entity (e.g. forecast_run, experiment_run)",
    )
    model_tier: str | None = Field(
        None, max_length=10, description="Model tier: A, B, or C"
    )
    model_name: str | None = Field(
        None, max_length=255, description="Specific model name used"
    )
    input_tokens: int | None = Field(
        None, ge=0, description="Number of input tokens"
    )
    output_tokens: int | None = Field(
        None, ge=0, description="Number of output tokens"
    )
    cost_usd: float = Field(
        ..., ge=0.0, description="Cost in USD"
    )
    latency_ms: int | None = Field(
        None, ge=0, description="Latency in milliseconds"
    )
    metadata: dict[str, Any] | None = Field(
        None, description="Additional metadata"
    )

    model_config = ConfigDict(from_attributes=True)


class CostLogResponse(BaseModel):
    """Full cost log entry response."""

    id: UUID
    operation_type: OperationType
    reference_id: UUID | None = None
    reference_type: str | None = None
    model_tier: str | None = None
    model_name: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float
    latency_ms: int | None = None
    metadata: dict[str, Any] | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CostSummary(BaseModel):
    """Aggregated cost summary across operations."""

    total_cost: float = Field(
        ..., ge=0.0, description="Total cost in USD"
    )
    cost_by_operation: dict[str, float] = Field(
        default_factory=dict,
        description="Cost breakdown by operation type",
    )
    cost_by_model_tier: dict[str, float] = Field(
        default_factory=dict,
        description="Cost breakdown by model tier (A, B, C)",
    )
    cost_per_forecast: float | None = Field(
        None, ge=0.0, description="Average cost per forecast run"
    )
    cost_per_question: float | None = Field(
        None, ge=0.0, description="Average cost per question"
    )
    total_input_tokens: int = Field(0, ge=0)
    total_output_tokens: int = Field(0, ge=0)
    period_start: datetime | None = Field(
        None, description="Start of the summary period"
    )
    period_end: datetime | None = Field(
        None, description="End of the summary period"
    )

    model_config = ConfigDict(from_attributes=True)


class CostPerformanceTradeoff(BaseModel):
    """A single data point for cost vs. accuracy analysis."""

    experiment_id: UUID | None = Field(
        None, description="Associated experiment run"
    )
    label: str = Field(
        ..., description="Label for this data point (e.g. experiment name)"
    )
    cost_usd: float = Field(
        ..., ge=0.0, description="Total cost in USD"
    )
    brier_score: float | None = Field(
        None, ge=0.0, le=2.0, description="Mean Brier score"
    )
    log_score: float | None = Field(
        None, description="Mean log score"
    )
    total_questions: int | None = Field(
        None, ge=0, description="Number of questions evaluated"
    )

    model_config = ConfigDict(from_attributes=True)
