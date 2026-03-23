"""Seed script that loads JSON seed files and inserts records into the database.

Usage:
    python -m app.core.seed          # seed all tables
    python -m app.core.seed --only questions scenarios
    python -m app.core.seed --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.models import (
    BaseRate,
    EvidenceItem,
    ForecastingQuestion,
    PolicyEvent,
    PolicyEventType,
    Scenario,
    ScenarioIntensity,
    SourceType,
    TargetType,
)

logger = logging.getLogger(__name__)

# Path to the seed data directory
_SEED_DIR = Path(__file__).resolve().parents[3] / "data" / "seeds"


# ── helpers ───────────────────────────────────────────────────────────


def _parse_date(value: str | None) -> date | None:
    """Parse an ISO date string, returning None on failure."""
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        return None


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


# ── seeders ───────────────────────────────────────────────────────────


async def seed_questions(session: AsyncSession, *, dry_run: bool = False) -> int:
    """Seed forecasting questions."""
    records = _load_json("seed_questions.json")
    if not records:
        return 0

    # Skip if table already has data
    result = await session.execute(select(ForecastingQuestion.id).limit(1))
    if result.scalar_one_or_none() is not None:
        logger.info("Questions table already has data, skipping.")
        return 0

    count = 0
    for rec in records:
        q = ForecastingQuestion(
            title=rec["title"],
            description=rec.get("description"),
            target_type=TargetType(rec["target_type"]),
            target_metric=rec.get("target_metric"),
            unit_of_analysis=rec.get("unit_of_analysis"),
            forecast_horizon_months=rec.get("forecast_horizon_months"),
            resolution_criteria=rec.get("resolution_criteria"),
        )
        if not dry_run:
            session.add(q)
        count += 1

    if not dry_run:
        await session.flush()
    logger.info("Seeded %d questions%s", count, " (dry run)" if dry_run else "")
    return count


async def seed_scenarios(session: AsyncSession, *, dry_run: bool = False) -> int:
    """Seed policy scenarios."""
    records = _load_json("seed_scenarios.json")
    if not records:
        return 0

    result = await session.execute(select(Scenario.id).limit(1))
    if result.scalar_one_or_none() is not None:
        logger.info("Scenarios table already has data, skipping.")
        return 0

    count = 0
    for rec in records:
        timing = rec.get("timing", {})
        s = Scenario(
            name=rec["name"],
            narrative=rec.get("narrative"),
            assumptions=rec.get("assumptions"),
            policy_levers=rec.get("policy_levers"),
            timing_start=_parse_date(timing.get("start_date")),
            timing_end=_parse_date(timing.get("end_date")),
            intensity=(
                ScenarioIntensity(rec["intensity"])
                if rec.get("intensity")
                else None
            ),
            expected_channels=rec.get("expected_channels"),
        )
        if not dry_run:
            session.add(s)
        count += 1

    if not dry_run:
        await session.flush()
    logger.info("Seeded %d scenarios%s", count, " (dry run)" if dry_run else "")
    return count


async def seed_base_rates(session: AsyncSession, *, dry_run: bool = False) -> int:
    """Seed historical base rates."""
    records = _load_json("seed_base_rates.json")
    if not records:
        return 0

    result = await session.execute(select(BaseRate.id).limit(1))
    if result.scalar_one_or_none() is not None:
        logger.info("Base rates table already has data, skipping.")
        return 0

    count = 0
    for rec in records:
        br = BaseRate(
            target_metric=rec["target_metric"],
            geography=rec.get("geography", "nyc"),
            period_start=_parse_date(rec.get("period_start")),
            period_end=_parse_date(rec.get("period_end")),
            mean_value=rec.get("mean_value"),
            median_value=rec.get("median_value"),
            std_dev=rec.get("std_dev"),
            percentile_10=rec.get("percentile_10"),
            percentile_90=rec.get("percentile_90"),
            sample_size=rec.get("sample_size"),
            data_source=rec.get("data_source"),
            methodology_notes=rec.get("methodology_notes"),
        )
        if not dry_run:
            session.add(br)
        count += 1

    if not dry_run:
        await session.flush()
    logger.info("Seeded %d base rates%s", count, " (dry run)" if dry_run else "")
    return count


async def seed_evidence(session: AsyncSession, *, dry_run: bool = False) -> int:
    """Seed evidence items."""
    records = _load_json("seed_evidence.json")
    if not records:
        return 0

    result = await session.execute(select(EvidenceItem.id).limit(1))
    if result.scalar_one_or_none() is not None:
        logger.info("Evidence items table already has data, skipping.")
        return 0

    count = 0
    for rec in records:
        ei = EvidenceItem(
            title=rec["title"],
            source_url=rec.get("source_url"),
            source_name=rec.get("source_name"),
            source_type=SourceType(rec["source_type"]),
            content_summary=rec.get("content_summary"),
            published_date=_parse_date(rec.get("published_date")),
        )
        if not dry_run:
            session.add(ei)
        count += 1

    if not dry_run:
        await session.flush()
    logger.info("Seeded %d evidence items%s", count, " (dry run)" if dry_run else "")
    return count


async def seed_policy_events(session: AsyncSession, *, dry_run: bool = False) -> int:
    """Seed policy events."""
    records = _load_json("seed_policy_events.json")
    if not records:
        return 0

    result = await session.execute(select(PolicyEvent.id).limit(1))
    if result.scalar_one_or_none() is not None:
        logger.info("Policy events table already has data, skipping.")
        return 0

    count = 0
    for rec in records:
        pe = PolicyEvent(
            name=rec["name"],
            description=rec.get("description"),
            event_type=PolicyEventType(rec["event_type"]),
            effective_date=_parse_date(rec.get("effective_date")),
            announced_date=_parse_date(rec.get("announced_date")),
            jurisdiction=rec.get("jurisdiction"),
            affected_targets=rec.get("affected_targets"),
            source_url=rec.get("source_url"),
        )
        if not dry_run:
            session.add(pe)
        count += 1

    if not dry_run:
        await session.flush()
    logger.info(
        "Seeded %d policy events%s", count, " (dry run)" if dry_run else ""
    )
    return count


# ── registry ──────────────────────────────────────────────────────────

SEEDERS = {
    "questions": seed_questions,
    "scenarios": seed_scenarios,
    "base_rates": seed_base_rates,
    "evidence": seed_evidence,
    "policy_events": seed_policy_events,
}


async def run_all_seeds(
    *,
    only: list[str] | None = None,
    dry_run: bool = False,
) -> dict[str, int]:
    """Run seed functions and return counts of inserted records.

    Parameters
    ----------
    only : list[str], optional
        If provided, only run the named seeders.
    dry_run : bool
        If True, load and validate data but do not write to the database.
    """
    targets = only or list(SEEDERS.keys())
    results: dict[str, int] = {}

    async with async_session_factory() as session:
        for name in targets:
            seeder = SEEDERS.get(name)
            if seeder is None:
                logger.warning("Unknown seeder: %s", name)
                continue
            try:
                count = await seeder(session, dry_run=dry_run)
                results[name] = count
            except Exception:
                logger.exception("Error seeding %s", name)
                results[name] = -1

        if not dry_run:
            await session.commit()
            logger.info("All seeds committed.")
        else:
            logger.info("Dry run complete. No data written.")

    return results


# ── CLI entry point ───────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the NYC Housing Forecasting database")
    parser.add_argument(
        "--only",
        nargs="+",
        choices=list(SEEDERS.keys()),
        help="Seed only the specified tables",
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

    results = asyncio.run(run_all_seeds(only=args.only, dry_run=args.dry_run))

    print("\n=== Seed Results ===")
    for name, count in results.items():
        status = "ERROR" if count < 0 else f"{count} records"
        print(f"  {name:20s} {status}")
    print()

    if any(c < 0 for c in results.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
