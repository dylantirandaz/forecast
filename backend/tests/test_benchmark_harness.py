"""Tests for the BenchmarkHarness.

Validates scoring functions, export formatters, and config comparison.
"""

from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone

import pytest

from app.services.benchmark_harness import BenchmarkHarness


pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_forecast(probability: float, outcome: float, question_id: str | None = None) -> dict:
    """Return a minimal forecast dict for testing."""
    return {
        "question_id": question_id or str(uuid.uuid4()),
        "probability": probability,
        "outcome": outcome,
    }


# ---------------------------------------------------------------------------
# Binary evaluation
# ---------------------------------------------------------------------------

class TestEvaluateBinary:
    """BenchmarkHarness.evaluate_binary()"""

    async def test_evaluate_binary_perfect(self):
        """Perfect forecasts (1.0 for YES, 0.0 for NO) should yield
        a Brier score of 0.0."""
        harness = BenchmarkHarness.__new__(BenchmarkHarness)

        forecasts = [
            _make_forecast(1.0, 1.0),
            _make_forecast(0.0, 0.0),
            _make_forecast(1.0, 1.0),
            _make_forecast(0.0, 0.0),
        ]

        result = harness.evaluate_binary(forecasts)

        assert result["brier_score"] == pytest.approx(0.0)
        assert result["count"] == 4

    async def test_evaluate_binary_random(self):
        """Uniform 0.5 forecasts should yield a Brier score of 0.25."""
        harness = BenchmarkHarness.__new__(BenchmarkHarness)

        forecasts = [
            _make_forecast(0.5, 1.0),
            _make_forecast(0.5, 0.0),
            _make_forecast(0.5, 1.0),
            _make_forecast(0.5, 0.0),
        ]

        result = harness.evaluate_binary(forecasts)

        assert result["brier_score"] == pytest.approx(0.25)
        assert result["count"] == 4


# ---------------------------------------------------------------------------
# CRPS
# ---------------------------------------------------------------------------

class TestComputeCRPS:
    """Continuous Ranked Probability Score."""

    async def test_compute_crps(self):
        """CRPS for a point forecast equal to the actual value should be 0."""
        harness = BenchmarkHarness.__new__(BenchmarkHarness)

        # When the predicted distribution is a point mass at the true value,
        # CRPS should be zero.
        crps = harness.compute_crps(
            predicted_cdf=[(1500.0, 0.0), (1600.0, 1.0)],
            actual_value=1600.0,
        )

        assert crps == pytest.approx(0.0, abs=0.01)


# ---------------------------------------------------------------------------
# Coverage
# ---------------------------------------------------------------------------

class TestComputeCoverage:
    """Prediction interval coverage."""

    async def test_compute_coverage(self):
        """Coverage should equal the fraction of actuals inside the interval."""
        harness = BenchmarkHarness.__new__(BenchmarkHarness)

        intervals = [
            {"lower": 1400, "upper": 1700, "actual": 1500},  # inside
            {"lower": 1400, "upper": 1700, "actual": 1600},  # inside
            {"lower": 1400, "upper": 1700, "actual": 1800},  # outside
            {"lower": 1400, "upper": 1700, "actual": 1300},  # outside
        ]

        coverage = harness.compute_coverage(intervals)

        assert coverage == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Export formats
# ---------------------------------------------------------------------------

class TestExportFormats:
    """ForecastBench and Metaculus export formatting."""

    async def test_export_forecastbench_format(self):
        """The ForecastBench export should contain required top-level keys."""
        harness = BenchmarkHarness.__new__(BenchmarkHarness)

        forecasts = [
            {
                "question_id": str(uuid.uuid4()),
                "question_text": "Will median rent exceed $1,600?",
                "probability": 0.72,
                "rationale": "Upward trend continues",
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        ]

        result = harness.format_forecastbench(forecasts, metadata={"team": "nyc-forecast"})

        assert "format" in result
        assert result["format"] == "forecastbench"
        assert "version" in result
        assert "forecasts" in result
        assert isinstance(result["forecasts"], list)
        assert len(result["forecasts"]) == 1
        assert "metadata" in result
        assert result["metadata"]["team"] == "nyc-forecast"

    async def test_export_metaculus_format(self):
        """The Metaculus export should map to Metaculus prediction schema."""
        harness = BenchmarkHarness.__new__(BenchmarkHarness)

        forecasts = [
            {
                "question_id": str(uuid.uuid4()),
                "probability": 0.65,
                "metaculus_question_id": 12345,
            },
        ]

        result = harness.format_metaculus(forecasts)

        assert "predictions" in result
        assert isinstance(result["predictions"], list)
        assert len(result["predictions"]) == 1
        prediction = result["predictions"][0]
        assert prediction["metaculus_question_id"] == 12345
        assert prediction["prediction"] == 0.65


# ---------------------------------------------------------------------------
# Config comparison
# ---------------------------------------------------------------------------

class TestCompareConfigs:
    """Side-by-side comparison of experiment configurations."""

    async def test_compare_configs(self):
        """Comparing two configs should identify differing parameters."""
        harness = BenchmarkHarness.__new__(BenchmarkHarness)

        config_a = {
            "model_tier_a": "gpt-4o-mini",
            "model_tier_b": "gpt-4o",
            "escalation_threshold": 0.6,
            "use_base_rates": True,
        }
        config_b = {
            "model_tier_a": "gpt-4o-mini",
            "model_tier_b": "claude-sonnet-4-6",
            "escalation_threshold": 0.4,
            "use_base_rates": True,
        }

        diff = harness.compare_configs(config_a, config_b)

        assert "model_tier_b" in diff
        assert "escalation_threshold" in diff
        # Same values should NOT appear in the diff
        assert "model_tier_a" not in diff
        assert "use_base_rates" not in diff
