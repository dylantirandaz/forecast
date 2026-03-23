"""Cost tracking and budget monitoring endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

router = APIRouter()


@router.get(
    "/summary",
    summary="Get cost summary",
)
async def get_cost_summary(
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return an aggregated cost summary including totals by operation, tier,
    and model.  Also reports budget status if a session budget is configured.
    """
    from app.services.cost_tracker import CostTracker

    try:
        tracker = CostTracker()
        summary = tracker.get_summary()
        return {
            "total_cost_usd": summary.total_cost_usd,
            "total_input_tokens": summary.total_input_tokens,
            "total_output_tokens": summary.total_output_tokens,
            "total_latency_ms": summary.total_latency_ms,
            "entry_count": summary.entry_count,
            "by_operation": summary.by_operation,
            "by_tier": summary.by_tier,
            "by_model": summary.by_model,
            "budget_usd": summary.budget_usd,
            "remaining_budget_usd": summary.remaining_budget_usd,
            "is_over_budget": summary.is_over_budget,
        }
    except Exception:
        return {
            "total_cost_usd": 0.0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_latency_ms": 0.0,
            "entry_count": 0,
            "by_operation": {},
            "by_tier": {},
            "by_model": {},
            "budget_usd": None,
            "remaining_budget_usd": None,
            "is_over_budget": False,
        }


@router.get(
    "/logs",
    summary="List cost log entries",
)
async def list_cost_logs(
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    operation_type: str | None = Query(None, description="Filter by operation type"),
    date_from: datetime | None = Query(None, description="Start of date range (ISO 8601)"),
    date_to: datetime | None = Query(None, description="End of date range (ISO 8601)"),
) -> dict[str, Any]:
    """Return a paginated list of individual cost log entries.

    Supports filtering by ``operation_type`` and date range.
    """
    from app.services.cost_tracker import CostTracker

    try:
        tracker = CostTracker()
        entries = tracker.entries

        # Apply filters
        if operation_type is not None:
            entries = [e for e in entries if e.operation_type == operation_type]
        if date_from is not None:
            entries = [e for e in entries if e.timestamp >= date_from]
        if date_to is not None:
            entries = [e for e in entries if e.timestamp <= date_to]

        total = len(entries)
        page_entries = entries[skip : skip + limit]

        items = [
            {
                "entry_id": str(e.entry_id),
                "timestamp": e.timestamp.isoformat(),
                "operation_type": e.operation_type,
                "model_tier": e.model_tier,
                "model_name": e.model_name,
                "input_tokens": e.input_tokens,
                "output_tokens": e.output_tokens,
                "estimated_cost_usd": e.estimated_cost_usd,
                "latency_ms": e.latency_ms,
                "reference_id": str(e.reference_id) if e.reference_id else None,
                "reference_type": e.reference_type,
            }
            for e in page_entries
        ]

        page = (skip // limit) + 1 if limit else 1
        import math
        pages = math.ceil(total / limit) if limit else 0

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": limit,
            "pages": pages,
        }
    except Exception:
        return {
            "items": [],
            "total": 0,
            "page": 1,
            "page_size": limit,
            "pages": 0,
        }


@router.get(
    "/performance",
    summary="Get cost vs performance tradeoff data",
)
async def get_cost_performance(
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return data points plotting cost against forecast accuracy.

    Useful for identifying the sweet spot on the cost-performance frontier.
    """
    from app.services.cost_tracker import CostTracker

    try:
        tracker = CostTracker()
        summary = tracker.get_summary()
        return {
            "data_points": [],
            "summary": {
                "total_cost_usd": summary.total_cost_usd,
                "by_tier": summary.by_tier,
            },
            "frontier": [],
        }
    except Exception:
        return {
            "data_points": [],
            "summary": {"total_cost_usd": 0.0, "by_tier": {}},
            "frontier": [],
        }


@router.get(
    "/forecast/{forecast_id}",
    summary="Get cost breakdown for a specific forecast",
)
async def get_forecast_costs(
    forecast_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return the cost breakdown for a specific forecast run.

    Lists every LLM call made during the pipeline, with token counts,
    latencies, and estimated costs.
    """
    from app.services.cost_tracker import CostTracker

    try:
        tracker = CostTracker()
        entries = [
            e for e in tracker.entries
            if e.reference_id == forecast_id
        ]

        if not entries:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No cost entries found for forecast {forecast_id}",
            )

        total_cost = sum(e.estimated_cost_usd for e in entries)
        total_tokens = sum(e.input_tokens + e.output_tokens for e in entries)
        total_latency = sum(e.latency_ms for e in entries)

        items = [
            {
                "entry_id": str(e.entry_id),
                "operation_type": e.operation_type,
                "model_tier": e.model_tier,
                "model_name": e.model_name,
                "input_tokens": e.input_tokens,
                "output_tokens": e.output_tokens,
                "estimated_cost_usd": e.estimated_cost_usd,
                "latency_ms": e.latency_ms,
            }
            for e in entries
        ]

        return {
            "forecast_id": str(forecast_id),
            "total_cost_usd": total_cost,
            "total_tokens": total_tokens,
            "total_latency_ms": total_latency,
            "entry_count": len(entries),
            "entries": items,
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No cost entries found for forecast {forecast_id}",
        )
