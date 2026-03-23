"""Base-rate computation engine.

Computes historical baseline distributions and trend estimates that serve
as the uninformed prior before any evidence is incorporated.  All
statistical heavy-lifting uses numpy/scipy so the caller can pass plain
Python sequences or numpy arrays.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Sequence

import numpy as np
from numpy.typing import ArrayLike

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DistributionStats:
    """Summary statistics for a univariate series."""

    mean: float
    median: float
    std: float
    min: float
    max: float
    p5: float
    p10: float
    p25: float
    p75: float
    p90: float
    p95: float
    n: int


@dataclass(frozen=True)
class TrendResult:
    """Result of a trend extraction."""

    coefficients: list[float]
    degree: int
    r_squared: float
    trend_direction: str  # "increasing", "decreasing", "flat"
    annualised_change: float


@dataclass
class BaseRate:
    """A computed base-rate prior for a target metric in a geography."""

    target_metric: str
    geography: str
    stats: DistributionStats
    trend: TrendResult | None = None
    analog_prior: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class BaseRateEngine:
    """Compute historical base-rate priors for forecasting questions.

    The engine operates on time-series data that the caller loads from
    whatever data source is appropriate (Census, HVS, NYCHVS, RGB orders,
    etc.).  It exposes pure-functional helpers plus a thin caching layer
    so that the same base rate is not recomputed within a single session.
    """

    def __init__(self) -> None:
        self._cache: dict[str, BaseRate] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compute_base_rate(
        self,
        target_metric: str,
        geography: str,
        data: ArrayLike,
    ) -> BaseRate:
        """Compute a full base-rate prior from historical time-series data.

        Parameters
        ----------
        target_metric:
            Name of the metric (e.g. ``"median_rent_stabilised"``).
        geography:
            Geographic scope (e.g. ``"nyc"`` or ``"manhattan_cd_03"``).
        data:
            One-dimensional array-like of chronologically ordered
            observations.  ``NaN`` values are dropped automatically.

        Returns
        -------
        BaseRate
            Frozen data class with distribution stats and trend info.
        """
        cache_key = f"{target_metric}::{geography}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        series = np.asarray(data, dtype=np.float64)
        series = series[~np.isnan(series)]

        if series.size < 2:
            raise ValueError(
                f"Need at least 2 non-NaN observations for base-rate "
                f"computation; got {series.size}."
            )

        stats = self.get_distribution_stats(series)
        trend = self.get_trend(series)

        base_rate = BaseRate(
            target_metric=target_metric,
            geography=geography,
            stats=stats,
            trend=trend,
        )
        self._cache[cache_key] = base_rate
        logger.info(
            "Computed base rate for %s @ %s  (mean=%.4f, trend=%s)",
            target_metric,
            geography,
            stats.mean,
            trend.trend_direction,
        )
        return base_rate

    def compute_analog_prior(
        self,
        target_metric: str,
        analogs: Sequence[dict[str, Any]],
    ) -> float:
        """Estimate a prior probability from analogous historical situations.

        Each *analog* is a dict with at least the keys ``"outcome_value"``
        (the observed outcome) and optionally ``"weight"`` (a relevance
        weight, default 1.0).

        For binary metrics the returned value is the weighted fraction of
        positive outcomes.  For continuous metrics it is the weighted mean
        of ``outcome_value``.

        Parameters
        ----------
        target_metric:
            Name of the metric (used for cache key).
        analogs:
            Sequence of dicts describing historical analogs.

        Returns
        -------
        float
            The analog-weighted prior estimate.
        """
        if not analogs:
            raise ValueError("At least one analog is required.")

        values = np.array(
            [a["outcome_value"] for a in analogs], dtype=np.float64
        )
        weights = np.array(
            [a.get("weight", 1.0) for a in analogs], dtype=np.float64
        )
        weights = weights / weights.sum()  # normalise

        weighted_mean: float = float(np.dot(weights, values))
        logger.info(
            "Analog prior for %s from %d analogs = %.4f",
            target_metric,
            len(analogs),
            weighted_mean,
        )
        return weighted_mean

    # ------------------------------------------------------------------
    # Statistical helpers
    # ------------------------------------------------------------------

    @staticmethod
    def get_distribution_stats(series: ArrayLike) -> DistributionStats:
        """Compute descriptive statistics for a 1-D series.

        Parameters
        ----------
        series:
            Array-like of numeric values (NaNs should already be removed).

        Returns
        -------
        DistributionStats
        """
        arr = np.asarray(series, dtype=np.float64)
        return DistributionStats(
            mean=float(np.mean(arr)),
            median=float(np.median(arr)),
            std=float(np.std(arr, ddof=1)) if arr.size > 1 else 0.0,
            min=float(np.min(arr)),
            max=float(np.max(arr)),
            p5=float(np.percentile(arr, 5)),
            p10=float(np.percentile(arr, 10)),
            p25=float(np.percentile(arr, 25)),
            p75=float(np.percentile(arr, 75)),
            p90=float(np.percentile(arr, 90)),
            p95=float(np.percentile(arr, 95)),
            n=int(arr.size),
        )

    @staticmethod
    def get_trend(
        series: ArrayLike,
        degree: int = 1,
    ) -> TrendResult:
        """Extract a polynomial trend from a chronologically ordered series.

        Parameters
        ----------
        series:
            Array-like of chronologically ordered observations.
        degree:
            Polynomial degree (1 = linear, 2 = quadratic, etc.).

        Returns
        -------
        TrendResult
        """
        arr = np.asarray(series, dtype=np.float64)
        t = np.arange(arr.size, dtype=np.float64)

        coefficients = np.polyfit(t, arr, degree)

        # R-squared
        predicted = np.polyval(coefficients, t)
        ss_res = float(np.sum((arr - predicted) ** 2))
        ss_tot = float(np.sum((arr - np.mean(arr)) ** 2))
        r_squared = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0

        # Annualised change: use the linear coefficient (the slope term).
        # For a degree-1 fit this is coefficients[0]; for higher degrees
        # we still report the linear term as the dominant trend signal.
        linear_slope = float(coefficients[-2]) if degree >= 1 else 0.0

        if abs(linear_slope) < 1e-9:
            trend_direction = "flat"
        elif linear_slope > 0:
            trend_direction = "increasing"
        else:
            trend_direction = "decreasing"

        return TrendResult(
            coefficients=[float(c) for c in coefficients],
            degree=degree,
            r_squared=r_squared,
            trend_direction=trend_direction,
            annualised_change=linear_slope,
        )

    # ------------------------------------------------------------------
    # Cache management
    # ------------------------------------------------------------------

    def clear_cache(self) -> None:
        """Drop all cached base rates."""
        self._cache.clear()
