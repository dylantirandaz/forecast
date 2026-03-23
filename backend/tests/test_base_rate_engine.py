"""Tests for the BaseRateEngine.

Validates distribution statistics computation, trend extraction, and
the full compute_base_rate pipeline.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.services.base_rate_engine import BaseRateEngine, DistributionStats, TrendResult


@pytest.fixture()
def engine() -> BaseRateEngine:
    return BaseRateEngine()


# Realistic NYC rent-stabilised median rent series (annual, 2015-2024)
RENT_SERIES = [1250.0, 1275.0, 1310.0, 1340.0, 1360.0,
               1380.0, 1400.0, 1430.0, 1475.0, 1525.0]


# ------------------------------------------------------------------
# Distribution statistics
# ------------------------------------------------------------------

class TestDistributionStats:
    """Descriptive statistics for a univariate series."""

    def test_compute_distribution_stats(self, engine: BaseRateEngine):
        """Stats should match numpy calculations."""
        stats = engine.get_distribution_stats(RENT_SERIES)

        assert isinstance(stats, DistributionStats)
        assert stats.n == len(RENT_SERIES)
        assert stats.mean == pytest.approx(np.mean(RENT_SERIES), abs=0.01)
        assert stats.median == pytest.approx(np.median(RENT_SERIES), abs=0.01)
        assert stats.std == pytest.approx(
            np.std(RENT_SERIES, ddof=1), abs=0.01
        )
        assert stats.min == pytest.approx(min(RENT_SERIES), abs=0.01)
        assert stats.max == pytest.approx(max(RENT_SERIES), abs=0.01)

    def test_percentiles(self, engine: BaseRateEngine):
        """Percentile values should be monotonically non-decreasing."""
        stats = engine.get_distribution_stats(RENT_SERIES)
        assert stats.p5 <= stats.p10
        assert stats.p10 <= stats.p25
        assert stats.p25 <= stats.median
        assert stats.median <= stats.p75
        assert stats.p75 <= stats.p90
        assert stats.p90 <= stats.p95

    def test_single_value_series(self, engine: BaseRateEngine):
        """A single-value series should have std=0 and all stats equal."""
        stats = engine.get_distribution_stats([42.0])
        assert stats.mean == pytest.approx(42.0)
        assert stats.std == pytest.approx(0.0)
        assert stats.n == 1


# ------------------------------------------------------------------
# Trend extraction
# ------------------------------------------------------------------

class TestTrend:
    """Polynomial trend fitting."""

    def test_compute_trend(self, engine: BaseRateEngine):
        """An increasing rent series should yield an 'increasing' trend."""
        trend = engine.get_trend(RENT_SERIES)

        assert isinstance(trend, TrendResult)
        assert trend.degree == 1
        assert trend.trend_direction == "increasing"
        assert trend.annualised_change > 0
        assert 0.0 <= trend.r_squared <= 1.0
        assert len(trend.coefficients) == 2  # slope + intercept

    def test_flat_trend(self, engine: BaseRateEngine):
        """A constant series should have a 'flat' trend."""
        flat = [100.0] * 10
        trend = engine.get_trend(flat)
        assert trend.trend_direction == "flat"
        assert abs(trend.annualised_change) < 1e-6

    def test_decreasing_trend(self, engine: BaseRateEngine):
        """A strictly decreasing series should have a 'decreasing' trend."""
        decreasing = [100.0, 95.0, 90.0, 85.0, 80.0]
        trend = engine.get_trend(decreasing)
        assert trend.trend_direction == "decreasing"
        assert trend.annualised_change < 0

    def test_high_r_squared_for_linear_data(self, engine: BaseRateEngine):
        """Perfectly linear data should give R-squared very close to 1."""
        linear = [10.0 + 5.0 * i for i in range(20)]
        trend = engine.get_trend(linear)
        assert trend.r_squared == pytest.approx(1.0, abs=1e-6)


# ------------------------------------------------------------------
# Full pipeline
# ------------------------------------------------------------------

class TestComputeBaseRate:
    """End-to-end base-rate computation."""

    def test_compute_base_rate_returns_valid_stats(self, engine: BaseRateEngine):
        """compute_base_rate should return a BaseRate with stats and trend."""
        br = engine.compute_base_rate(
            target_metric="median_rent_stabilised",
            geography="nyc",
            data=RENT_SERIES,
        )

        assert br.target_metric == "median_rent_stabilised"
        assert br.geography == "nyc"
        assert br.stats is not None
        assert br.trend is not None
        assert br.stats.n == len(RENT_SERIES)
        assert br.trend.trend_direction == "increasing"

    def test_compute_base_rate_caching(self, engine: BaseRateEngine):
        """Repeated calls with the same key should return cached results."""
        br1 = engine.compute_base_rate("test_metric", "nyc", RENT_SERIES)
        br2 = engine.compute_base_rate("test_metric", "nyc", RENT_SERIES)
        assert br1 is br2

    def test_compute_base_rate_rejects_too_few_points(self, engine: BaseRateEngine):
        """Fewer than 2 observations should raise ValueError."""
        with pytest.raises(ValueError, match="at least 2"):
            engine.compute_base_rate("x", "nyc", [42.0])

    def test_compute_base_rate_handles_nans(self, engine: BaseRateEngine):
        """NaN values should be silently dropped."""
        data_with_nans = [1.0, float("nan"), 3.0, float("nan"), 5.0]
        br = engine.compute_base_rate("nan_test", "nyc", data_with_nans)
        assert br.stats.n == 3  # only non-NaN values

    def test_clear_cache(self, engine: BaseRateEngine):
        """clear_cache should empty the internal cache."""
        engine.compute_base_rate("cached", "nyc", RENT_SERIES)
        assert len(engine._cache) > 0
        engine.clear_cache()
        assert len(engine._cache) == 0
