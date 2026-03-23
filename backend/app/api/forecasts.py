"""Forecast run and update endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.forecast import ForecastRun, ForecastUpdate
from app.models.question import ForecastingQuestion
from app.models.scenario import Scenario
from app.schemas.forecast import (
    ForecastHistory,
    ForecastRunCreate,
    ForecastRunResponse,
    ForecastUpdateCreate,
    ForecastUpdateResponse,
)
from app.services.forecast_engine import ForecastEngine

router = APIRouter()


@router.post(
    "/run",
    response_model=ForecastRunResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Run a new forecast for a question",
)
async def run_forecast(
    payload: ForecastRunCreate,
    db: AsyncSession = Depends(get_db),
) -> ForecastRunResponse:
    # Validate that the question exists
    q_result = await db.execute(
        select(ForecastingQuestion).where(ForecastingQuestion.id == payload.question_id)
    )
    question = q_result.scalar_one_or_none()
    if question is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question {payload.question_id} not found",
        )

    # Validate scenario if provided
    if payload.scenario_id is not None:
        s_result = await db.execute(
            select(Scenario).where(Scenario.id == payload.scenario_id)
        )
        if s_result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scenario {payload.scenario_id} not found",
            )

    # Create the forecast run via the engine (or directly if engine unavailable)
    try:
        engine = ForecastEngine(db)
        forecast_run = await engine.create_run(
            question_id=payload.question_id,
            scenario_id=payload.scenario_id,
            initial_probability=payload.initial_probability,
            rationale=payload.rationale,
            methodology=payload.methodology,
        )
    except Exception:
        # Fallback: create directly
        forecast_run = ForecastRun(
            question_id=payload.question_id,
            scenario_id=payload.scenario_id,
            prior_value=payload.initial_probability,
            posterior_value=payload.initial_probability,
            rationale=payload.rationale,
        )
        db.add(forecast_run)
        await db.flush()
        await db.refresh(forecast_run)

    return ForecastRunResponse(
        id=forecast_run.id,
        question_id=forecast_run.question_id,
        scenario_id=forecast_run.scenario_id,
        initial_probability=forecast_run.prior_value or 0.5,
        current_probability=forecast_run.posterior_value or forecast_run.prior_value or 0.5,
        rationale=forecast_run.rationale or "",
        methodology=payload.methodology,
        update_count=0,
        created_at=forecast_run.created_at,
        updated_at=forecast_run.created_at,
    )


@router.get(
    "/{forecast_id}",
    response_model=ForecastRunResponse,
    summary="Get forecast detail with full history",
)
async def get_forecast(
    forecast_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ForecastRunResponse:
    result = await db.execute(
        select(ForecastRun)
        .options(selectinload(ForecastRun.updates))
        .where(ForecastRun.id == forecast_id)
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Forecast run {forecast_id} not found",
        )

    return ForecastRunResponse(
        id=run.id,
        question_id=run.question_id,
        scenario_id=run.scenario_id,
        initial_probability=run.prior_value or 0.5,
        current_probability=run.posterior_value or run.prior_value or 0.5,
        rationale=run.rationale or "",
        methodology=None,
        update_count=len(run.updates),
        created_at=run.created_at,
        updated_at=run.created_at,
    )


@router.post(
    "/{forecast_id}/update",
    response_model=ForecastUpdateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add evidence and update a forecast",
)
async def update_forecast(
    forecast_id: uuid.UUID,
    payload: ForecastUpdateCreate,
    db: AsyncSession = Depends(get_db),
) -> ForecastUpdateResponse:
    # Verify the forecast run exists
    result = await db.execute(
        select(ForecastRun)
        .options(selectinload(ForecastRun.updates))
        .where(ForecastRun.id == forecast_id)
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Forecast run {forecast_id} not found",
        )

    next_order = len(run.updates) + 1

    update = ForecastUpdate(
        forecast_run_id=forecast_id,
        update_order=next_order,
        prior_value=payload.previous_probability,
        posterior_value=payload.new_probability,
        evidence_item_id=payload.evidence_ids[0] if payload.evidence_ids else None,
        rationale=payload.reason,
    )
    db.add(update)

    # Update the run's posterior
    run.posterior_value = payload.new_probability

    await db.flush()
    await db.refresh(update)

    return ForecastUpdateResponse(
        id=update.id,
        forecast_run_id=update.forecast_run_id,
        new_probability=update.posterior_value or 0.5,
        previous_probability=update.prior_value or 0.5,
        reason=update.rationale or "",
        evidence_ids=payload.evidence_ids,
        created_at=update.created_at,
    )


@router.get(
    "/history/{question_id}",
    response_model=list[ForecastHistory],
    summary="Get forecast history for a question",
)
async def get_forecast_history(
    question_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[ForecastHistory]:
    result = await db.execute(
        select(ForecastRun)
        .options(selectinload(ForecastRun.updates))
        .where(ForecastRun.question_id == question_id)
        .order_by(ForecastRun.created_at.desc())
    )
    runs = result.scalars().all()

    if not runs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No forecast runs found for question {question_id}",
        )

    histories: list[ForecastHistory] = []
    for run in runs:
        updates = [
            ForecastUpdateResponse(
                id=u.id,
                forecast_run_id=u.forecast_run_id,
                new_probability=u.posterior_value or 0.5,
                previous_probability=u.prior_value or 0.5,
                reason=u.rationale or "",
                evidence_ids=[u.evidence_item_id] if u.evidence_item_id else [],
                created_at=u.created_at,
            )
            for u in run.updates
        ]
        histories.append(
            ForecastHistory(
                forecast_run_id=run.id,
                question_id=run.question_id,
                initial_probability=run.prior_value or 0.5,
                current_probability=run.posterior_value or run.prior_value or 0.5,
                updates=updates,
                update_count=len(updates),
            )
        )

    return histories


@router.get(
    "/compare",
    response_model=list[ForecastRunResponse],
    summary="Compare forecasts across scenarios",
)
async def compare_forecasts(
    question_id: uuid.UUID = Query(..., description="Question to compare forecasts for"),
    scenario_ids: list[uuid.UUID] = Query(
        default=[], alias="scenario_id", description="Scenario IDs to compare"
    ),
    db: AsyncSession = Depends(get_db),
) -> list[ForecastRunResponse]:
    stmt = (
        select(ForecastRun)
        .options(selectinload(ForecastRun.updates))
        .where(ForecastRun.question_id == question_id)
    )

    if scenario_ids:
        stmt = stmt.where(ForecastRun.scenario_id.in_(scenario_ids))

    result = await db.execute(stmt.order_by(ForecastRun.created_at.desc()))
    runs = result.scalars().all()

    return [
        ForecastRunResponse(
            id=run.id,
            question_id=run.question_id,
            scenario_id=run.scenario_id,
            initial_probability=run.prior_value or 0.5,
            current_probability=run.posterior_value or run.prior_value or 0.5,
            rationale=run.rationale or "",
            methodology=None,
            update_count=len(run.updates),
            created_at=run.created_at,
            updated_at=run.created_at,
        )
        for run in runs
    ]
