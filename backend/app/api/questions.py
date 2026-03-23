"""CRUD endpoints for forecasting questions."""

from __future__ import annotations

import math
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.question import ForecastingQuestion, QuestionStatus
from app.schemas.question import (
    QuestionCreate,
    QuestionList,
    QuestionResponse,
    QuestionUpdate,
)
from app.schemas.common import PaginatedResponse

router = APIRouter()


@router.post(
    "",
    response_model=QuestionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new forecasting question",
)
async def create_question(
    payload: QuestionCreate,
    db: AsyncSession = Depends(get_db),
) -> QuestionResponse:
    question = ForecastingQuestion(
        title=payload.title,
        description=payload.description,
        target_type=payload.target_type,
        resolution_criteria=payload.resolution_criteria,
        resolution_date=payload.resolution_date,
    )
    db.add(question)
    await db.flush()
    await db.refresh(question)
    return QuestionResponse.model_validate(question)


@router.get(
    "",
    response_model=PaginatedResponse[QuestionList],
    summary="List forecasting questions with pagination and filters",
)
async def list_questions(
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=100, description="Max records to return"),
    status_filter: QuestionStatus | None = Query(None, alias="status", description="Filter by status"),
    target_type: str | None = Query(None, description="Filter by target type"),
    search: str | None = Query(None, description="Search in title and description"),
) -> PaginatedResponse[QuestionList]:
    stmt = select(ForecastingQuestion)

    if status_filter is not None:
        stmt = stmt.where(ForecastingQuestion.status == status_filter)
    if target_type is not None:
        stmt = stmt.where(ForecastingQuestion.target_type == target_type)
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(
            ForecastingQuestion.title.ilike(pattern)
            | ForecastingQuestion.description.ilike(pattern)
        )

    # Total count
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    # Fetch page
    stmt = stmt.order_by(ForecastingQuestion.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    questions = result.scalars().all()

    page = (skip // limit) + 1 if limit else 1
    pages = math.ceil(total / limit) if limit else 0

    return PaginatedResponse[QuestionList](
        items=[QuestionList.model_validate(q) for q in questions],
        total=total,
        page=page,
        page_size=limit,
        pages=pages,
    )


@router.get(
    "/{question_id}",
    response_model=QuestionResponse,
    summary="Get a single forecasting question by ID",
)
async def get_question(
    question_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> QuestionResponse:
    result = await db.execute(
        select(ForecastingQuestion).where(ForecastingQuestion.id == question_id)
    )
    question = result.scalar_one_or_none()
    if question is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question {question_id} not found",
        )
    return QuestionResponse.model_validate(question)


@router.put(
    "/{question_id}",
    response_model=QuestionResponse,
    summary="Update a forecasting question",
)
async def update_question(
    question_id: uuid.UUID,
    payload: QuestionUpdate,
    db: AsyncSession = Depends(get_db),
) -> QuestionResponse:
    result = await db.execute(
        select(ForecastingQuestion).where(ForecastingQuestion.id == question_id)
    )
    question = result.scalar_one_or_none()
    if question is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question {question_id} not found",
        )

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(question, field, value)

    await db.flush()
    await db.refresh(question)
    return QuestionResponse.model_validate(question)


@router.delete(
    "/{question_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a forecasting question",
)
async def delete_question(
    question_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(
        select(ForecastingQuestion).where(ForecastingQuestion.id == question_id)
    )
    question = result.scalar_one_or_none()
    if question is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question {question_id} not found",
        )
    await db.delete(question)
    await db.flush()
