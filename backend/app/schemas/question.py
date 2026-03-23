"""Schemas for forecasting questions."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TargetType(StrEnum):
    """Type of forecasting target."""

    BINARY = "binary"
    NUMERIC = "numeric"
    CATEGORICAL = "categorical"
    DATE = "date"


class QuestionStatus(StrEnum):
    """Status of a forecasting question."""

    DRAFT = "draft"
    OPEN = "open"
    CLOSED = "closed"
    RESOLVED = "resolved"
    ANNULLED = "annulled"


class QuestionCreate(BaseModel):
    """Schema for creating a new question."""

    title: str = Field(
        ..., min_length=10, max_length=500, description="Question title"
    )
    description: str | None = Field(
        None, max_length=5000, description="Detailed description"
    )
    target_type: TargetType = Field(..., description="Type of forecast target")
    resolution_criteria: str = Field(
        ...,
        min_length=10,
        max_length=5000,
        description="Criteria for resolving the question",
    )
    resolution_date: datetime = Field(
        ..., description="Expected date of resolution"
    )
    category: str | None = Field(
        None, max_length=100, description="Question category"
    )
    tags: list[str] = Field(
        default_factory=list, description="Tags for categorisation"
    )

    model_config = ConfigDict(from_attributes=True)

    @field_validator("resolution_date")
    @classmethod
    def resolution_date_must_be_future(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("resolution_date must be timezone-aware")
        return v

    @field_validator("tags")
    @classmethod
    def tags_must_be_lowercase(cls, v: list[str]) -> list[str]:
        return [tag.strip().lower() for tag in v]


class QuestionUpdate(BaseModel):
    """Schema for updating an existing question."""

    title: str | None = Field(None, min_length=10, max_length=500)
    description: str | None = Field(None, max_length=5000)
    resolution_criteria: str | None = Field(None, min_length=10, max_length=5000)
    resolution_date: datetime | None = None
    category: str | None = Field(None, max_length=100)
    tags: list[str] | None = None
    status: QuestionStatus | None = None

    model_config = ConfigDict(from_attributes=True)

    @field_validator("tags")
    @classmethod
    def tags_must_be_lowercase(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        return [tag.strip().lower() for tag in v]


class QuestionResponse(BaseModel):
    """Full question response including relationships."""

    id: UUID
    title: str
    description: str | None = None
    target_type: TargetType
    resolution_criteria: str
    resolution_date: datetime
    category: str | None = None
    tags: list[str] = Field(default_factory=list)
    status: QuestionStatus

    # Relationships
    scenario_count: int = Field(0, description="Number of attached scenarios")
    latest_forecast: float | None = Field(
        None, ge=0.0, le=1.0, description="Most recent forecast probability"
    )
    evidence_count: int = Field(0, description="Number of evidence items")

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class QuestionList(BaseModel):
    """Lightweight question representation for list views."""

    id: UUID
    title: str
    target_type: TargetType
    status: QuestionStatus
    category: str | None = None
    latest_forecast: float | None = Field(None, ge=0.0, le=1.0)
    resolution_date: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
