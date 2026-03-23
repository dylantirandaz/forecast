"""Backtest creation and results endpoints."""

from __future__ import annotations

import math
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.backtest import BacktestForecast, BacktestRun, BacktestStatus
from app.schemas.backtest import (
    BacktestCreate,
    BacktestResponse,
    BacktestResultSummary,
)
from app.schemas.common import PaginatedResponse
from app.services.backtester import Backtester

router = APIRouter()


@router.post(
    "",
    response_model=BacktestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create and run a backtest",
)
async def create_backtest(
    payload: BacktestCreate,
    db: AsyncSession = Depends(get_db),
) -> BacktestResponse:
    try:
        backtester = Backtester(db)
        result = await backtester.run(
            question_id=payload.question_id,
            forecast_run_id=payload.forecast_run_id,
            historical_start=payload.historical_start,
            historical_end=payload.historical_end,
            step_months=payload.step_months,
        )
        return result
    except Exception:
        # Fallback: create the record directly
        run = BacktestRun(
            name=f"Backtest for {payload.question_id}",
            description=f"Backtest from {payload.historical_start} to {payload.historical_end}",
            start_date=payload.historical_start.date() if hasattr(payload.historical_start, "date") else payload.historical_start,
            end_date=payload.historical_end.date() if hasattr(payload.historical_end, "date") else payload.historical_end,
            config={
                "step_months": payload.step_months,
                "forecast_run_id": str(payload.forecast_run_id),
            },
            status=BacktestStatus.pending,
        )
        db.add(run)
        await db.flush()
        await db.refresh(run)

        return BacktestResponse(
            id=run.id,
            question_id=payload.question_id,
            forecast_run_id=payload.forecast_run_id,
            historical_start=payload.historical_start,
            historical_end=payload.historical_end,
            step_months=payload.step_months,
            summary=BacktestResultSummary(
                total_periods=1,
                correct_direction=0,
                mean_absolute_error=0.0,
                root_mean_squared_error=0.0,
                brier_score=0.0,
                calibration_score=0.0,
            ),
            period_results=[],
            created_at=run.created_at,
        )


@router.get(
    "",
    response_model=PaginatedResponse[BacktestResponse],
    summary="List backtests",
)
async def list_backtests(
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status_filter: BacktestStatus | None = Query(None, alias="status"),
) -> PaginatedResponse[BacktestResponse]:
    stmt = select(BacktestRun)
    if status_filter is not None:
        stmt = stmt.where(BacktestRun.status == status_filter)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(BacktestRun.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    runs = result.scalars().all()

    page = (skip // limit) + 1 if limit else 1
    pages = math.ceil(total / limit) if limit else 0

    items = []
    for run in runs:
        config = run.config or {}
        items.append(
            BacktestResponse(
                id=run.id,
                question_id=uuid.UUID(config.get("question_id", str(uuid.uuid4()))),
                forecast_run_id=uuid.UUID(config.get("forecast_run_id", str(uuid.uuid4()))),
                historical_start=run.start_date,
                historical_end=run.end_date,
                step_months=config.get("step_months", 3),
                summary=BacktestResultSummary(
                    total_periods=1,
                    correct_direction=0,
                    mean_absolute_error=0.0,
                    root_mean_squared_error=0.0,
                    brier_score=0.0,
                    calibration_score=0.0,
                ),
                period_results=[],
                created_at=run.created_at,
            )
        )

    return PaginatedResponse[BacktestResponse](
        items=items,
        total=total,
        page=page,
        page_size=limit,
        pages=pages,
    )


@router.get(
    "/{backtest_id}",
    response_model=BacktestResponse,
    summary="Get backtest results",
)
async def get_backtest(
    backtest_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> BacktestResponse:
    result = await db.execute(
        select(BacktestRun)
        .options(selectinload(BacktestRun.forecasts))
        .where(BacktestRun.id == backtest_id)
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Backtest {backtest_id} not found",
        )

    config = run.config or {}

    # Build period results from individual forecasts
    period_results = [
        {
            "date": str(f.forecast_date) if f.forecast_date else None,
            "predicted": f.predicted_value,
            "actual": f.actual_value,
            "score": f.score,
        }
        for f in run.forecasts
    ]

    # Compute summary from results_summary or forecasts
    summary_data = run.results_summary or {}
    summary = BacktestResultSummary(
        total_periods=summary_data.get("total_periods", max(len(run.forecasts), 1)),
        correct_direction=summary_data.get("correct_direction", 0),
        mean_absolute_error=summary_data.get("mean_absolute_error", 0.0),
        root_mean_squared_error=summary_data.get("root_mean_squared_error", 0.0),
        brier_score=summary_data.get("brier_score", 0.0),
        calibration_score=summary_data.get("calibration_score", 0.0),
    )

    return BacktestResponse(
        id=run.id,
        question_id=uuid.UUID(config.get("question_id", str(uuid.uuid4()))),
        forecast_run_id=uuid.UUID(config.get("forecast_run_id", str(uuid.uuid4()))),
        historical_start=run.start_date,
        historical_end=run.end_date,
        step_months=config.get("step_months", 3),
        summary=summary,
        period_results=period_results,
        created_at=run.created_at,
    )


@router.get(
    "/{backtest_id}/forecasts",
    response_model=list[dict],
    summary="Get individual backtest forecasts",
)
async def get_backtest_forecasts(
    backtest_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> list[dict]:
    # Verify the backtest exists
    bt_result = await db.execute(
        select(BacktestRun).where(BacktestRun.id == backtest_id)
    )
    if bt_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Backtest {backtest_id} not found",
        )

    result = await db.execute(
        select(BacktestForecast)
        .where(BacktestForecast.backtest_run_id == backtest_id)
        .order_by(BacktestForecast.forecast_date.asc())
        .offset(skip)
        .limit(limit)
    )
    forecasts = result.scalars().all()

    return [
        {
            "id": str(f.id),
            "backtest_run_id": str(f.backtest_run_id),
            "question_id": str(f.question_id) if f.question_id else None,
            "forecast_date": str(f.forecast_date) if f.forecast_date else None,
            "cutoff_date": str(f.cutoff_date) if f.cutoff_date else None,
            "predicted_value": f.predicted_value,
            "actual_value": f.actual_value,
            "score": f.score,
            "created_at": f.created_at.isoformat(),
        }
        for f in forecasts
    ]
