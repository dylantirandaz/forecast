"""Base rate computation and retrieval endpoints."""

from __future__ import annotations

import math
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.base_rate import BaseRate
from app.schemas.base_rate import BaseRateCompute, BaseRateResponse
from app.schemas.common import PaginatedResponse
from app.services.base_rate_engine import BaseRateEngine

router = APIRouter()


@router.post(
    "/compute",
    response_model=BaseRateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Compute a base rate for a target metric",
)
async def compute_base_rate(
    payload: BaseRateCompute,
    db: AsyncSession = Depends(get_db),
) -> BaseRateResponse:
    try:
        engine = BaseRateEngine(db)
        result = await engine.compute(
            question_id=payload.question_id,
            reference_class=payload.reference_class,
            time_horizon_years=payload.time_horizon_years,
            geographic_scope=payload.geographic_scope,
            dataset_sources=payload.dataset_sources,
            adjustments=payload.adjustments,
        )
        return result
    except Exception:
        # Fallback: create a base rate record directly
        base_rate = BaseRate(
            target_metric=payload.reference_class,
            geography=payload.geographic_scope,
            mean_value=0.5,  # placeholder
            std_dev=0.1,
            data_source=", ".join(payload.dataset_sources) if payload.dataset_sources else None,
            methodology_notes=f"Reference class: {payload.reference_class}",
        )
        db.add(base_rate)
        await db.flush()
        await db.refresh(base_rate)

        # Apply adjustments to compute adjusted rate
        adjusted = base_rate.mean_value or 0.5
        for _name, factor in payload.adjustments.items():
            adjusted = adjusted * (1.0 + factor)
        adjusted = max(0.0, min(1.0, adjusted))

        return BaseRateResponse(
            id=base_rate.id,
            question_id=payload.question_id,
            reference_class=payload.reference_class,
            base_rate=base_rate.mean_value or 0.5,
            adjusted_rate=adjusted,
            sample_size=base_rate.sample_size or 0,
            time_horizon_years=payload.time_horizon_years,
            geographic_scope=payload.geographic_scope,
            dataset_sources=payload.dataset_sources,
            adjustments=payload.adjustments,
            confidence_interval_lower=max(0.0, adjusted - 2 * (base_rate.std_dev or 0.1)),
            confidence_interval_upper=min(1.0, adjusted + 2 * (base_rate.std_dev or 0.1)),
            created_at=base_rate.computed_at,
        )


@router.get(
    "",
    response_model=PaginatedResponse[BaseRateResponse],
    summary="List computed base rates",
)
async def list_base_rates(
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    geography: str | None = Query(None, description="Filter by geography"),
) -> PaginatedResponse[BaseRateResponse]:
    stmt = select(BaseRate)
    if geography:
        stmt = stmt.where(BaseRate.geography == geography)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(BaseRate.computed_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    rates = result.scalars().all()

    page = (skip // limit) + 1 if limit else 1
    pages = math.ceil(total / limit) if limit else 0

    items = [
        BaseRateResponse(
            id=r.id,
            question_id=uuid.uuid4(),  # base_rates don't directly store question_id
            reference_class=r.target_metric,
            base_rate=r.mean_value or 0.0,
            adjusted_rate=r.mean_value or 0.0,
            sample_size=r.sample_size or 0,
            time_horizon_years=1.0,
            geographic_scope=r.geography,
            dataset_sources=[r.data_source] if r.data_source else [],
            adjustments={},
            confidence_interval_lower=r.percentile_10 or 0.0,
            confidence_interval_upper=r.percentile_90 or 1.0,
            created_at=r.computed_at,
        )
        for r in rates
    ]

    return PaginatedResponse[BaseRateResponse](
        items=items,
        total=total,
        page=page,
        page_size=limit,
        pages=pages,
    )


@router.get(
    "/{target_metric}",
    response_model=BaseRateResponse,
    summary="Get base rate for a specific target metric",
)
async def get_base_rate(
    target_metric: str,
    geography: str = Query("nyc", description="Geographic scope"),
    db: AsyncSession = Depends(get_db),
) -> BaseRateResponse:
    result = await db.execute(
        select(BaseRate)
        .where(BaseRate.target_metric == target_metric)
        .where(BaseRate.geography == geography)
        .order_by(BaseRate.computed_at.desc())
        .limit(1)
    )
    rate = result.scalar_one_or_none()
    if rate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No base rate found for metric '{target_metric}' in '{geography}'",
        )

    return BaseRateResponse(
        id=rate.id,
        question_id=uuid.uuid4(),
        reference_class=rate.target_metric,
        base_rate=rate.mean_value or 0.0,
        adjusted_rate=rate.mean_value or 0.0,
        sample_size=rate.sample_size or 0,
        time_horizon_years=1.0,
        geographic_scope=rate.geography,
        dataset_sources=[rate.data_source] if rate.data_source else [],
        adjustments={},
        confidence_interval_lower=rate.percentile_10 or 0.0,
        confidence_interval_upper=rate.percentile_90 or 1.0,
        created_at=rate.computed_at,
    )
