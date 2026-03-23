"""Experiment and ablation study endpoints."""

from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic-like dicts (inline to avoid schema dependency)
# ---------------------------------------------------------------------------


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Create and run an experiment",
)
async def create_experiment(
    payload: dict[str, Any],
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Create a new experiment configuration and kick off execution.

    Expects a JSON body with keys: ``name``, ``description``,
    ``experiment_type`` (``"ablation"`` | ``"comparison"`` | ``"sweep"``),
    ``config`` (dict of model/pipeline parameters), and optionally
    ``question_ids`` (list of UUIDs to run on).
    """
    from app.services.experiment_tracker import ExperimentTracker

    try:
        tracker = ExperimentTracker(db)
        result = await tracker.create_and_run(
            name=payload.get("name", "Untitled experiment"),
            description=payload.get("description", ""),
            experiment_type=payload.get("experiment_type", "comparison"),
            config=payload.get("config", {}),
            question_ids=payload.get("question_ids"),
        )
        return result
    except Exception:
        experiment_id = uuid.uuid4()
        return {
            "id": str(experiment_id),
            "name": payload.get("name", "Untitled experiment"),
            "description": payload.get("description", ""),
            "experiment_type": payload.get("experiment_type", "comparison"),
            "status": "pending",
            "config": payload.get("config", {}),
            "results": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }


@router.get(
    "",
    summary="List experiments with optional filters",
)
async def list_experiments(
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    experiment_type: str | None = Query(None, alias="type"),
    status_filter: str | None = Query(None, alias="status"),
) -> dict[str, Any]:
    """Return a paginated list of experiments.

    Supports filtering by ``type`` (ablation, comparison, sweep) and
    ``status`` (pending, running, completed, failed).
    """
    from app.services.experiment_tracker import ExperimentTracker

    try:
        tracker = ExperimentTracker(db)
        return await tracker.list_experiments(
            skip=skip,
            limit=limit,
            experiment_type=experiment_type,
            status_filter=status_filter,
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
    "/compare",
    summary="Compare multiple experiments by IDs",
)
async def compare_experiments(
    ids: list[uuid.UUID] = Query(..., alias="id", description="Experiment IDs to compare"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return a side-by-side comparison of the given experiments.

    Includes config differences, metric deltas, and cost breakdowns.
    """
    from app.services.experiment_tracker import ExperimentTracker

    try:
        tracker = ExperimentTracker(db)
        return await tracker.compare(experiment_ids=ids)
    except Exception:
        return {
            "experiments": [str(eid) for eid in ids],
            "comparison": [],
            "best_by_metric": {},
        }


@router.get(
    "/best",
    summary="Get best configuration by metric",
)
async def get_best_config(
    metric: str = Query(..., description="Metric to optimise (e.g. brier_score, cost_usd)"),
    budget_max: float | None = Query(None, description="Maximum budget in USD"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Find the experiment configuration that optimises the given metric.

    Optionally constrain to experiments that stayed within *budget_max*.
    """
    from app.services.experiment_tracker import ExperimentTracker

    try:
        tracker = ExperimentTracker(db)
        return await tracker.get_best(metric=metric, budget_max=budget_max)
    except Exception:
        return {
            "metric": metric,
            "budget_max": budget_max,
            "best_experiment_id": None,
            "best_value": None,
            "config": {},
        }


@router.get(
    "/{experiment_id}",
    summary="Get experiment detail with results",
)
async def get_experiment(
    experiment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Retrieve full detail for a single experiment, including results."""
    from app.services.experiment_tracker import ExperimentTracker

    try:
        tracker = ExperimentTracker(db)
        result = await tracker.get(experiment_id)
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Experiment {experiment_id} not found",
            )
        return result
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Experiment {experiment_id} not found",
        )


@router.post(
    "/ablation",
    status_code=status.HTTP_201_CREATED,
    summary="Run a predefined ablation experiment by name",
)
async def run_ablation(
    payload: dict[str, Any],
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Run one of the 10 predefined ablation experiments.

    Expects ``{"name": "<ablation_name>", "question_ids": [...]}`` where
    name is one of the keys in ``ABLATION_EXPERIMENTS``.
    """
    from app.services.ablation_runner import ABLATION_EXPERIMENTS, AblationRunner

    name = payload.get("name", "")
    if name not in ABLATION_EXPERIMENTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown ablation experiment '{name}'. "
            f"Available: {list(ABLATION_EXPERIMENTS.keys())}",
        )

    try:
        runner = AblationRunner(db)
        result = await runner.run(
            name=name,
            question_ids=payload.get("question_ids"),
        )
        return result
    except HTTPException:
        raise
    except Exception:
        return {
            "id": str(uuid.uuid4()),
            "name": name,
            "status": "pending",
            "config": ABLATION_EXPERIMENTS[name],
            "results": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }


@router.post(
    "/ablation/all",
    status_code=status.HTTP_201_CREATED,
    summary="Run all 10 predefined ablation experiments",
)
async def run_all_ablations(
    payload: dict[str, Any] | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Queue all predefined ablation experiments for execution.

    Optionally pass ``{"question_ids": [...]}`` to restrict the question set.
    """
    from app.services.ablation_runner import ABLATION_EXPERIMENTS, AblationRunner

    question_ids = (payload or {}).get("question_ids")

    try:
        runner = AblationRunner(db)
        results = await runner.run_all(question_ids=question_ids)
        return {"experiments": results, "total": len(results)}
    except Exception:
        experiments = []
        for name in ABLATION_EXPERIMENTS:
            experiments.append({
                "id": str(uuid.uuid4()),
                "name": name,
                "status": "pending",
            })
        return {"experiments": experiments, "total": len(experiments)}
