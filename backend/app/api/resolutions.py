"""Resolution endpoints for resolving forecasts and recording outcomes."""

from __future__ import annotations

import math
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.forecast import ForecastRun
from app.models.question import ForecastingQuestion, QuestionStatus
from app.models.resolution import Resolution
from app.schemas.resolution import ResolutionCreate, ResolutionResponse, ScoreResponse
from app.schemas.common import PaginatedResponse
from app.services.resolution_engine import ResolutionEngine

router = APIRouter()


@router.post(
    "",
    response_model=ResolutionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Resolve a forecast / question",
)
async def create_resolution(
    payload: ResolutionCreate,
    db: AsyncSession = Depends(get_db),
) -> ResolutionResponse:
    # Verify the question exists
    q_result = await db.execute(
        select(ForecastingQuestion).where(ForecastingQuestion.id == payload.question_id)
    )
    question = q_result.scalar_one_or_none()
    if question is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question {payload.question_id} not found",
        )

    # Find the latest forecast run for this question
    fr_result = await db.execute(
        select(ForecastRun)
        .where(ForecastRun.question_id == payload.question_id)
        .order_by(ForecastRun.created_at.desc())
        .limit(1)
    )
    forecast_run = fr_result.scalar_one_or_none()

    try:
        engine = ResolutionEngine(db)
        resolution = await engine.resolve(
            question_id=payload.question_id,
            outcome=payload.outcome,
            outcome_value=payload.outcome_value,
            resolution_notes=payload.resolution_notes,
            source_url=payload.source_url,
        )
    except Exception:
        # Fallback: create resolution directly
        actual_value = 1.0 if payload.outcome else 0.0
        if payload.outcome_value is not None:
            actual_value = payload.outcome_value

        # Compute brier and log scores if we have a forecast
        brier_score = None
        log_score = None
        if forecast_run and forecast_run.posterior_value is not None:
            p = forecast_run.posterior_value
            outcome_val = 1.0 if payload.outcome else 0.0
            brier_score = (p - outcome_val) ** 2
            import math as _math

            eps = 1e-15
            if payload.outcome:
                log_score = _math.log(max(p, eps))
            else:
                log_score = _math.log(max(1.0 - p, eps))

        resolution = Resolution(
            question_id=payload.question_id,
            forecast_run_id=forecast_run.id if forecast_run else None,
            actual_value=actual_value,
            brier_score=brier_score,
            log_score=log_score,
            notes=payload.resolution_notes,
        )
        db.add(resolution)

        # Mark question as resolved
        question.status = QuestionStatus.resolved
        question.resolution_value = actual_value

        await db.flush()
        await db.refresh(resolution)

    return ResolutionResponse(
        id=resolution.id,
        question_id=resolution.question_id,
        outcome=payload.outcome,
        outcome_value=payload.outcome_value,
        resolution_notes=resolution.notes or payload.resolution_notes,
        source_url=payload.source_url,
        resolved_at=resolution.resolved_at,
        created_at=resolution.resolved_at,
    )


@router.get(
    "",
    response_model=PaginatedResponse[ResolutionResponse],
    summary="List resolutions",
)
async def list_resolutions(
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    question_id: uuid.UUID | None = Query(None, description="Filter by question"),
) -> PaginatedResponse[ResolutionResponse]:
    stmt = select(Resolution)
    if question_id is not None:
        stmt = stmt.where(Resolution.question_id == question_id)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(Resolution.resolved_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    resolutions = result.scalars().all()

    page = (skip // limit) + 1 if limit else 1
    pages = math.ceil(total / limit) if limit else 0

    items = [
        ResolutionResponse(
            id=r.id,
            question_id=r.question_id,
            outcome=(r.actual_value or 0.0) >= 0.5,
            outcome_value=r.actual_value,
            resolution_notes=r.notes or "",
            source_url=None,
            resolved_at=r.resolved_at,
            created_at=r.resolved_at,
        )
        for r in resolutions
    ]

    return PaginatedResponse[ResolutionResponse](
        items=items,
        total=total,
        page=page,
        page_size=limit,
        pages=pages,
    )


@router.get(
    "/{resolution_id}",
    response_model=ResolutionResponse,
    summary="Get resolution detail",
)
async def get_resolution(
    resolution_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ResolutionResponse:
    result = await db.execute(
        select(Resolution).where(Resolution.id == resolution_id)
    )
    resolution = result.scalar_one_or_none()
    if resolution is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Resolution {resolution_id} not found",
        )

    return ResolutionResponse(
        id=resolution.id,
        question_id=resolution.question_id,
        outcome=(resolution.actual_value or 0.0) >= 0.5,
        outcome_value=resolution.actual_value,
        resolution_notes=resolution.notes or "",
        source_url=None,
        resolved_at=resolution.resolved_at,
        created_at=resolution.resolved_at,
    )
