"""Tests for the CalibrationEngine.

Validates Brier scores, log scores, and calibration curve binning.
"""

from __future__ import annotations

import math

import pytest

from app.services.calibration import CalibrationEngine


@pytest.fixture()
def engine() -> CalibrationEngine:
    return CalibrationEngine()


# ------------------------------------------------------------------
# Brier score
# ------------------------------------------------------------------

class TestBrierScore:
    """Individual and batch Brier scores."""

    def test_brier_score_perfect(self, engine: CalibrationEngine):
        """A perfect forecast (1.0 for outcome=1) should score 0.0."""
        assert engine.brier_score(1.0, 1.0) == pytest.approx(0.0)

    def test_brier_score_perfect_negative(self, engine: CalibrationEngine):
        """A perfect forecast (0.0 for outcome=0) should also score 0.0."""
        assert engine.brier_score(0.0, 0.0) == pytest.approx(0.0)

    def test_brier_score_worst(self, engine: CalibrationEngine):
        """The worst possible forecast (0.0 for outcome=1) should score 1.0."""
        assert engine.brier_score(0.0, 1.0) == pytest.approx(1.0)

    def test_brier_score_worst_inverse(self, engine: CalibrationEngine):
        """Predicting 1.0 when outcome is 0 should also score 1.0."""
        assert engine.brier_score(1.0, 0.0) == pytest.approx(1.0)

    def test_brier_score_uniform(self, engine: CalibrationEngine):
        """A completely uninformed 0.5 forecast should score 0.25."""
        assert engine.brier_score(0.5, 1.0) == pytest.approx(0.25)
        assert engine.brier_score(0.5, 0.0) == pytest.approx(0.25)

    def test_brier_score_asymmetric(self, engine: CalibrationEngine):
        """Brier score for a 0.7 forecast on outcome=1."""
        expected = (0.7 - 1.0) ** 2
        assert engine.brier_score(0.7, 1.0) == pytest.approx(expected)

    def test_mean_brier_score(self, engine: CalibrationEngine):
        """Mean Brier across multiple forecasts."""
        forecasts = [0.9, 0.3, 0.8, 0.1]
        outcomes = [1.0, 0.0, 1.0, 0.0]
        expected = sum(
            (f - o) ** 2 for f, o in zip(forecasts, outcomes)
        ) / len(forecasts)
        assert engine.mean_brier_score(forecasts, outcomes) == pytest.approx(expected)


# ------------------------------------------------------------------
# Log score
# ------------------------------------------------------------------

class TestLogScore:
    """Logarithmic scoring rule."""

    def test_log_score_perfect(self, engine: CalibrationEngine):
        """Perfect forecast should have log score close to 0."""
        score = engine.log_score(0.999, 1.0)
        assert score < 0.0
        assert score > -0.01  # very close to 0

    def test_log_score_terrible(self, engine: CalibrationEngine):
        """A near-zero forecast for outcome=1 should produce a very negative score."""
        score = engine.log_score(0.01, 1.0)
        assert score < -4.0  # ln(0.01) ~ -4.6

    def test_log_score_outcome_zero(self, engine: CalibrationEngine):
        """For outcome=0, a low forecast probability should score well."""
        score = engine.log_score(0.1, 0.0)
        # log(1 - 0.1) = log(0.9) ~ -0.105
        assert score == pytest.approx(math.log(0.9), abs=1e-10)

    def test_log_score_uniform(self, engine: CalibrationEngine):
        """A 0.5 forecast should give log(0.5) for either outcome."""
        score_yes = engine.log_score(0.5, 1.0)
        score_no = engine.log_score(0.5, 0.0)
        assert score_yes == pytest.approx(math.log(0.5), abs=1e-10)
        assert score_no == pytest.approx(math.log(0.5), abs=1e-10)

    def test_mean_log_score(self, engine: CalibrationEngine):
        """Mean log score across multiple forecasts."""
        forecasts = [0.9, 0.2]
        outcomes = [1.0, 0.0]
        expected = (math.log(0.9) + math.log(0.8)) / 2
        assert engine.mean_log_score(forecasts, outcomes) == pytest.approx(
            expected, abs=1e-10
        )


# ------------------------------------------------------------------
# Calibration curve
# ------------------------------------------------------------------

class TestCalibrationCurve:
    """Calibration curve binning."""

    def test_calibration_curve_bins(self, engine: CalibrationEngine):
        """Verify that bins are produced and cover the data range."""
        # Construct a set of forecasts spread across the [0, 1] range.
        forecasts = [0.05, 0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.95]
        outcomes = [0.0, 0.0, 0.0, 1.0, 0.0, 1.0, 1.0, 1.0, 1.0, 1.0]

        buckets = engine.calibration_curve(forecasts, outcomes, n_bins=5)

        # Should produce buckets (non-empty bins only).
        assert len(buckets) > 0

        # Each bucket should have valid bounds and counts.
        for b in buckets:
            assert 0.0 <= b.bucket_lower <= b.bucket_upper <= 1.0
            assert b.count > 0
            assert 0.0 <= b.predicted_mean <= 1.0
            assert 0.0 <= b.observed_frequency <= 1.0

        # Total counts across all buckets should equal the number of forecasts.
        total_count = sum(b.count for b in buckets)
        assert total_count == len(forecasts)

    def test_calibration_curve_single_bin(self, engine: CalibrationEngine):
        """With n_bins=1, all forecasts should fall in one bucket."""
        forecasts = [0.3, 0.7]
        outcomes = [0.0, 1.0]
        buckets = engine.calibration_curve(forecasts, outcomes, n_bins=1)
        assert len(buckets) == 1
        assert buckets[0].count == 2
        assert buckets[0].predicted_mean == pytest.approx(0.5)
        assert buckets[0].observed_frequency == pytest.approx(0.5)

    def test_calibration_curve_empty_bins_skipped(self, engine: CalibrationEngine):
        """Bins with no forecasts should be omitted from the output."""
        # All forecasts clustered in the 0.4-0.6 range.
        forecasts = [0.45, 0.50, 0.55]
        outcomes = [0.0, 1.0, 1.0]
        buckets = engine.calibration_curve(forecasts, outcomes, n_bins=10)
        # Should have far fewer buckets than 10 since most bins are empty.
        assert len(buckets) < 10
        assert sum(b.count for b in buckets) == 3
