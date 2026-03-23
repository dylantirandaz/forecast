"""Calibration and scoring engine.

Computes proper scoring rules (Brier, log), calibration curves,
sharpness, resolution, and supports recalibration via Platt scaling
or isotonic regression.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Sequence

import numpy as np
from numpy.typing import ArrayLike

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BrierScoreResult:
    """Brier score with Murphy (1973) decomposition."""

    brier_score: float  # lower is better, 0-1 for binary
    reliability: float  # calibration component (lower is better)
    resolution: float  # discrimination component (higher is better)
    uncertainty: float  # base-rate entropy
    n: int


@dataclass(frozen=True)
class CalibrationBin:
    """One bin of a calibration / reliability diagram."""

    bin_lower: float
    bin_upper: float
    bin_midpoint: float
    mean_predicted: float
    mean_observed: float
    count: int


@dataclass
class CalibrationReport:
    """Full calibration report across a set of forecast runs."""

    brier_score: float
    log_score: float
    calibration_curve: list[CalibrationBin]
    sharpness: float
    resolution: float
    n_forecasts: int
    summary: str
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class CalibrationEngine:
    """Evaluate and improve probabilistic forecast calibration.

    All methods accept plain arrays/sequences; no ORM dependency.
    """

    # ------------------------------------------------------------------
    # Scoring rules
    # ------------------------------------------------------------------

    @staticmethod
    def compute_brier_score(
        predictions: ArrayLike,
        outcomes: ArrayLike,
    ) -> BrierScoreResult:
        """Standard Brier score with reliability-resolution decomposition.

        Brier = (1/N) * sum( (p_i - o_i)^2 )

        Decomposition (Murphy 1973):
            Brier = Reliability - Resolution + Uncertainty

        Parameters
        ----------
        predictions:
            Array of predicted probabilities in [0, 1].
        outcomes:
            Array of binary outcomes (0 or 1).

        Returns
        -------
        BrierScoreResult
        """
        p = np.asarray(predictions, dtype=np.float64)
        o = np.asarray(outcomes, dtype=np.float64)

        if p.shape != o.shape:
            raise ValueError(
                f"Shape mismatch: predictions {p.shape} vs outcomes {o.shape}"
            )

        n = p.size
        if n == 0:
            raise ValueError("Need at least one prediction-outcome pair.")

        brier = float(np.mean((p - o) ** 2))

        # Base-rate uncertainty.
        o_bar = float(np.mean(o))
        uncertainty = o_bar * (1.0 - o_bar)

        # Bin-based decomposition (10 equal-width bins).
        n_bins = 10
        reliability = 0.0
        resolution = 0.0
        for k in range(n_bins):
            lo = k / n_bins
            hi = (k + 1) / n_bins
            if k < n_bins - 1:
                mask = (p >= lo) & (p < hi)
            else:
                mask = (p >= lo) & (p <= hi)
            n_k = int(mask.sum())
            if n_k == 0:
                continue
            p_k = float(p[mask].mean())
            o_k = float(o[mask].mean())
            reliability += n_k * (p_k - o_k) ** 2
            resolution += n_k * (o_k - o_bar) ** 2

        reliability /= n
        resolution /= n

        return BrierScoreResult(
            brier_score=brier,
            reliability=reliability,
            resolution=resolution,
            uncertainty=uncertainty,
            n=n,
        )

    @staticmethod
    def compute_log_score(
        predictions: ArrayLike,
        outcomes: ArrayLike,
        eps: float = 1e-15,
    ) -> float:
        """Mean logarithmic scoring rule (lower is better).

        log_score = -(1/N) * sum( o_i*log(p_i) + (1-o_i)*log(1-p_i) )

        Parameters
        ----------
        predictions:
            Predicted probabilities in [0, 1].
        outcomes:
            Binary outcomes (0 or 1).
        eps:
            Small constant to avoid log(0).

        Returns
        -------
        float
        """
        p = np.clip(
            np.asarray(predictions, dtype=np.float64), eps, 1.0 - eps
        )
        o = np.asarray(outcomes, dtype=np.float64)

        return -float(
            np.mean(o * np.log(p) + (1.0 - o) * np.log(1.0 - p))
        )

    # ------------------------------------------------------------------
    # Calibration curve
    # ------------------------------------------------------------------

    @staticmethod
    def compute_calibration_curve(
        predictions: ArrayLike,
        outcomes: ArrayLike,
        n_bins: int = 10,
    ) -> list[CalibrationBin]:
        """Compute reliability diagram data.

        Bins predictions into ``n_bins`` equal-width buckets and
        computes the mean predicted probability and the observed
        frequency (fraction of positive outcomes) in each bin.

        Parameters
        ----------
        predictions:
            Predicted probabilities in [0, 1].
        outcomes:
            Binary outcomes (0 or 1).
        n_bins:
            Number of bins (default 10).

        Returns
        -------
        list[CalibrationBin]
        """
        p = np.asarray(predictions, dtype=np.float64)
        o = np.asarray(outcomes, dtype=np.float64)
        bins: list[CalibrationBin] = []

        for k in range(n_bins):
            lo = k / n_bins
            hi = (k + 1) / n_bins
            if k < n_bins - 1:
                mask = (p >= lo) & (p < hi)
            else:
                mask = (p >= lo) & (p <= hi)

            count = int(mask.sum())
            if count == 0:
                mean_pred = (lo + hi) / 2.0
                mean_obs = 0.0
            else:
                mean_pred = float(p[mask].mean())
                mean_obs = float(o[mask].mean())

            bins.append(
                CalibrationBin(
                    bin_lower=lo,
                    bin_upper=hi,
                    bin_midpoint=(lo + hi) / 2.0,
                    mean_predicted=mean_pred,
                    mean_observed=mean_obs,
                    count=count,
                )
            )

        return bins

    # ------------------------------------------------------------------
    # Sharpness and resolution
    # ------------------------------------------------------------------

    @staticmethod
    def compute_sharpness(predictions: ArrayLike) -> float:
        """Measure how decisive the forecasts are.

        Sharpness = mean( (p_i - 0.5)^2 ).

        A forecaster who always says 50 % has sharpness 0.  One who
        always says 0 % or 100 % has sharpness 0.25.

        Parameters
        ----------
        predictions:
            Predicted probabilities in [0, 1].

        Returns
        -------
        float
        """
        p = np.asarray(predictions, dtype=np.float64)
        return float(np.mean((p - 0.5) ** 2))

    @staticmethod
    def compute_resolution(
        predictions: ArrayLike,
        outcomes: ArrayLike,
        n_bins: int = 10,
    ) -> float:
        """Measure the model's ability to discriminate outcomes.

        Resolution = (1/N) * sum_k n_k * (o_k - o_bar)^2

        Higher is better.

        Parameters
        ----------
        predictions:
            Predicted probabilities in [0, 1].
        outcomes:
            Binary outcomes (0 or 1).
        n_bins:
            Number of bins.

        Returns
        -------
        float
        """
        p = np.asarray(predictions, dtype=np.float64)
        o = np.asarray(outcomes, dtype=np.float64)
        o_bar = float(np.mean(o))
        n = p.size

        resolution = 0.0
        for k in range(n_bins):
            lo = k / n_bins
            hi = (k + 1) / n_bins
            if k < n_bins - 1:
                mask = (p >= lo) & (p < hi)
            else:
                mask = (p >= lo) & (p <= hi)
            n_k = int(mask.sum())
            if n_k == 0:
                continue
            o_k = float(o[mask].mean())
            resolution += n_k * (o_k - o_bar) ** 2

        return resolution / n if n > 0 else 0.0

    # ------------------------------------------------------------------
    # Report generation
    # ------------------------------------------------------------------

    def generate_calibration_report(
        self,
        predictions: ArrayLike,
        outcomes: ArrayLike,
        n_bins: int = 10,
    ) -> CalibrationReport:
        """Generate a full calibration report.

        Parameters
        ----------
        predictions:
            Array of predicted probabilities.
        outcomes:
            Array of binary outcomes.
        n_bins:
            Number of bins for calibration curve.

        Returns
        -------
        CalibrationReport
        """
        brier_result = self.compute_brier_score(predictions, outcomes)
        log_score = self.compute_log_score(predictions, outcomes)
        cal_curve = self.compute_calibration_curve(
            predictions, outcomes, n_bins
        )
        sharpness = self.compute_sharpness(predictions)
        resolution = self.compute_resolution(predictions, outcomes, n_bins)

        p = np.asarray(predictions, dtype=np.float64)
        o = np.asarray(outcomes, dtype=np.float64)
        summary_lines = [
            f"Calibration Report ({brier_result.n} forecasts)",
            f"  Brier score:  {brier_result.brier_score:.4f}",
            f"  Log score:    {log_score:.4f}",
            f"  Reliability:  {brier_result.reliability:.4f}",
            f"  Resolution:   {resolution:.4f}",
            f"  Sharpness:    {sharpness:.4f}",
            f"  Mean pred:    {float(p.mean()):.4f}",
            f"  Mean outcome: {float(o.mean()):.4f}",
        ]

        return CalibrationReport(
            brier_score=brier_result.brier_score,
            log_score=log_score,
            calibration_curve=cal_curve,
            sharpness=sharpness,
            resolution=resolution,
            n_forecasts=brier_result.n,
            summary="\n".join(summary_lines),
        )

    # ------------------------------------------------------------------
    # Recalibration
    # ------------------------------------------------------------------

    @staticmethod
    def recalibrate(
        predictions: ArrayLike,
        outcomes: ArrayLike,
        method: str = "platt",
    ) -> dict[str, Any]:
        """Fit a recalibration model (Platt scaling or isotonic).

        Parameters
        ----------
        predictions:
            Training-set predicted probabilities.
        outcomes:
            Training-set binary outcomes.
        method:
            ``"platt"`` (logistic regression on logits) or
            ``"isotonic"`` (isotonic regression).

        Returns
        -------
        dict
            ``{"method": ..., "params": ..., "transform": callable}``
            where ``transform(p_array) -> recalibrated_p_array``.
        """
        p = np.asarray(predictions, dtype=np.float64)
        o = np.asarray(outcomes, dtype=np.float64)

        if method == "platt":
            eps = 1e-7
            logits = np.log(
                np.clip(p, eps, 1 - eps)
                / np.clip(1 - p, eps, 1 - eps)
            )

            from numpy.linalg import lstsq

            X = np.column_stack([logits, np.ones_like(logits)])
            o_smooth = np.clip(o, eps, 1 - eps)
            y = np.log(o_smooth / (1 - o_smooth))

            coeffs, *_ = lstsq(X, y, rcond=None)
            a, b = float(coeffs[0]), float(coeffs[1])

            def platt_transform(raw: ArrayLike) -> np.ndarray:
                raw_arr = np.asarray(raw, dtype=np.float64)
                raw_logits = np.log(
                    np.clip(raw_arr, eps, 1 - eps)
                    / np.clip(1 - raw_arr, eps, 1 - eps)
                )
                return 1.0 / (1.0 + np.exp(-(a * raw_logits + b)))

            return {
                "method": "platt",
                "params": {"a": a, "b": b},
                "transform": platt_transform,
            }

        elif method == "isotonic":
            order = np.argsort(p)
            p_sorted = p[order]
            o_sorted = o[order]

            iso_values = _pool_adjacent_violators(o_sorted)

            unique_mask = np.concatenate(
                [[True], np.diff(p_sorted) > 1e-12]
            )
            p_unique = p_sorted[unique_mask]
            iso_unique = iso_values[unique_mask]

            if len(p_unique) < 2:
                constant_val = float(np.mean(o))

                def iso_transform_const(raw: ArrayLike) -> np.ndarray:
                    return np.full_like(
                        np.asarray(raw, dtype=np.float64), constant_val
                    )

                return {
                    "method": "isotonic",
                    "params": {"constant": constant_val},
                    "transform": iso_transform_const,
                }

            from scipy.interpolate import interp1d

            interpolator = interp1d(
                p_unique,
                iso_unique,
                kind="linear",
                bounds_error=False,
                fill_value=(
                    float(iso_unique[0]),
                    float(iso_unique[-1]),
                ),
            )

            def iso_transform_interp(raw: ArrayLike) -> np.ndarray:
                return np.clip(
                    interpolator(np.asarray(raw, dtype=np.float64)),
                    0.0,
                    1.0,
                )

            return {
                "method": "isotonic",
                "params": {
                    "knots_p": p_unique.tolist(),
                    "knots_iso": iso_unique.tolist(),
                },
                "transform": iso_transform_interp,
            }

        else:
            raise ValueError(
                f"Unknown recalibration method '{method}'. "
                f"Use 'platt' or 'isotonic'."
            )


# ---------------------------------------------------------------------------
# Utility: Pool Adjacent Violators Algorithm
# ---------------------------------------------------------------------------

def _pool_adjacent_violators(y: np.ndarray) -> np.ndarray:
    """Isotonic regression via the pool-adjacent-violators algorithm.

    Parameters
    ----------
    y:
        1-D array of values to make monotonically non-decreasing.

    Returns
    -------
    np.ndarray
        Isotonic-fit values, same length as *y*.
    """
    n = len(y)
    result = y.astype(np.float64).copy()
    blocks: list[list[float]] = []

    for i in range(n):
        blocks.append([float(result[i]), 1.0])
        while len(blocks) > 1 and blocks[-2][0] > blocks[-1][0]:
            prev = blocks[-2]
            curr = blocks[-1]
            merged_value = (
                (prev[0] * prev[1] + curr[0] * curr[1])
                / (prev[1] + curr[1])
            )
            prev[0] = merged_value
            prev[1] += curr[1]
            blocks.pop()

    idx = 0
    for value, count in blocks:
        c = int(count)
        result[idx : idx + c] = value
        idx += c

    return result
