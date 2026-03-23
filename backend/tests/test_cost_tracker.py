"""Tests for the CostTracker.

Validates logging, aggregation, budget checks, and summary generation.
"""

from __future__ import annotations

import uuid

import pytest

from app.services.cost_tracker import CostTracker


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tracker() -> CostTracker:
    """Return a fresh CostTracker with a $1.00 budget."""
    return CostTracker(session_budget=1.00)


@pytest.fixture()
def tracker_no_budget() -> CostTracker:
    """Return a CostTracker with no budget limit."""
    return CostTracker()


def _log_sample(tracker: CostTracker, **overrides) -> None:
    """Log a sample cost entry with sensible defaults."""
    kwargs = {
        "operation_type": "tier_a_forecast",
        "model_tier": "A",
        "model_name": "gpt-4o-mini",
        "input_tokens": 1000,
        "output_tokens": 500,
        "latency_ms": 300.0,
    }
    kwargs.update(overrides)
    tracker.log(**kwargs)


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

class TestLogCost:
    """CostTracker.log()"""

    def test_log_cost(self, tracker: CostTracker):
        """Logging a cost entry should add it to the entries list with
        a computed estimated_cost_usd."""
        entry = tracker.log(
            operation_type="tier_a_forecast",
            model_tier="A",
            model_name="gpt-4o-mini",
            input_tokens=1000,
            output_tokens=500,
            latency_ms=250.0,
        )

        assert len(tracker.entries) == 1
        assert entry.operation_type == "tier_a_forecast"
        assert entry.model_tier == "A"
        assert entry.model_name == "gpt-4o-mini"
        assert entry.input_tokens == 1000
        assert entry.output_tokens == 500
        assert entry.latency_ms == 250.0
        assert entry.estimated_cost_usd > 0.0
        assert entry.entry_id is not None
        assert entry.timestamp is not None

    def test_log_cost_with_reference(self, tracker: CostTracker):
        """Logging with a reference_id should store it on the entry."""
        ref_id = uuid.uuid4()
        entry = tracker.log(
            operation_type="classification",
            model_tier="A",
            model_name="gpt-4o-mini",
            input_tokens=500,
            output_tokens=100,
            latency_ms=150.0,
            reference_id=ref_id,
            reference_type="question",
        )

        assert entry.reference_id == ref_id
        assert entry.reference_type == "question"


# ---------------------------------------------------------------------------
# Totals
# ---------------------------------------------------------------------------

class TestGetTotal:
    """CostTracker.get_total()"""

    def test_get_total(self, tracker: CostTracker):
        """Total should equal the sum of estimated costs across all entries."""
        _log_sample(tracker, model_name="gpt-4o-mini", input_tokens=1000, output_tokens=500)
        _log_sample(tracker, model_name="gpt-4o-mini", input_tokens=2000, output_tokens=1000)

        total = tracker.get_total()

        # Manually compute expected: (1000/1000)*0.00015 + (500/1000)*0.0006
        #                           + (2000/1000)*0.00015 + (1000/1000)*0.0006
        expected = (
            (1000 / 1000) * 0.00015 + (500 / 1000) * 0.0006
            + (2000 / 1000) * 0.00015 + (1000 / 1000) * 0.0006
        )
        assert total == pytest.approx(expected)

    def test_get_total_empty(self, tracker: CostTracker):
        """Total for a tracker with no entries should be 0."""
        assert tracker.get_total() == 0.0


# ---------------------------------------------------------------------------
# By-operation breakdown
# ---------------------------------------------------------------------------

class TestGetByOperation:
    """CostTracker.get_by_operation()"""

    def test_get_by_operation(self, tracker: CostTracker):
        """Costs should be broken down by operation type."""
        _log_sample(tracker, operation_type="tier_a_forecast")
        _log_sample(tracker, operation_type="tier_a_forecast")
        _log_sample(tracker, operation_type="classification")

        by_op = tracker.get_by_operation()

        assert "tier_a_forecast" in by_op
        assert "classification" in by_op
        assert by_op["tier_a_forecast"] > by_op["classification"]


# ---------------------------------------------------------------------------
# By-tier breakdown
# ---------------------------------------------------------------------------

class TestGetByTier:
    """CostTracker.get_by_tier()"""

    def test_get_by_tier(self, tracker: CostTracker):
        """Costs should be broken down by model tier."""
        _log_sample(tracker, model_tier="A", model_name="gpt-4o-mini")
        _log_sample(tracker, model_tier="B", model_name="gpt-4o",
                     input_tokens=1000, output_tokens=500)

        by_tier = tracker.get_by_tier()

        assert "A" in by_tier
        assert "B" in by_tier
        # Tier B (gpt-4o) is more expensive per token
        assert by_tier["B"] > by_tier["A"]


# ---------------------------------------------------------------------------
# Budget checking
# ---------------------------------------------------------------------------

class TestBudgetCheck:
    """CostTracker.is_over_budget() and get_remaining_budget()"""

    def test_budget_check(self, tracker: CostTracker):
        """Tracker should report under-budget when spending is low."""
        _log_sample(tracker, input_tokens=100, output_tokens=50)

        assert tracker.is_over_budget() is False
        remaining = tracker.get_remaining_budget()
        assert remaining is not None
        assert remaining > 0.0
        assert remaining < 1.00

    def test_budget_check_over(self, tracker: CostTracker):
        """Tracker should report over-budget after heavy spending."""
        # gpt-4o at 50k input + 20k output = (50*0.0025) + (20*0.01) = 0.325
        # Do it 4 times => 1.30 > 1.00 budget
        for _ in range(4):
            tracker.log(
                operation_type="tier_b_forecast",
                model_tier="B",
                model_name="gpt-4o",
                input_tokens=50_000,
                output_tokens=20_000,
                latency_ms=2000.0,
            )

        assert tracker.is_over_budget() is True
        assert tracker.get_remaining_budget() == 0.0

    def test_budget_check_no_budget(self, tracker_no_budget: CostTracker):
        """A tracker with no budget should never be over-budget."""
        _log_sample(tracker_no_budget, input_tokens=100_000, output_tokens=50_000)

        assert tracker_no_budget.is_over_budget() is False
        assert tracker_no_budget.get_remaining_budget() is None


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

class TestCostSummary:
    """CostTracker.get_summary()"""

    def test_cost_summary(self, tracker: CostTracker):
        """Summary should aggregate all dimensions correctly."""
        tracker.log(
            operation_type="tier_a_forecast",
            model_tier="A",
            model_name="gpt-4o-mini",
            input_tokens=1000,
            output_tokens=500,
            latency_ms=300.0,
        )
        tracker.log(
            operation_type="tier_b_forecast",
            model_tier="B",
            model_name="gpt-4o",
            input_tokens=2000,
            output_tokens=800,
            latency_ms=1500.0,
        )

        summary = tracker.get_summary()

        assert summary.entry_count == 2
        assert summary.total_cost_usd > 0.0
        assert summary.total_input_tokens == 3000
        assert summary.total_output_tokens == 1300
        assert summary.total_latency_ms == pytest.approx(1800.0)
        assert "tier_a_forecast" in summary.by_operation
        assert "tier_b_forecast" in summary.by_operation
        assert "A" in summary.by_tier
        assert "B" in summary.by_tier
        assert "gpt-4o-mini" in summary.by_model
        assert "gpt-4o" in summary.by_model
        assert summary.budget_usd == 1.00
        assert summary.remaining_budget_usd is not None
        assert summary.is_over_budget is False

    def test_cost_summary_empty(self, tracker: CostTracker):
        """Summary for an empty tracker should have zeroed-out fields."""
        summary = tracker.get_summary()

        assert summary.entry_count == 0
        assert summary.total_cost_usd == 0.0
        assert summary.total_input_tokens == 0
        assert summary.total_output_tokens == 0
        assert summary.by_operation == {}
        assert summary.by_tier == {}
        assert summary.by_model == {}
