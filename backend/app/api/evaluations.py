"""Evaluation API endpoints for running and reviewing forecast evaluations."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.evaluation import (
    HistoricalQuestion, HistoricalEvidence, EvaluationSet,
    EvalRun, EvalPrediction, EvalRunStatus,
)
from app.schemas.evaluation import (
    HistoricalQuestionCreate, HistoricalQuestionResponse,
    EvaluationSetCreate, EvaluationSetResponse,
    EvalRunCreate, EvalRunResponse, EvalRunSummary,
    EvalPredictionResponse, EvalMetrics,
    EvalComparisonRequest, EvalComparisonResponse,
    CalibrationCurveData,
)

router = APIRouter()


@router.post("/run", status_code=201)
async def create_eval_run(
    payload: EvalRunCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create and optionally start an evaluation run.

    Accepts an evaluation set, model config, ablation flags,
    and cutoff days. Creates the run record and returns its ID.
    The actual evaluation can be triggered asynchronously.
    """
    run = EvalRun(
        id=uuid.uuid4(),
        name=payload.name,
        description=payload.description,
        evaluation_set_id=payload.evaluation_set_id,
        model_config=payload.model_config or {},
        ablation_flags=payload.ablation_flags or {},
        cutoff_days=payload.cutoff_days or [90, 30, 7],
        status=EvalRunStatus.pending,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    # If auto_start, kick off the evaluation
    if payload.auto_start:
        try:
            run.status = EvalRunStatus.running
            run.started_at = datetime.now(timezone.utc)
            await db.commit()

            # Load questions from evaluation set
            eval_set = None
            if run.evaluation_set_id:
                eval_set = await db.get(EvaluationSet, run.evaluation_set_id)

            if eval_set and eval_set.question_ids:
                q_ids = [uuid.UUID(qid) if isinstance(qid, str) else qid for qid in eval_set.question_ids]
                result = await db.execute(
                    select(HistoricalQuestion).where(HistoricalQuestion.id.in_(q_ids))
                )
                questions = result.scalars().all()
            else:
                result = await db.execute(select(HistoricalQuestion))
                questions = result.scalars().all()

            # Load evidence for each question
            evidence_by_q = {}
            for q in questions:
                ev_result = await db.execute(
                    select(HistoricalEvidence)
                    .where(HistoricalEvidence.question_id == q.id)
                    .order_by(HistoricalEvidence.published_at)
                )
                evidence_by_q[str(q.id)] = [
                    {
                        "published_at": ev.published_at.isoformat(),
                        "source": ev.source,
                        "title": ev.title,
                        "content": ev.content,
                        "source_type": ev.source_type,
                        "source_quality_score": ev.source_quality_score,
                    }
                    for ev in ev_result.scalars().all()
                ]

            # Run evaluation using replay engine
            from app.services.replay_engine import ReplayRunner, ReplayConfig

            replay_config = ReplayConfig(
                name=run.name,
                **{k: v for k, v in (run.ablation_flags or {}).items()
                   if k in ReplayConfig.__dataclass_fields__},
            )

            runner = ReplayRunner()
            q_dicts = [
                {
                    "id": str(q.id),
                    "question_text": q.question_text,
                    "domain": q.domain.value if hasattr(q.domain, 'value') else q.domain,
                    "question_type": q.question_type.value if hasattr(q.question_type, 'value') else q.question_type,
                    "open_date": q.open_date.isoformat(),
                    "resolve_date": q.resolve_date.isoformat(),
                    "resolved_value": q.resolved_value,
                    "difficulty": q.difficulty,
                }
                for q in questions
            ]

            # Map question index to evidence
            evidence_indexed = {}
            for idx, q in enumerate(q_dicts):
                evidence_indexed[idx] = evidence_by_q.get(q["id"], [])

            replay_result = runner.run_evaluation(
                questions=q_dicts,
                evidence_by_question=evidence_indexed,
                cutoff_days_list=run.cutoff_days,
                config=replay_config,
            )

            # Store predictions
            for pred in replay_result.predictions:
                eval_pred = EvalPrediction(
                    id=uuid.uuid4(),
                    eval_run_id=run.id,
                    question_id=uuid.UUID(pred.question_id),
                    cutoff_days=pred.cutoff_days,
                    cutoff_date=pred.cutoff_date,
                    predicted_probability=pred.predicted_probability,
                    actual_value=pred.actual_value,
                    brier_score=pred.brier_score,
                    log_score=pred.log_score,
                    evidence_count=pred.evidence_count,
                    base_rate_used=pred.base_rate_used,
                    model_tier_used=pred.model_tier_used,
                    cost_usd=pred.cost_usd,
                    latency_ms=pred.latency_ms,
                    rationale=pred.rationale,
                    pipeline_trace=pred.pipeline_trace,
                )
                db.add(eval_pred)

            # Update run with results
            run.mean_brier_score = replay_result.mean_brier_score
            run.mean_log_score = replay_result.mean_log_score
            run.calibration_error = replay_result.calibration_error
            run.sharpness = replay_result.sharpness
            run.total_questions = replay_result.total_questions
            run.total_cost_usd = replay_result.total_cost_usd
            run.total_latency_ms = replay_result.total_latency_ms
            run.results_by_domain = replay_result.by_domain
            run.results_by_horizon = replay_result.by_horizon
            run.results_by_difficulty = replay_result.by_difficulty
            run.status = EvalRunStatus.completed
            run.completed_at = datetime.now(timezone.utc)

            await db.commit()

        except Exception as e:
            run.status = EvalRunStatus.failed
            run.full_results = {"error": str(e)}
            await db.commit()
            raise HTTPException(status_code=500, detail=f"Evaluation failed: {e}")

    await db.refresh(run)
    return {
        "id": str(run.id),
        "name": run.name,
        "status": run.status.value if hasattr(run.status, 'value') else run.status,
        "mean_brier_score": run.mean_brier_score,
        "total_questions": run.total_questions,
    }


@router.get("/results")
async def list_eval_results(
    status: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List evaluation runs with summary metrics."""
    query = select(EvalRun).order_by(EvalRun.created_at.desc())
    if status:
        query = query.where(EvalRun.status == status)
    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    runs = result.scalars().all()

    count_result = await db.execute(select(func.count(EvalRun.id)))
    total = count_result.scalar()

    return {
        "total": total,
        "items": [
            {
                "id": str(r.id),
                "name": r.name,
                "status": r.status.value if hasattr(r.status, 'value') else r.status,
                "mean_brier_score": r.mean_brier_score,
                "mean_log_score": r.mean_log_score,
                "calibration_error": r.calibration_error,
                "sharpness": r.sharpness,
                "total_questions": r.total_questions,
                "total_cost_usd": r.total_cost_usd,
                "results_by_domain": r.results_by_domain,
                "results_by_horizon": r.results_by_horizon,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            }
            for r in runs
        ],
    }


@router.get("/{eval_id}")
async def get_eval_run(
    eval_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get detailed evaluation run results."""
    run = await db.get(EvalRun, eval_id)
    if not run:
        raise HTTPException(status_code=404, detail="Evaluation run not found")

    # Load predictions
    result = await db.execute(
        select(EvalPrediction)
        .where(EvalPrediction.eval_run_id == eval_id)
        .order_by(EvalPrediction.cutoff_days.desc(), EvalPrediction.brier_score)
    )
    predictions = result.scalars().all()

    return {
        "id": str(run.id),
        "name": run.name,
        "description": run.description,
        "status": run.status.value if hasattr(run.status, 'value') else run.status,
        "model_config": run.model_config,
        "ablation_flags": run.ablation_flags,
        "cutoff_days": run.cutoff_days,
        "mean_brier_score": run.mean_brier_score,
        "mean_log_score": run.mean_log_score,
        "calibration_error": run.calibration_error,
        "sharpness": run.sharpness,
        "total_questions": run.total_questions,
        "total_cost_usd": run.total_cost_usd,
        "total_latency_ms": run.total_latency_ms,
        "results_by_domain": run.results_by_domain,
        "results_by_horizon": run.results_by_horizon,
        "results_by_difficulty": run.results_by_difficulty,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "predictions": [
            {
                "id": str(p.id),
                "question_id": str(p.question_id),
                "cutoff_days": p.cutoff_days,
                "predicted_probability": p.predicted_probability,
                "actual_value": p.actual_value,
                "brier_score": p.brier_score,
                "log_score": p.log_score,
                "evidence_count": p.evidence_count,
                "base_rate_used": p.base_rate_used,
                "model_tier_used": p.model_tier_used,
                "cost_usd": p.cost_usd,
                "rationale": p.rationale,
            }
            for p in predictions
        ],
    }


@router.post("/ablation")
async def run_ablation_eval(
    configs: list[dict],
    evaluation_set_id: uuid.UUID = Query(...),
    cutoff_days: list[int] = Query([90, 30, 7]),
    db: AsyncSession = Depends(get_db),
):
    """Run multiple ablation configurations on the same evaluation set.

    Each config is a dict of ablation flags. Results are compared side-by-side.
    """
    results = []

    for i, config in enumerate(configs):
        config_name = config.pop("name", f"ablation_{i}")

        run = EvalRun(
            id=uuid.uuid4(),
            name=config_name,
            description=f"Ablation run: {config_name}",
            evaluation_set_id=evaluation_set_id,
            ablation_flags=config,
            cutoff_days=cutoff_days,
            status=EvalRunStatus.pending,
        )
        db.add(run)
        results.append({
            "id": str(run.id),
            "name": config_name,
            "config": config,
            "status": "pending",
        })

    await db.commit()
    return {"ablation_runs": results, "total": len(results)}


@router.get("/compare")
async def compare_eval_runs(
    run_ids: list[uuid.UUID] = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Compare multiple evaluation runs side-by-side."""
    runs = []
    for rid in run_ids:
        run = await db.get(EvalRun, rid)
        if not run:
            raise HTTPException(status_code=404, detail=f"Run {rid} not found")
        runs.append(run)

    if len(runs) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 runs to compare")

    # Find best run
    completed = [r for r in runs if r.mean_brier_score is not None]
    best = min(completed, key=lambda r: r.mean_brier_score) if completed else None

    comparisons = []
    for run in runs:
        delta_vs_best = None
        if best and run.mean_brier_score is not None and best.mean_brier_score is not None:
            delta_vs_best = round(run.mean_brier_score - best.mean_brier_score, 6)

        comparisons.append({
            "id": str(run.id),
            "name": run.name,
            "ablation_flags": run.ablation_flags,
            "mean_brier_score": run.mean_brier_score,
            "mean_log_score": run.mean_log_score,
            "calibration_error": run.calibration_error,
            "sharpness": run.sharpness,
            "total_cost_usd": run.total_cost_usd,
            "total_questions": run.total_questions,
            "delta_vs_best": delta_vs_best,
            "is_best": best and str(run.id) == str(best.id),
            "results_by_domain": run.results_by_domain,
            "results_by_horizon": run.results_by_horizon,
        })

    return {
        "runs": comparisons,
        "best_run_id": str(best.id) if best else None,
    }


@router.get("/calibration")
async def get_eval_calibration(
    eval_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Get calibration curve data for an evaluation run."""
    result = await db.execute(
        select(EvalPrediction)
        .where(EvalPrediction.eval_run_id == eval_id)
    )
    predictions = result.scalars().all()

    if not predictions:
        raise HTTPException(status_code=404, detail="No predictions found")

    from app.services.eval_metrics import EvalMetricsEngine
    import numpy as np

    engine = EvalMetricsEngine()
    probs = np.array([p.predicted_probability for p in predictions])
    actuals = np.array([p.actual_value for p in predictions])

    cal_curve = engine.compute_calibration_curve(probs, actuals)
    baseline = engine.compute_baseline_comparison(probs, actuals)
    hist = engine.compute_prediction_histogram(probs)

    return {
        "eval_id": str(eval_id),
        "calibration_curve": [
            {
                "bin_midpoint": b.bin_midpoint,
                "mean_predicted": b.mean_predicted,
                "mean_observed": b.mean_observed,
                "count": b.count,
                "ci_lower": b.confidence_interval_lower,
                "ci_upper": b.confidence_interval_upper,
            }
            for b in cal_curve if b.count > 0
        ],
        "baseline_comparison": {
            "model_brier": baseline.model_brier,
            "always_half_brier": baseline.always_half_brier,
            "base_rate_brier": baseline.base_rate_brier,
            "skill_score": baseline.skill_score,
        },
        "prediction_histogram": hist,
    }


# Historical questions CRUD
@router.post("/questions", status_code=201)
async def create_historical_question(
    payload: HistoricalQuestionCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a historical question for evaluation."""
    question = HistoricalQuestion(
        id=uuid.uuid4(),
        question_text=payload.question_text,
        domain=payload.domain,
        question_type=payload.question_type,
        open_date=payload.open_date,
        close_date=payload.close_date,
        resolve_date=payload.resolve_date,
        resolution_criteria=payload.resolution_criteria,
        resolved_value=payload.resolved_value,
        forecast_cutoff_days=payload.forecast_cutoff_days or [90, 30, 7],
        difficulty=payload.difficulty,
        source_platform=payload.source_platform,
    )
    db.add(question)
    await db.commit()
    await db.refresh(question)
    return {"id": str(question.id), "question_text": question.question_text}


@router.get("/questions")
async def list_historical_questions(
    domain: Optional[str] = None,
    difficulty: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """List historical questions with optional filters."""
    query = select(HistoricalQuestion).order_by(HistoricalQuestion.resolve_date.desc())
    if domain:
        query = query.where(HistoricalQuestion.domain == domain)
    if difficulty:
        query = query.where(HistoricalQuestion.difficulty == difficulty)
    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    questions = result.scalars().all()

    return {
        "items": [
            {
                "id": str(q.id),
                "question_text": q.question_text,
                "domain": q.domain.value if hasattr(q.domain, 'value') else q.domain,
                "question_type": q.question_type.value if hasattr(q.question_type, 'value') else q.question_type,
                "resolved_value": q.resolved_value,
                "resolve_date": q.resolve_date.isoformat(),
                "difficulty": q.difficulty,
            }
            for q in questions
        ],
    }


# Evaluation sets CRUD
@router.post("/sets", status_code=201)
async def create_evaluation_set(
    payload: EvaluationSetCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create an evaluation set."""
    eval_set = EvaluationSet(
        id=uuid.uuid4(),
        name=payload.name,
        description=payload.description,
        domains_included=payload.domains_included or [],
        difficulty_mix=payload.difficulty_mix or {},
        num_questions=len(payload.question_ids) if payload.question_ids else 0,
        question_ids=[str(qid) for qid in (payload.question_ids or [])],
    )
    db.add(eval_set)
    await db.commit()
    await db.refresh(eval_set)
    return {"id": str(eval_set.id), "name": eval_set.name, "num_questions": eval_set.num_questions}


@router.get("/sets")
async def list_evaluation_sets(
    db: AsyncSession = Depends(get_db),
):
    """List all evaluation sets."""
    result = await db.execute(select(EvaluationSet).order_by(EvaluationSet.created_at.desc()))
    sets = result.scalars().all()
    return {
        "items": [
            {
                "id": str(s.id),
                "name": s.name,
                "description": s.description,
                "num_questions": s.num_questions,
                "domains_included": s.domains_included,
            }
            for s in sets
        ],
    }
