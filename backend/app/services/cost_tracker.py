"""Cost tracking and budget management.

Provides a thread-safe accumulator that logs token usage, latency,
and estimated USD cost for every LLM call made during a forecast
pipeline run.  Supports session-level budgets and per-operation
breakdowns.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------

@dataclass
class CostEntry:
    """A single tracked LLM invocation with cost metadata."""

    entry_id: uuid.UUID
    timestamp: datetime
    operation_type: str          # e.g. "tier_a_forecast", "classification"
    model_tier: str              # "A" or "B"
    model_name: str              # e.g. "gpt-4o-mini"
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float
    latency_ms: float
    reference_id: uuid.UUID | None = None    # question or run id
    reference_type: str | None = None        # "question" | "forecast_run"


@dataclass
class CostSummary:
    """Aggregated cost statistics for a session or pipeline run."""

    total_cost_usd: float
    total_input_tokens: int
    total_output_tokens: int
    total_latency_ms: float
    entry_count: int
    by_operation: dict[str, float]
    by_tier: dict[str, float]
    by_model: dict[str, float]
    budget_usd: float | None
    remaining_budget_usd: float | None
    is_over_budget: bool


# ---------------------------------------------------------------------------
# Cost per 1K tokens (approximate, kept in sync with ModelRouter)
# ---------------------------------------------------------------------------

_MODEL_COSTS: dict[str, dict[str, float]] = {
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4o": {"input": 0.0025, "output": 0.01},
    "claude-sonnet-4-6": {"input": 0.003, "output": 0.015},
    "claude-haiku-4-5-20251001": {"input": 0.0008, "output": 0.004},
}


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class CostTracker:
    """Track costs across all LLM operations.  Thread-safe accumulator.

    Usage::

        tracker = CostTracker(session_budget=0.50)
        entry = tracker.log(
            operation_type="tier_a_forecast",
            model_tier="A",
            model_name="gpt-4o-mini",
            input_tokens=1200,
            output_tokens=400,
            latency_ms=320.0,
        )
        print(tracker.get_total())       # total USD so far
        print(tracker.is_over_budget())  # False
    """

    def __init__(self, session_budget: float | None = None) -> None:
        self.entries: list[CostEntry] = []
        self.session_budget: float | None = session_budget
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Core logging
    # ------------------------------------------------------------------

    def log(
        self,
        operation_type: str,
        model_tier: str,
        model_name: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: float,
        reference_id: uuid.UUID | None = None,
        reference_type: str | None = None,
    ) -> CostEntry:
        """Record a single LLM invocation.

        Parameters
        ----------
        operation_type:
            Descriptive label (e.g. ``"tier_a_forecast"``,
            ``"difficulty_classification"``).
        model_tier:
            ``"A"`` (cheap/fast) or ``"B"`` (strong reasoning).
        model_name:
            Exact model identifier used for the call.
        input_tokens:
            Number of input (prompt) tokens consumed.
        output_tokens:
            Number of output (completion) tokens consumed.
        latency_ms:
            Wall-clock latency of the call in milliseconds.
        reference_id:
            Optional UUID linking this cost to a question or run.
        reference_type:
            Optional label for *reference_id* (e.g. ``"question"``).

        Returns
        -------
        CostEntry
            The logged entry with computed cost.
        """
        cost = self._estimate_cost(model_name, input_tokens, output_tokens)

        entry = CostEntry(
            entry_id=uuid.uuid4(),
            timestamp=datetime.now(timezone.utc),
            operation_type=operation_type,
            model_tier=model_tier,
            model_name=model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=cost,
            latency_ms=latency_ms,
            reference_id=reference_id,
            reference_type=reference_type,
        )

        with self._lock:
            self.entries.append(entry)

        logger.debug(
            "Cost logged: %s  model=%s  tokens=%d+%d  $%.6f  %.0fms",
            operation_type,
            model_name,
            input_tokens,
            output_tokens,
            cost,
            latency_ms,
        )
        return entry

    # ------------------------------------------------------------------
    # Aggregation helpers
    # ------------------------------------------------------------------

    def get_total(self) -> float:
        """Return total estimated cost in USD accumulated so far."""
        with self._lock:
            return sum(e.estimated_cost_usd for e in self.entries)

    def get_by_operation(self) -> dict[str, float]:
        """Return cost breakdown keyed by ``operation_type``."""
        with self._lock:
            result: dict[str, float] = {}
            for e in self.entries:
                result[e.operation_type] = (
                    result.get(e.operation_type, 0.0) + e.estimated_cost_usd
                )
            return result

    def get_by_tier(self) -> dict[str, float]:
        """Return cost breakdown keyed by model tier (``"A"``/``"B"``)."""
        with self._lock:
            result: dict[str, float] = {}
            for e in self.entries:
                result[e.model_tier] = (
                    result.get(e.model_tier, 0.0) + e.estimated_cost_usd
                )
            return result

    def get_by_model(self) -> dict[str, float]:
        """Return cost breakdown keyed by model name."""
        with self._lock:
            result: dict[str, float] = {}
            for e in self.entries:
                result[e.model_name] = (
                    result.get(e.model_name, 0.0) + e.estimated_cost_usd
                )
            return result

    def get_remaining_budget(self) -> float | None:
        """Return remaining budget in USD, or ``None`` if no budget is set."""
        if self.session_budget is None:
            return None
        return max(0.0, self.session_budget - self.get_total())

    def is_over_budget(self) -> bool:
        """Return ``True`` if total cost exceeds the session budget."""
        if self.session_budget is None:
            return False
        return self.get_total() > self.session_budget

    # ------------------------------------------------------------------
    # Summary and export
    # ------------------------------------------------------------------

    def get_summary(self) -> CostSummary:
        """Produce an aggregated cost summary for the session.

        Returns
        -------
        CostSummary
        """
        with self._lock:
            total_cost = sum(e.estimated_cost_usd for e in self.entries)
            total_in = sum(e.input_tokens for e in self.entries)
            total_out = sum(e.output_tokens for e in self.entries)
            total_lat = sum(e.latency_ms for e in self.entries)

        remaining = None
        over = False
        if self.session_budget is not None:
            remaining = max(0.0, self.session_budget - total_cost)
            over = total_cost > self.session_budget

        return CostSummary(
            total_cost_usd=total_cost,
            total_input_tokens=total_in,
            total_output_tokens=total_out,
            total_latency_ms=total_lat,
            entry_count=len(self.entries),
            by_operation=self.get_by_operation(),
            by_tier=self.get_by_tier(),
            by_model=self.get_by_model(),
            budget_usd=self.session_budget,
            remaining_budget_usd=remaining,
            is_over_budget=over,
        )

    def to_db_records(self) -> list[dict[str, Any]]:
        """Serialise all entries as plain dicts suitable for DB insertion.

        Returns
        -------
        list[dict]
            Each dict maps column names to values.
        """
        with self._lock:
            records: list[dict[str, Any]] = []
            for e in self.entries:
                records.append({
                    "id": str(e.entry_id),
                    "timestamp": e.timestamp.isoformat(),
                    "operation_type": e.operation_type,
                    "model_tier": e.model_tier,
                    "model_name": e.model_name,
                    "input_tokens": e.input_tokens,
                    "output_tokens": e.output_tokens,
                    "estimated_cost_usd": e.estimated_cost_usd,
                    "latency_ms": e.latency_ms,
                    "reference_id": str(e.reference_id) if e.reference_id else None,
                    "reference_type": e.reference_type,
                })
            return records

    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Clear all recorded entries (budget is preserved)."""
        with self._lock:
            self.entries.clear()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _estimate_cost(
        model_name: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """Estimate USD cost for a single LLM call.

        Parameters
        ----------
        model_name:
            Model identifier (must be a key in ``_MODEL_COSTS``).
        input_tokens:
            Number of prompt tokens.
        output_tokens:
            Number of completion tokens.

        Returns
        -------
        float
            Estimated cost in USD.
        """
        costs = _MODEL_COSTS.get(model_name)
        if costs is None:
            logger.warning(
                "Unknown model '%s' for cost estimation; using gpt-4o-mini rates.",
                model_name,
            )
            costs = _MODEL_COSTS["gpt-4o-mini"]

        input_cost = (input_tokens / 1000.0) * costs["input"]
        output_cost = (output_tokens / 1000.0) * costs["output"]
        return input_cost + output_cost
