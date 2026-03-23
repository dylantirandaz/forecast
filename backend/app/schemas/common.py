"""Common schemas shared across the application."""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response wrapper."""

    items: list[T]
    total: int = Field(..., ge=0, description="Total number of items")
    page: int = Field(..., ge=1, description="Current page number")
    page_size: int = Field(..., ge=1, le=100, description="Items per page")
    pages: int = Field(..., ge=0, description="Total number of pages")

    model_config = ConfigDict(from_attributes=True)


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., examples=["ok"])
    version: str = Field(..., examples=["1.0.0"])
    database: str = Field(..., examples=["connected"])

    model_config = ConfigDict(from_attributes=True)


class ErrorResponse(BaseModel):
    """Standard error response."""

    detail: str = Field(..., description="Human-readable error message")
    code: str | None = Field(
        None, description="Machine-readable error code"
    )
    errors: list[dict[str, Any]] | None = Field(
        None, description="Detailed validation errors"
    )

    model_config = ConfigDict(from_attributes=True)
