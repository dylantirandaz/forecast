"""CRUD endpoints for scenarios."""

from __future__ import annotations

import math
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.scenario import Scenario
from app.models.question import ForecastingQuestion
from app.schemas.scenario import ScenarioCreate, ScenarioResponse, ScenarioUpdate
from app.schemas.common import PaginatedResponse

router = APIRouter()


@router.post(
    "",
    response_model=ScenarioResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new scenario",
)
async def create_scenario(
    payload: ScenarioCreate,
    db: AsyncSession = Depends(get_db),
) -> ScenarioResponse:
    # Verify the parent question exists
    q_result = await db.execute(
        select(ForecastingQuestion).where(ForecastingQuestion.id == payload.question_id)
    )
    if q_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question {payload.question_id} not found",
        )

    scenario = Scenario(
        name=payload.name,
        narrative=payload.description,
        intensity=payload.intensity,
        assumptions={"items": payload.assumptions} if payload.assumptions else None,
    )
    db.add(scenario)
    await db.flush()
    await db.refresh(scenario)
    return ScenarioResponse.model_validate(scenario)


@router.get(
    "",
    response_model=PaginatedResponse[ScenarioResponse],
    summary="List scenarios with pagination",
)
async def list_scenarios(
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    question_id: uuid.UUID | None = Query(None, description="Filter by question"),
) -> PaginatedResponse[ScenarioResponse]:
    stmt = select(Scenario)

    # Note: question_id filtering depends on how scenarios are linked to questions
    # in future schema revisions. For now we list all scenarios.

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(Scenario.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    scenarios = result.scalars().all()

    page = (skip // limit) + 1 if limit else 1
    pages = math.ceil(total / limit) if limit else 0

    return PaginatedResponse[ScenarioResponse](
        items=[ScenarioResponse.model_validate(s) for s in scenarios],
        total=total,
        page=page,
        page_size=limit,
        pages=pages,
    )


@router.get(
    "/compare",
    response_model=list[ScenarioResponse],
    summary="Compare scenarios for a given question",
)
async def compare_scenarios(
    question_id: uuid.UUID = Query(..., description="Question ID to compare scenarios for"),
    db: AsyncSession = Depends(get_db),
) -> list[ScenarioResponse]:
    """Return all scenarios associated with a question for side-by-side comparison."""
    # Scenarios are linked via forecast_runs. Fetch scenarios that have runs
    # for this question.
    from app.models.forecast import ForecastRun

    stmt = (
        select(Scenario)
        .join(ForecastRun, ForecastRun.scenario_id == Scenario.id)
        .where(ForecastRun.question_id == question_id)
        .distinct()
    )
    result = await db.execute(stmt)
    scenarios = result.scalars().all()
    return [ScenarioResponse.model_validate(s) for s in scenarios]


@router.get(
    "/{scenario_id}",
    response_model=ScenarioResponse,
    summary="Get a single scenario by ID",
)
async def get_scenario(
    scenario_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ScenarioResponse:
    result = await db.execute(
        select(Scenario).where(Scenario.id == scenario_id)
    )
    scenario = result.scalar_one_or_none()
    if scenario is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scenario {scenario_id} not found",
        )
    return ScenarioResponse.model_validate(scenario)


@router.put(
    "/{scenario_id}",
    response_model=ScenarioResponse,
    summary="Update a scenario",
)
async def update_scenario(
    scenario_id: uuid.UUID,
    payload: ScenarioUpdate,
    db: AsyncSession = Depends(get_db),
) -> ScenarioResponse:
    result = await db.execute(
        select(Scenario).where(Scenario.id == scenario_id)
    )
    scenario = result.scalar_one_or_none()
    if scenario is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scenario {scenario_id} not found",
        )

    update_data = payload.model_dump(exclude_unset=True)
    # Map schema fields to model fields where names differ
    field_map: dict[str, str] = {"description": "narrative"}
    for field, value in update_data.items():
        model_field = field_map.get(field, field)
        if field == "assumptions" and isinstance(value, list):
            setattr(scenario, model_field, {"items": value})
        else:
            setattr(scenario, model_field, value)

    await db.flush()
    await db.refresh(scenario)
    return ScenarioResponse.model_validate(scenario)
