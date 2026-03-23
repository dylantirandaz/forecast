"""Seed script for evaluation framework data.

Loads historical questions, evidence, and evaluation sets from JSON seed
files and inserts them into the database via SQLAlchemy async.

Usage:
    python -m app.core.seed_eval
    python -m app.core.seed_eval --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.models.evaluation import (
    EvaluationSet,
    HistoricalEvidence,
    HistoricalQuestion,
    QuestionDomain,
    QuestionType,
)

logger = logging.getLogger(__name__)

# Path to the seed data directory
_SEED_DIR = Path(__file__).resolve().parents[3] / "data" / "seeds"


# ── helpers ───────────────────────────────────────────────────────────


def _load_json(filename: str) -> list[dict[str, Any]]:
    """Load a JSON seed file from the seeds directory."""
    path = _SEED_DIR / filename
    if not path.exists():
        logger.warning("Seed file not found: %s", path)
        return []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    logger.info("Loaded %d records from %s", len(data), filename)
    return data


def _parse_datetime(value: str | None) -> datetime | None:
    """Parse an ISO datetime string, returning None on failure."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


# ── seeders ───────────────────────────────────────────────────────────


async def seed_historical_questions(
    session: AsyncSession, *, dry_run: bool = False
) -> list[HistoricalQuestion]:
    """Seed historical questions. Returns the list of created model instances."""
    records = _load_json("seed_historical_questions.json")
    if not records:
        return []

    # Idempotent: skip if data already exists
    result = await session.execute(select(HistoricalQuestion.id).limit(1))
    if result.scalar_one_or_none() is not None:
        logger.info("Historical questions table already has data, skipping.")
        # Return existing questions in order for evidence mapping
        result = await session.execute(
            select(HistoricalQuestion).order_by(HistoricalQuestion.created_at)
        )
        return list(result.scalars().all())

    questions: list[HistoricalQuestion] = []
    for rec in records:
        q = HistoricalQuestion(
            question_text=rec["question_text"],
            domain=QuestionDomain(rec["domain"]),
            question_type=QuestionType(rec["question_type"]),
            open_date=_parse_datetime(rec["open_date"]),
            close_date=_parse_datetime(rec["close_date"]),
            resolve_date=_parse_datetime(rec["resolve_date"]),
            resolution_criteria=rec["resolution_criteria"],
            resolved_value=rec["resolved_value"],
            forecast_cutoff_days=rec.get("forecast_cutoff_days", [90, 30, 7]),
            difficulty=rec.get("difficulty"),
            source_platform=rec.get("source_platform"),
            source_url=rec.get("source_url"),
        )
        if not dry_run:
            session.add(q)
        questions.append(q)

    if not dry_run:
        await session.flush()

    logger.info(
        "Seeded %d historical questions%s",
        len(questions),
        " (dry run)" if dry_run else "",
    )
    return questions


async def seed_historical_evidence(
    session: AsyncSession,
    questions: list[HistoricalQuestion],
    *,
    dry_run: bool = False,
) -> int:
    """Seed historical evidence items, mapping question_index to actual IDs."""
    records = _load_json("seed_historical_evidence.json")
    if not records:
        return 0

    # Idempotent: skip if data already exists
    result = await session.execute(select(HistoricalEvidence.id).limit(1))
    if result.scalar_one_or_none() is not None:
        logger.info("Historical evidence table already has data, skipping.")
        return 0

    if not questions:
        logger.warning("No questions available for evidence mapping, skipping.")
        return 0

    count = 0
    for rec in records:
        q_idx = rec["question_index"]
        if q_idx < 0 or q_idx >= len(questions):
            logger.warning(
                "Evidence item references invalid question_index %d, skipping.", q_idx
            )
            continue

        ev = HistoricalEvidence(
            question_id=questions[q_idx].id,
            published_at=_parse_datetime(rec["published_at"]),
            source=rec["source"],
            title=rec["title"],
            content=rec["content"],
            url=rec.get("url"),
            source_type=rec["source_type"],
            source_quality_score=rec.get("source_quality_score"),
        )
        if not dry_run:
            session.add(ev)
        count += 1

    if not dry_run:
        await session.flush()

    logger.info(
        "Seeded %d historical evidence items%s",
        count,
        " (dry run)" if dry_run else "",
    )
    return count


async def seed_evaluation_sets(
    session: AsyncSession,
    questions: list[HistoricalQuestion],
    *,
    dry_run: bool = False,
) -> int:
    """Seed evaluation sets, mapping question_indices to actual UUIDs."""
    records = _load_json("seed_evaluation_sets.json")
    if not records:
        return 0

    # Idempotent: skip if data already exists
    result = await session.execute(select(EvaluationSet.id).limit(1))
    if result.scalar_one_or_none() is not None:
        logger.info("Evaluation sets table already has data, skipping.")
        return 0

    if not questions:
        logger.warning("No questions available for evaluation set mapping, skipping.")
        return 0

    count = 0
    for rec in records:
        # Map question_indices to actual UUIDs
        q_indices = rec.get("question_indices", [])
        question_ids = []
        for idx in q_indices:
            if 0 <= idx < len(questions):
                question_ids.append(str(questions[idx].id))
            else:
                logger.warning(
                    "Eval set '%s' references invalid question_index %d",
                    rec["name"],
                    idx,
                )

        es = EvaluationSet(
            name=rec["name"],
            description=rec.get("description"),
            domains_included=rec.get("domains_included", []),
            difficulty_mix=rec.get("difficulty_mix", {}),
            num_questions=rec.get("num_questions", len(question_ids)),
            question_ids=question_ids,
        )
        if not dry_run:
            session.add(es)
        count += 1

    if not dry_run:
        await session.flush()

    logger.info(
        "Seeded %d evaluation sets%s",
        count,
        " (dry run)" if dry_run else "",
    )
    return count


# ── main runner ───────────────────────────────────────────────────────


async def run_eval_seeds(*, dry_run: bool = False) -> dict[str, int]:
    """Run all evaluation seed functions and return counts."""
    results: dict[str, int] = {}

    async with async_session_factory() as session:
        try:
            # 1. Seed questions first (others depend on them)
            questions = await seed_historical_questions(session, dry_run=dry_run)
            results["historical_questions"] = len(questions)

            # 2. Seed evidence (needs question IDs)
            ev_count = await seed_historical_evidence(
                session, questions, dry_run=dry_run
            )
            results["historical_evidence"] = ev_count

            # 3. Seed evaluation sets (needs question IDs)
            es_count = await seed_evaluation_sets(
                session, questions, dry_run=dry_run
            )
            results["evaluation_sets"] = es_count

            if not dry_run:
                await session.commit()
                logger.info("All evaluation seeds committed.")
            else:
                logger.info("Dry run complete. No data written.")

        except Exception:
            logger.exception("Error during evaluation seeding")
            if not dry_run:
                await session.rollback()
            raise

    return results


# ── CLI entry point ───────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed the evaluation framework database tables"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate seed data without writing to the database",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    results = asyncio.run(run_eval_seeds(dry_run=args.dry_run))

    print("\n=== Evaluation Seed Results ===")
    for name, count in results.items():
        status = "ERROR" if count < 0 else f"{count} records"
        print(f"  {name:25s} {status}")
    print()

    if any(c < 0 for c in results.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
