"""Comprehensive evaluation metrics engine.

Computes all scoring rules, calibration metrics, and breakdowns
needed for rigorous forecasting evaluation.
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
class MetricsSummary:
    """Summary metrics for an evaluation."""
    brier_score: float
    log_score: float
    calibration_error: float  # ECE
    sharpness: float
    resolution: float
    reliability: float
    n_predictions: int
    n_questions: int
    mean_prediction: float
    base_rate: float  # observed resolution rate


@dataclass(frozen=True)
class CalibrationBinData:
    """One bin for calibration/reliability diagrams."""
    bin_lower: float
    bin_upper: float
    bin_midpoint: float
    mean_predicted: float
    mean_observed: float
    count: int
    confidence_interval_lower: float = 0.0
    confidence_interval_upper: float = 1.0


@dataclass
class DomainMetrics:
    """Metrics broken down by domain."""
    domain: str
    brier_score: float
    log_score: float
    calibration_error: float
    sharpness: float
    n_predictions: int
    delta_vs_baseline: float = 0.0  # delta vs always-0.5


@dataclass
class HorizonMetrics:
    """Metrics broken down by forecast horizon."""
    horizon_label: str  # e.g. "90d", "30d", "7d"
    brier_score: float
    log_score: float
    calibration_error: float
    sharpness: float
    n_predictions: int
    improvement_from_prior: float = 0.0  # improvement vs longer horizon


@dataclass
class BaselineComparison:
    """Comparison against baseline predictors."""
    model_brier: float
    always_half_brier: float
    base_rate_brier: float
    model_vs_half_delta: float
    model_vs_base_rate_delta: float
    skill_score: float  # 1 - model_brier / reference_brier


@dataclass
class FullEvalReport:
    """Complete evaluation report."""
    summary: MetricsSummary
    calibration_curve: list[CalibrationBinData]
    domain_breakdown: list[DomainMetrics]
    horizon_breakdown: list[HorizonMetrics]
    baseline_comparison: BaselineComparison
    prediction_histogram: list[dict]  # for sharpness visualization
    reliability_data: dict  # for reliability diagram
    metadata: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class EvalMetricsEngine:
    """Comprehensive evaluation metrics engine.

    Computes:
    - Brier score (with Murphy decomposition)
    - Log loss / log score
    - Expected Calibration Error (ECE)
    - Maximum Calibration Error (MCE)
    - Sharpness (distribution of predictions)
    - Resolution (discrimination ability)
    - Reliability (calibration quality)
    - Baseline comparisons (vs always-0.5, vs base-rate-only)
    - Domain and horizon breakdowns
    - Reliability diagram data
    """

    def __init__(self, n_calibration_bins: int = 10):
        self.n_bins = n_calibration_bins

    # ------------------------------------------------------------------
    # Scoring rules
    # ------------------------------------------------------------------

    def compute_brier_score(
        self,
        predictions: ArrayLike,
        outcomes: ArrayLike,
    ) -> float:
        """Compute mean Brier score.

        Brier = mean((predicted - actual)^2)
        Range: 0 (perfect) to 1 (worst for binary).
        """
        preds = np.asarray(predictions, dtype=float)
        outs = np.asarray(outcomes, dtype=float)
        return float(np.mean((preds - outs) ** 2))

    def compute_brier_decomposition(
        self,
        predictions: ArrayLike,
        outcomes: ArrayLike,
    ) -> dict[str, float]:
        """Murphy (1973) decomposition: Brier = Reliability - Resolution + Uncertainty.

        - Reliability: measures calibration (lower is better)
        - Resolution: measures discrimination (higher is better)
        - Uncertainty: base-rate entropy (fixed for a given dataset)
        """
        preds = np.asarray(predictions, dtype=float)
        outs = np.asarray(outcomes, dtype=float)
        n = len(preds)
        base_rate = float(np.mean(outs))
        uncertainty = base_rate * (1 - base_rate)

        # Bin predictions
        bins_indices = np.digitize(preds, np.linspace(0, 1, self.n_bins + 1)) - 1
        bins_indices = np.clip(bins_indices, 0, self.n_bins - 1)

        reliability = 0.0
        resolution = 0.0

        for b in range(self.n_bins):
            mask = bins_indices == b
            n_b = int(np.sum(mask))
            if n_b == 0:
                continue
            mean_pred = float(np.mean(preds[mask]))
            mean_obs = float(np.mean(outs[mask]))
            reliability += n_b * (mean_pred - mean_obs) ** 2
            resolution += n_b * (mean_obs - base_rate) ** 2

        reliability /= n
        resolution /= n

        return {
            "brier_score": float(np.mean((preds - outs) ** 2)),
            "reliability": float(reliability),
            "resolution": float(resolution),
            "uncertainty": float(uncertainty),
        }

    def compute_log_score(
        self,
        predictions: ArrayLike,
        outcomes: ArrayLike,
    ) -> float:
        """Compute mean log loss / log score.

        LogLoss = -mean(y*log(p) + (1-y)*log(1-p))
        Penalizes overconfident wrong predictions heavily.
        """
        preds = np.asarray(predictions, dtype=float)
        outs = np.asarray(outcomes, dtype=float)
        eps = 1e-15
        preds_clamp = np.clip(preds, eps, 1 - eps)
        log_loss = -(outs * np.log(preds_clamp) + (1 - outs) * np.log(1 - preds_clamp))
        return float(np.mean(log_loss))

    # ------------------------------------------------------------------
    # Calibration
    # ------------------------------------------------------------------

    def compute_calibration_curve(
        self,
        predictions: ArrayLike,
        outcomes: ArrayLike,
        n_bins: int | None = None,
    ) -> list[CalibrationBinData]:
        """Compute calibration curve data for reliability diagrams.

        Bins predictions into n_bins equal-width bins and computes
        mean predicted vs mean observed probability in each bin.
        Also computes Wilson confidence intervals for observed frequency.
        """
        preds = np.asarray(predictions, dtype=float)
        outs = np.asarray(outcomes, dtype=float)
        n_bins = n_bins or self.n_bins

        bins: list[CalibrationBinData] = []
        edges = np.linspace(0, 1, n_bins + 1)

        for i in range(n_bins):
            lower, upper = float(edges[i]), float(edges[i + 1])
            if i < n_bins - 1:
                mask = (preds >= lower) & (preds < upper)
            else:
                mask = (preds >= lower) & (preds <= upper)
            count = int(np.sum(mask))

            if count == 0:
                bins.append(CalibrationBinData(
                    bin_lower=lower,
                    bin_upper=upper,
                    bin_midpoint=(lower + upper) / 2,
                    mean_predicted=(lower + upper) / 2,
                    mean_observed=0.0,
                    count=0,
                ))
                continue

            mean_pred = float(np.mean(preds[mask]))
            mean_obs = float(np.mean(outs[mask]))

            # Wilson score interval for observed proportion
            z = 1.96  # 95% CI
            denom = 1 + z**2 / count
            center = (mean_obs + z**2 / (2 * count)) / denom
            spread = z * math.sqrt((mean_obs * (1 - mean_obs) + z**2 / (4 * count)) / count) / denom
            ci_lower = max(0.0, center - spread)
            ci_upper = min(1.0, center + spread)

            bins.append(CalibrationBinData(
                bin_lower=lower,
                bin_upper=upper,
                bin_midpoint=(lower + upper) / 2,
                mean_predicted=mean_pred,
                mean_observed=mean_obs,
                count=count,
                confidence_interval_lower=ci_lower,
                confidence_interval_upper=ci_upper,
            ))

        return bins

    def compute_ece(
        self,
        predictions: ArrayLike,
        outcomes: ArrayLike,
    ) -> float:
        """Expected Calibration Error (ECE).

        Weighted average of |mean_predicted - mean_observed| across bins.
        """
        bins = self.compute_calibration_curve(predictions, outcomes)
        total = sum(b.count for b in bins)
        if total == 0:
            return 0.0

        ece = sum(
            b.count / total * abs(b.mean_predicted - b.mean_observed)
            for b in bins if b.count > 0
        )
        return float(ece)

    def compute_mce(
        self,
        predictions: ArrayLike,
        outcomes: ArrayLike,
    ) -> float:
        """Maximum Calibration Error (MCE).

        Maximum |mean_predicted - mean_observed| across bins.
        """
        bins = self.compute_calibration_curve(predictions, outcomes)
        nonempty = [b for b in bins if b.count > 0]
        if not nonempty:
            return 0.0
        return float(max(abs(b.mean_predicted - b.mean_observed) for b in nonempty))

    # ------------------------------------------------------------------
    # Sharpness
    # ------------------------------------------------------------------

    def compute_sharpness(self, predictions: ArrayLike) -> float:
        """Sharpness: average distance of predictions from 0.5.

        Higher = more decisive predictions.
        Range: 0 (always 0.5) to 0.5 (always 0 or 1).
        """
        preds = np.asarray(predictions, dtype=float)
        return float(np.mean(np.abs(preds - 0.5)))

    def compute_prediction_histogram(
        self,
        predictions: ArrayLike,
        n_bins: int = 20,
    ) -> list[dict]:
        """Histogram of prediction distribution for sharpness visualization."""
        preds = np.asarray(predictions, dtype=float)
        counts, edges = np.histogram(preds, bins=n_bins, range=(0, 1))
        return [
            {
                "bin_lower": float(edges[i]),
                "bin_upper": float(edges[i + 1]),
                "count": int(counts[i]),
            }
            for i in range(n_bins)
        ]

    # ------------------------------------------------------------------
    # Baseline comparisons
    # ------------------------------------------------------------------

    def compute_baseline_comparison(
        self,
        predictions: ArrayLike,
        outcomes: ArrayLike,
    ) -> BaselineComparison:
        """Compare model against baseline predictors.

        Baselines:
        1. Always 0.5 predictor (uninformed)
        2. Base-rate-only predictor (dataset resolution rate)
        """
        preds = np.asarray(predictions, dtype=float)
        outs = np.asarray(outcomes, dtype=float)

        model_brier = self.compute_brier_score(preds, outs)

        # Always 0.5
        half_preds = np.full_like(preds, 0.5)
        always_half_brier = self.compute_brier_score(half_preds, outs)

        # Base rate only
        base_rate = float(np.mean(outs))
        br_preds = np.full_like(preds, base_rate)
        base_rate_brier = self.compute_brier_score(br_preds, outs)

        # Skill score: 1 - model/reference (positive = better than reference)
        reference = max(always_half_brier, 1e-10)
        skill = 1 - model_brier / reference

        return BaselineComparison(
            model_brier=round(model_brier, 6),
            always_half_brier=round(always_half_brier, 6),
            base_rate_brier=round(base_rate_brier, 6),
            model_vs_half_delta=round(model_brier - always_half_brier, 6),
            model_vs_base_rate_delta=round(model_brier - base_rate_brier, 6),
            skill_score=round(skill, 6),
        )

    # ------------------------------------------------------------------
    # Full report
    # ------------------------------------------------------------------

    def compute_full_report(
        self,
        predictions: list[dict],  # each has: predicted_probability, actual_value, domain, cutoff_days, difficulty
    ) -> FullEvalReport:
        """Compute comprehensive evaluation report.

        Args:
            predictions: list of dicts with at minimum:
                - predicted_probability (float)
                - actual_value (float, 0 or 1 for binary)
                - domain (str, optional)
                - cutoff_days (int, optional)
                - difficulty (str, optional)
        """
        if not predictions:
            raise ValueError("No predictions to evaluate")

        probs = np.array([p["predicted_probability"] for p in predictions])
        actuals = np.array([p["actual_value"] for p in predictions])

        # Core metrics
        decomp = self.compute_brier_decomposition(probs, actuals)
        log_score = self.compute_log_score(probs, actuals)
        ece = self.compute_ece(probs, actuals)
        sharpness = self.compute_sharpness(probs)

        summary = MetricsSummary(
            brier_score=round(decomp["brier_score"], 6),
            log_score=round(log_score, 6),
            calibration_error=round(ece, 6),
            sharpness=round(sharpness, 6),
            resolution=round(decomp["resolution"], 6),
            reliability=round(decomp["reliability"], 6),
            n_predictions=len(predictions),
            n_questions=len(set(p.get("question_id", i) for i, p in enumerate(predictions))),
            mean_prediction=round(float(np.mean(probs)), 6),
            base_rate=round(float(np.mean(actuals)), 6),
        )

        # Calibration curve
        cal_curve = self.compute_calibration_curve(probs, actuals)

        # Domain breakdown
        domain_metrics = self._compute_domain_breakdown(predictions, probs, actuals)

        # Horizon breakdown
        horizon_metrics = self._compute_horizon_breakdown(predictions, probs, actuals)

        # Baseline comparison
        baseline = self.compute_baseline_comparison(probs, actuals)

        # Prediction histogram
        pred_hist = self.compute_prediction_histogram(probs)

        # Reliability data for plotting
        reliability_data = {
            "bins": [
                {
                    "midpoint": b.bin_midpoint,
                    "predicted": b.mean_predicted,
                    "observed": b.mean_observed,
                    "count": b.count,
                    "ci_lower": b.confidence_interval_lower,
                    "ci_upper": b.confidence_interval_upper,
                }
                for b in cal_curve if b.count > 0
            ],
            "perfect_line": [[0, 0], [1, 1]],
        }

        return FullEvalReport(
            summary=summary,
            calibration_curve=cal_curve,
            domain_breakdown=domain_metrics,
            horizon_breakdown=horizon_metrics,
            baseline_comparison=baseline,
            prediction_histogram=pred_hist,
            reliability_data=reliability_data,
        )

    # ------------------------------------------------------------------
    # Breakdown helpers
    # ------------------------------------------------------------------

    def _compute_domain_breakdown(
        self,
        predictions: list[dict],
        probs: np.ndarray,
        actuals: np.ndarray,
    ) -> list[DomainMetrics]:
        """Compute metrics per domain."""
        domains: dict[str, list[int]] = {}
        for i, p in enumerate(predictions):
            d = p.get("domain", "other")
            domains.setdefault(d, []).append(i)

        result: list[DomainMetrics] = []

        for domain, indices in sorted(domains.items()):
            idx_arr = np.array(indices)
            d_probs = probs[idx_arr]
            d_actuals = actuals[idx_arr]
            d_brier = self.compute_brier_score(d_probs, d_actuals)
            d_log = self.compute_log_score(d_probs, d_actuals)
            d_ece = self.compute_ece(d_probs, d_actuals)
            d_sharp = self.compute_sharpness(d_probs)

            # Delta vs always-0.5 baseline
            d_half_brier = self.compute_brier_score(np.full_like(d_probs, 0.5), d_actuals)

            result.append(DomainMetrics(
                domain=domain,
                brier_score=round(d_brier, 6),
                log_score=round(d_log, 6),
                calibration_error=round(d_ece, 6),
                sharpness=round(d_sharp, 6),
                n_predictions=len(indices),
                delta_vs_baseline=round(d_brier - d_half_brier, 6),
            ))

        return result

    def _compute_horizon_breakdown(
        self,
        predictions: list[dict],
        probs: np.ndarray,
        actuals: np.ndarray,
    ) -> list[HorizonMetrics]:
        """Compute metrics per forecast horizon."""
        horizons: dict[int, list[int]] = {}
        for i, p in enumerate(predictions):
            h = p.get("cutoff_days", 0)
            horizons.setdefault(h, []).append(i)

        results: list[HorizonMetrics] = []
        prev_brier: float | None = None

        for horizon in sorted(horizons.keys(), reverse=True):
            indices = horizons[horizon]
            idx_arr = np.array(indices)
            h_probs = probs[idx_arr]
            h_actuals = actuals[idx_arr]
            h_brier = self.compute_brier_score(h_probs, h_actuals)
            h_log = self.compute_log_score(h_probs, h_actuals)
            h_ece = self.compute_ece(h_probs, h_actuals)
            h_sharp = self.compute_sharpness(h_probs)

            improvement = 0.0
            if prev_brier is not None:
                improvement = prev_brier - h_brier  # positive = improvement

            results.append(HorizonMetrics(
                horizon_label=f"{horizon}d",
                brier_score=round(h_brier, 6),
                log_score=round(h_log, 6),
                calibration_error=round(h_ece, 6),
                sharpness=round(h_sharp, 6),
                n_predictions=len(indices),
                improvement_from_prior=round(improvement, 6),
            ))

            prev_brier = h_brier

        return results
