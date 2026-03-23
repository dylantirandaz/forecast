"""Evidence ingestion and scoring endpoints."""

from __future__ import annotations

import math
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.evidence import EvidenceItem, EvidenceScore
from app.models.question import ForecastingQuestion
from app.schemas.evidence import (
    EvidenceCreate,
    EvidenceResponse,
    EvidenceScoreCreate,
    EvidenceScoreResponse,
)
from app.schemas.common import PaginatedResponse

router = APIRouter()


@router.post(
    "",
    response_model=EvidenceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a new piece of evidence",
)
async def create_evidence(
    payload: EvidenceCreate,
    db: AsyncSession = Depends(get_db),
) -> EvidenceResponse:
    # Verify parent question exists
    q_result = await db.execute(
        select(ForecastingQuestion).where(ForecastingQuestion.id == payload.question_id)
    )
    if q_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question {payload.question_id} not found",
        )

    evidence = EvidenceItem(
        title=payload.title,
        content_summary=payload.summary,
        source_type=payload.source_type,
        source_url=str(payload.source_url) if payload.source_url else None,
        published_date=payload.publication_date.date() if payload.publication_date else None,
    )
    db.add(evidence)
    await db.flush()
    await db.refresh(evidence)

    return EvidenceResponse(
        id=evidence.id,
        question_id=payload.question_id,
        title=evidence.title,
        summary=evidence.content_summary or "",
        source_type=payload.source_type,
        source_url=evidence.source_url,
        publication_date=payload.publication_date,
        directional_effect=payload.directional_effect,
        tags=payload.tags,
        created_at=evidence.ingested_at,
        updated_at=evidence.ingested_at,
    )


@router.get(
    "",
    response_model=PaginatedResponse[EvidenceResponse],
    summary="List evidence items with filters",
)
async def list_evidence(
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    question_id: uuid.UUID | None = Query(None, description="Filter by question"),
    source_type: str | None = Query(None, description="Filter by source type"),
    search: str | None = Query(None, description="Search in title and summary"),
) -> PaginatedResponse[EvidenceResponse]:
    stmt = select(EvidenceItem)

    if source_type is not None:
        stmt = stmt.where(EvidenceItem.source_type == source_type)
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(
            EvidenceItem.title.ilike(pattern)
            | EvidenceItem.content_summary.ilike(pattern)
        )
    if question_id is not None:
        # Filter via evidence_scores join
        stmt = stmt.join(
            EvidenceScore, EvidenceScore.evidence_item_id == EvidenceItem.id
        ).where(EvidenceScore.question_id == question_id)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(EvidenceItem.ingested_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    items = result.scalars().all()

    page = (skip // limit) + 1 if limit else 1
    pages = math.ceil(total / limit) if limit else 0

    responses = []
    for item in items:
        responses.append(
            EvidenceResponse(
                id=item.id,
                question_id=question_id or uuid.uuid4(),  # placeholder if no filter
                title=item.title,
                summary=item.content_summary or "",
                source_type=item.source_type,
                source_url=item.source_url,
                publication_date=None,
                directional_effect="neutral",
                tags=[],
                created_at=item.ingested_at,
                updated_at=item.ingested_at,
            )
        )

    return PaginatedResponse[EvidenceResponse](
        items=responses,
        total=total,
        page=page,
        page_size=limit,
        pages=pages,
    )


@router.get(
    "/{evidence_id}",
    response_model=EvidenceResponse,
    summary="Get evidence detail with scores",
)
async def get_evidence(
    evidence_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> EvidenceResponse:
    result = await db.execute(
        select(EvidenceItem)
        .options(selectinload(EvidenceItem.scores))
        .where(EvidenceItem.id == evidence_id)
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evidence item {evidence_id} not found",
        )

    # Determine question_id from first score if available
    q_id = item.scores[0].question_id if item.scores else uuid.uuid4()

    return EvidenceResponse(
        id=item.id,
        question_id=q_id,
        title=item.title,
        summary=item.content_summary or "",
        source_type=item.source_type,
        source_url=item.source_url,
        publication_date=None,
        directional_effect="neutral",
        tags=[],
        created_at=item.ingested_at,
        updated_at=item.ingested_at,
    )


@router.post(
    "/{evidence_id}/score",
    response_model=EvidenceScoreResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Score a piece of evidence for a question",
)
async def score_evidence(
    evidence_id: uuid.UUID,
    payload: EvidenceScoreCreate,
    db: AsyncSession = Depends(get_db),
) -> EvidenceScoreResponse:
    # Verify evidence exists
    ev_result = await db.execute(
        select(EvidenceItem).where(EvidenceItem.id == evidence_id)
    )
    if ev_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evidence item {evidence_id} not found",
        )

    score = EvidenceScore(
        evidence_item_id=evidence_id,
        question_id=payload.evidence_id,  # Schema reuse: question_id carried via evidence_id field
        source_credibility=payload.credibility,
        domain_relevance=payload.relevance,
        composite_weight=payload.weight,
    )
    db.add(score)
    await db.flush()
    await db.refresh(score)

    return EvidenceScoreResponse(
        id=score.id,
        evidence_id=evidence_id,
        relevance=score.domain_relevance or 0.0,
        credibility=score.source_credibility or 0.0,
        weight=score.composite_weight or 0.0,
        rationale=payload.rationale,
        created_at=score.scored_at,
    )
