"""Schemas for evidence and evidence scoring."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    field_validator,
)


class SourceType(StrEnum):
    """Type of evidence source."""

    GOVERNMENT_REPORT = "government_report"
    ACADEMIC_PAPER = "academic_paper"
    NEWS_ARTICLE = "news_article"
    DATASET = "dataset"
    EXPERT_OPINION = "expert_opinion"
    MARKET_DATA = "market_data"
    SURVEY = "survey"
    OTHER = "other"


class DirectionalEffect(StrEnum):
    """How the evidence affects the forecast probability."""

    STRONGLY_INCREASES = "strongly_increases"
    INCREASES = "increases"
    NEUTRAL = "neutral"
    DECREASES = "decreases"
    STRONGLY_DECREASES = "strongly_decreases"


class EvidenceCreate(BaseModel):
    """Schema for submitting a new piece of evidence."""

    question_id: UUID = Field(..., description="Related question")
    title: str = Field(
        ..., min_length=5, max_length=300, description="Evidence title"
    )
    summary: str = Field(
        ...,
        min_length=10,
        max_length=5000,
        description="Summary of the evidence",
    )
    source_type: SourceType = Field(..., description="Type of source")
    source_url: HttpUrl | None = Field(
        None, description="URL of the source material"
    )
    publication_date: datetime | None = Field(
        None, description="When the source was published"
    )
    directional_effect: DirectionalEffect = Field(
        ..., description="How this evidence affects the forecast"
    )
    tags: list[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)

    @field_validator("tags")
    @classmethod
    def tags_lowercase(cls, v: list[str]) -> list[str]:
        return [t.strip().lower() for t in v if t.strip()]


class EvidenceResponse(BaseModel):
    """Full evidence response."""

    id: UUID
    question_id: UUID
    title: str
    summary: str
    source_type: SourceType
    source_url: str | None = None
    publication_date: datetime | None = None
    directional_effect: DirectionalEffect
    tags: list[str] = Field(default_factory=list)

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EvidenceScoreCreate(BaseModel):
    """Schema for scoring a piece of evidence."""

    evidence_id: UUID = Field(..., description="Evidence being scored")
    relevance: float = Field(
        ..., ge=0.0, le=1.0, description="Relevance score"
    )
    credibility: float = Field(
        ..., ge=0.0, le=1.0, description="Source credibility score"
    )
    weight: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Overall weight to assign this evidence",
    )
    rationale: str | None = Field(
        None, max_length=2000, description="Explanation of scores"
    )

    model_config = ConfigDict(from_attributes=True)


class EvidenceScoreResponse(BaseModel):
    """Evidence score response."""

    id: UUID
    evidence_id: UUID
    relevance: float = Field(..., ge=0.0, le=1.0)
    credibility: float = Field(..., ge=0.0, le=1.0)
    weight: float = Field(..., ge=0.0, le=1.0)
    rationale: str | None = None

    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
