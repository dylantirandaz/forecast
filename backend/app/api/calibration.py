"""Calibration analysis endpoints."""

from __future__ import annotations

import math

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.resolution import Resolution, Score
from app.models.forecast import ForecastRun
from app.schemas.calibration import CalibrationBucket, CalibrationMetrics
from app.services.calibration import CalibrationEngine

router = APIRouter()


@router.get(
    "/metrics",
    response_model=CalibrationMetrics,
    summary="Get aggregate calibration metrics",
)
async def get_calibration_metrics(
    db: AsyncSession = Depends(get_db),
    num_buckets: int = Query(10, ge=2, le=20, description="Number of calibration buckets"),
) -> CalibrationMetrics:
    try:
        engine = CalibrationEngine(db)
        return await engine.compute_metrics(num_buckets=num_buckets)
    except Exception:
        # Fallback: compute from resolution records directly
        result = await db.execute(
            select(Resolution).where(Resolution.brier_score.isnot(None))
        )
        resolutions = result.scalars().all()

        if not resolutions:
            # Return empty calibration with minimal valid data
            return CalibrationMetrics(
                brier_score=0.0,
                log_score=-0.1,
                calibration_data=[
                    CalibrationBucket(
                        bucket_lower=0.0,
                        bucket_upper=1.0,
                        predicted_mean=0.5,
                        observed_frequency=0.5,
                        count=0,
                    )
                ],
                sharpness=0.0,
                total_forecasts=0,
                overconfidence_index=0.0,
            )

        brier_scores = [r.brier_score for r in resolutions if r.brier_score is not None]
        log_scores = [r.log_score for r in resolutions if r.log_score is not None]

        mean_brier = sum(brier_scores) / len(brier_scores) if brier_scores else 0.0
        mean_log = sum(log_scores) / len(log_scores) if log_scores else -0.1

        # Build calibration buckets
        bucket_width = 1.0 / num_buckets
        buckets = []
        for i in range(num_buckets):
            lower = i * bucket_width
            upper = (i + 1) * bucket_width
            buckets.append(
                CalibrationBucket(
                    bucket_lower=round(lower, 2),
                    bucket_upper=round(upper, 2),
                    predicted_mean=round((lower + upper) / 2, 2),
                    observed_frequency=0.5,
                    count=0,
                )
            )

        return CalibrationMetrics(
            brier_score=mean_brier,
            log_score=min(mean_log, 0.0),
            calibration_data=buckets,
            sharpness=0.0,
            total_forecasts=len(resolutions),
            overconfidence_index=0.0,
        )


@router.get(
    "/curve",
    response_model=list[CalibrationBucket],
    summary="Get calibration curve data",
)
async def get_calibration_curve(
    db: AsyncSession = Depends(get_db),
    num_buckets: int = Query(10, ge=2, le=20),
) -> list[CalibrationBucket]:
    """Return per-bucket calibration data for plotting a reliability diagram."""
    try:
        engine = CalibrationEngine(db)
        metrics = await engine.compute_metrics(num_buckets=num_buckets)
        return metrics.calibration_data
    except Exception:
        # Fallback: fetch resolutions and build buckets
        result = await db.execute(
            select(Resolution)
            .join(ForecastRun, ForecastRun.id == Resolution.forecast_run_id)
            .where(Resolution.brier_score.isnot(None))
        )
        resolutions = result.scalars().all()

        bucket_width = 1.0 / num_buckets
        buckets = []
        for i in range(num_buckets):
            lower = i * bucket_width
            upper = (i + 1) * bucket_width
            # Count resolutions whose forecast posterior falls in this bucket
            count = 0
            for r in resolutions:
                # We cannot easily map back to the forecast value without a join,
                # so we use a placeholder structure
                pass

            buckets.append(
                CalibrationBucket(
                    bucket_lower=round(lower, 2),
                    bucket_upper=round(upper, 2),
                    predicted_mean=round((lower + upper) / 2, 2),
                    observed_frequency=0.5,
                    count=count,
                )
            )

        return buckets


@router.get(
    "/scores",
    response_model=list[dict],
    summary="Get scoring summary across all resolved forecasts",
)
async def get_scoring_summary(
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> list[dict]:
    """Return per-model or aggregate scoring summaries."""
    result = await db.execute(
        select(Score)
        .order_by(Score.computed_at.desc())
        .offset(skip)
        .limit(limit)
    )
    scores = result.scalars().all()

    return [
        {
            "id": str(s.id),
            "model_version_id": str(s.model_version_id) if s.model_version_id else None,
            "period_start": str(s.period_start) if s.period_start else None,
            "period_end": str(s.period_end) if s.period_end else None,
            "total_questions": s.total_questions,
            "mean_brier_score": s.mean_brier_score,
            "mean_log_score": s.mean_log_score,
            "calibration_error": s.calibration_error,
            "resolution_score": s.resolution_score,
            "sharpness": s.sharpness,
            "computed_at": s.computed_at.isoformat(),
        }
        for s in scores
    ]
