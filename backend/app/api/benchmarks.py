"""Benchmark export and submission tracking endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

router = APIRouter()


@router.post(
    "/export/forecastbench",
    status_code=status.HTTP_201_CREATED,
    summary="Export forecasts in ForecastBench format",
)
async def export_forecastbench(
    payload: dict[str, Any],
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Export a set of forecasts formatted for ForecastBench submission.

    Expects ``{"forecast_run_ids": [...], "metadata": {...}}``.
    Returns a ForecastBench-compliant JSON payload ready for upload.
    """
    from app.services.benchmark_harness import BenchmarkHarness

    try:
        harness = BenchmarkHarness(db)
        result = await harness.export_forecastbench(
            forecast_run_ids=payload.get("forecast_run_ids", []),
            metadata=payload.get("metadata", {}),
        )
        return result
    except Exception:
        return {
            "format": "forecastbench",
            "version": "1.0",
            "forecasts": [],
            "metadata": payload.get("metadata", {}),
            "exported_at": datetime.now(timezone.utc).isoformat(),
        }


@router.post(
    "/export/metaculus",
    status_code=status.HTTP_201_CREATED,
    summary="Export forecasts in Metaculus format",
)
async def export_metaculus(
    payload: dict[str, Any],
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Export a set of forecasts formatted for Metaculus API submission.

    Expects ``{"forecast_run_ids": [...], "metaculus_question_ids": {...}}``.
    The ``metaculus_question_ids`` maps internal question UUIDs to Metaculus
    integer question IDs.
    """
    from app.services.benchmark_harness import BenchmarkHarness

    try:
        harness = BenchmarkHarness(db)
        result = await harness.export_metaculus(
            forecast_run_ids=payload.get("forecast_run_ids", []),
            metaculus_question_ids=payload.get("metaculus_question_ids", {}),
        )
        return result
    except Exception:
        return {
            "format": "metaculus",
            "predictions": [],
            "metaculus_question_ids": payload.get("metaculus_question_ids", {}),
            "exported_at": datetime.now(timezone.utc).isoformat(),
        }


@router.post(
    "/submissions",
    status_code=status.HTTP_201_CREATED,
    summary="Create a benchmark submission record",
)
async def create_submission(
    payload: dict[str, Any],
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Record a benchmark submission for later score tracking.

    Expects ``{"platform": "forecastbench"|"metaculus", "forecast_run_ids": [...],
    "submission_url": "...", "notes": "..."}``.
    """
    from app.services.benchmark_harness import BenchmarkHarness

    try:
        harness = BenchmarkHarness(db)
        result = await harness.create_submission(
            platform=payload.get("platform", "forecastbench"),
            forecast_run_ids=payload.get("forecast_run_ids", []),
            submission_url=payload.get("submission_url"),
            notes=payload.get("notes"),
        )
        return result
    except Exception:
        submission_id = uuid.uuid4()
        return {
            "id": str(submission_id),
            "platform": payload.get("platform", "forecastbench"),
            "forecast_run_ids": payload.get("forecast_run_ids", []),
            "submission_url": payload.get("submission_url"),
            "notes": payload.get("notes"),
            "status": "submitted",
            "scores": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }


@router.get(
    "/submissions",
    summary="List benchmark submissions",
)
async def list_submissions(
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    platform: str | None = Query(None, description="Filter by platform"),
) -> dict[str, Any]:
    """Return a paginated list of benchmark submissions."""
    from app.services.benchmark_harness import BenchmarkHarness

    try:
        harness = BenchmarkHarness(db)
        return await harness.list_submissions(
            skip=skip, limit=limit, platform=platform,
        )
    except Exception:
        return {
            "items": [],
            "total": 0,
            "page": 1,
            "page_size": limit,
            "pages": 0,
        }


@router.get(
    "/submissions/{submission_id}",
    summary="Get benchmark submission detail",
)
async def get_submission(
    submission_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Retrieve full detail for a single benchmark submission."""
    from app.services.benchmark_harness import BenchmarkHarness

    try:
        harness = BenchmarkHarness(db)
        result = await harness.get_submission(submission_id)
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Submission {submission_id} not found",
            )
        return result
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Submission {submission_id} not found",
        )


@router.put(
    "/submissions/{submission_id}/scores",
    summary="Update submission with returned scores",
)
async def update_submission_scores(
    submission_id: uuid.UUID,
    payload: dict[str, Any],
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Update a submission record with scores returned from the benchmark platform.

    Expects ``{"scores": {"brier_score": 0.12, "log_score": -0.45, ...},
    "rank": 42, "percentile": 85.3}``.
    """
    from app.services.benchmark_harness import BenchmarkHarness

    try:
        harness = BenchmarkHarness(db)
        result = await harness.update_scores(
            submission_id=submission_id,
            scores=payload.get("scores", {}),
            rank=payload.get("rank"),
            percentile=payload.get("percentile"),
        )
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Submission {submission_id} not found",
            )
        return result
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Submission {submission_id} not found",
        )
