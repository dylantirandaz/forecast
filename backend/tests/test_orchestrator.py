"""Tests for the ForecastOrchestrator.

Validates difficulty estimation, domain classification, cheap-first
strategy, escalation logic, disagreement detection, and budget tracking.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from app.services.cost_tracker import CostTracker


pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def cost_tracker() -> CostTracker:
    return CostTracker(session_budget=1.00)


def _make_question(title: str, description: str = "", **kwargs) -> MagicMock:
    """Return a mock ForecastingQuestion with the given fields."""
    q = MagicMock()
    q.id = uuid.uuid4()
    q.title = title
    q.description = description or title
    q.target_type = kwargs.get("target_type", "binary")
    q.target_metric = kwargs.get("target_metric", "median_rent_stabilised")
    q.forecast_horizon_months = kwargs.get("forecast_horizon_months", 12)
    q.resolution_criteria = kwargs.get("resolution_criteria", "Resolves YES if ...")
    return q


# ---------------------------------------------------------------------------
# Difficulty estimation
# ---------------------------------------------------------------------------

class TestEstimateDifficulty:
    """ForecastOrchestrator.estimate_difficulty()"""

    async def test_estimate_difficulty_easy(self):
        """A short-horizon binary question on a well-tracked metric should
        be classified as easy."""
        from app.services.orchestrator import ForecastOrchestrator

        orchestrator = ForecastOrchestrator.__new__(ForecastOrchestrator)
        question = _make_question(
            title="Will median stabilised rent exceed $1,600 by end of 2026?",
            target_metric="median_rent_stabilised",
            forecast_horizon_months=6,
        )

        difficulty = orchestrator.estimate_difficulty(question)

        assert difficulty in ("easy", "medium", "hard")
        # Short horizon + well-known metric => easy
        assert difficulty == "easy"

    async def test_estimate_difficulty_hard(self):
        """A long-horizon question about a novel metric should be hard."""
        from app.services.orchestrator import ForecastOrchestrator

        orchestrator = ForecastOrchestrator.__new__(ForecastOrchestrator)
        question = _make_question(
            title="Will the ratio of affordable units to luxury completions "
            "drop below 0.3 across all five boroughs by 2030?",
            target_metric="affordable_luxury_ratio",
            forecast_horizon_months=48,
        )

        difficulty = orchestrator.estimate_difficulty(question)

        assert difficulty == "hard"


# ---------------------------------------------------------------------------
# Domain classification
# ---------------------------------------------------------------------------

class TestClassifyDomain:
    """ForecastOrchestrator.classify_domain()"""

    async def test_classify_domain_supply(self):
        """Questions about construction/units should classify as supply."""
        from app.services.orchestrator import ForecastOrchestrator

        orchestrator = ForecastOrchestrator.__new__(ForecastOrchestrator)
        question = _make_question(
            title="Will new housing construction starts exceed 30,000 units in 2027?",
            target_metric="construction_starts",
        )

        domain = orchestrator.classify_domain(question)

        assert domain == "supply"

    async def test_classify_domain_prices(self):
        """Questions about rent/price should classify as prices."""
        from app.services.orchestrator import ForecastOrchestrator

        orchestrator = ForecastOrchestrator.__new__(ForecastOrchestrator)
        question = _make_question(
            title="Will median stabilised rent exceed $1,600/month by 2027?",
            target_metric="median_rent_stabilised",
        )

        domain = orchestrator.classify_domain(question)

        assert domain == "prices"


# ---------------------------------------------------------------------------
# Cheap-first strategy
# ---------------------------------------------------------------------------

class TestCheapFirstStrategy:
    """The cheap-first orchestration should avoid escalation when Tier A
    returns high-confidence results."""

    async def test_cheap_first_strategy_no_escalation(self, cost_tracker):
        """When Tier A returns a high-confidence forecast, Tier B should
        not be invoked."""
        from app.services.orchestrator import ForecastOrchestrator

        orchestrator = ForecastOrchestrator.__new__(ForecastOrchestrator)
        orchestrator.cost_tracker = cost_tracker

        tier_a_result = {
            "probability": 0.85,
            "confidence": 0.90,
            "rationale": "Strong historical trend",
        }

        should_escalate = orchestrator.should_escalate(tier_a_result)

        assert should_escalate is False


# ---------------------------------------------------------------------------
# Escalation
# ---------------------------------------------------------------------------

class TestShouldEscalate:
    """Escalation logic for the cheap-first pipeline."""

    async def test_should_escalate_on_low_confidence(self):
        """A low-confidence Tier A result should trigger escalation."""
        from app.services.orchestrator import ForecastOrchestrator

        orchestrator = ForecastOrchestrator.__new__(ForecastOrchestrator)
        orchestrator.cost_tracker = CostTracker(session_budget=1.00)

        tier_a_result = {
            "probability": 0.50,
            "confidence": 0.30,
            "rationale": "Unclear signal",
        }

        should_escalate = orchestrator.should_escalate(tier_a_result)

        assert should_escalate is True


# ---------------------------------------------------------------------------
# Disagreement detection
# ---------------------------------------------------------------------------

class TestDisagreementDetection:
    """Detect when multiple model outputs disagree significantly."""

    async def test_disagreement_detection(self):
        """Forecasts from different sources that differ by >0.2 should
        be flagged as disagreeing."""
        from app.services.orchestrator import ForecastOrchestrator

        orchestrator = ForecastOrchestrator.__new__(ForecastOrchestrator)

        forecasts = [
            {"source": "tier_a", "probability": 0.80},
            {"source": "tier_b", "probability": 0.45},
            {"source": "base_rate", "probability": 0.60},
        ]

        has_disagreement = orchestrator.detect_disagreement(forecasts)

        assert has_disagreement is True


# ---------------------------------------------------------------------------
# Budget tracking
# ---------------------------------------------------------------------------

class TestBudgetTracking:
    """Budget guardrails in the orchestrator."""

    async def test_budget_tracking(self, cost_tracker):
        """The orchestrator should stop escalation when the budget is
        exhausted."""
        from app.services.orchestrator import ForecastOrchestrator

        orchestrator = ForecastOrchestrator.__new__(ForecastOrchestrator)
        orchestrator.cost_tracker = cost_tracker

        # Simulate spending most of the budget
        cost_tracker.log(
            operation_type="tier_a_forecast",
            model_tier="A",
            model_name="gpt-4o-mini",
            input_tokens=50_000,
            output_tokens=20_000,
            latency_ms=500.0,
        )
        cost_tracker.log(
            operation_type="tier_b_forecast",
            model_tier="B",
            model_name="gpt-4o",
            input_tokens=50_000,
            output_tokens=20_000,
            latency_ms=2000.0,
        )

        assert cost_tracker.is_over_budget() is True

        # Escalation should be blocked when over budget
        tier_a_result = {
            "probability": 0.50,
            "confidence": 0.30,
            "rationale": "Unclear signal",
        }

        should_escalate = orchestrator.should_escalate(tier_a_result)

        # Even though confidence is low, budget prevents escalation
        assert should_escalate is False
