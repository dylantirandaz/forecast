"""Benchmark evaluation harness for scoring forecasts against benchmarks.

Supports offline evaluation for binary and continuous targets,
exact scoring, per-domain breakdowns, cost tracking, and
benchmark-ready export (ForecastBench, Metaculus).
"""

from __future__ import annotations

import logging
import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Sequence

import numpy as np
from scipy import stats as scipy_stats

from .calibration import CalibrationEngine
from .forecast_engine import ForecastResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------

@dataclass
class BenchmarkResult:
    """Aggregated evaluation metrics for a set of forecasts."""

    # Binary metrics (None when evaluating continuous targets)
    brier_score: float | None = None
    log_score: float | None = None
    calibration_error: float | None = None  # ECE
    sharpness: float | None = None
    resolution: float | None = None

    # Continuous metrics (None when evaluating binary targets)
    crps: float | None = None
    mae: float | None = None
    rmse: float | None = None
    coverage_50: float | None = None
    coverage_90: float | None = None

    # Universal
    n_forecasts: int = 0
    target_type: str = "binary"
    domain: str | None = None
    difficulty: str | None = None
    cost_total: float = 0.0
    cost_per_question: float = 0.0

    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class BenchmarkReport:
    """Full evaluation report with all metrics and breakdowns."""

    overall: BenchmarkResult
    by_domain: dict[str, BenchmarkResult] = field(default_factory=dict)
    by_difficulty: dict[str, BenchmarkResult] = field(default_factory=dict)
    by_target_type: dict[str, BenchmarkResult] = field(default_factory=dict)
    cost_summary: dict[str, float] = field(default_factory=dict)
    summary: str = ""
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


@dataclass
class ConfigComparison:
    """Side-by-side comparison of multiple forecast configurations."""

    config_results: dict[str, BenchmarkResult] = field(default_factory=dict)
    best_config: str = ""
    ranking: list[str] = field(default_factory=list)
    score_deltas: dict[str, dict[str, float]] = field(default_factory=dict)
    summary: str = ""


# ---------------------------------------------------------------------------
# Domain and difficulty classification
# ---------------------------------------------------------------------------

_DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "housing_supply": [
        "permit", "construction", "completions", "build", "zoning",
        "development", "units", "starts",
    ],
    "prices": [
        "rent", "price", "median", "asking", "market rate", "sale",
        "transaction", "valuation",
    ],
    "quality": [
        "distress", "violation", "maintenance", "hpd", "condition",
        "deterioration", "complaint",
    ],
    "affordability": [
        "affordable", "burden", "income", "voucher", "section 8",
        "hcv", "nycha", "subsidy",
    ],
    "homelessness": [
        "homeless", "shelter", "unsheltered", "dhs", "right to shelter",
    ],
    "policy": [
        "rgb", "freeze", "guideline", "regulation", "stabilized",
        "421a", "incentive", "tax",
    ],
}


def _classify_domain(question: dict[str, Any]) -> str:
    """Infer domain from question text."""
    text = (
        question.get("title", "") + " " +
        question.get("description", "") + " " +
        question.get("target_metric", "")
    ).lower()

    best_domain = "other"
    best_count = 0
    for domain, keywords in _DOMAIN_KEYWORDS.items():
        count = sum(1 for kw in keywords if kw in text)
        if count > best_count:
            best_count = count
            best_domain = domain

    return best_domain


def _classify_difficulty(question: dict[str, Any]) -> str:
    """Heuristic difficulty classification based on horizon and target type."""
    horizon = int(question.get("forecast_horizon_months", 12))
    target_type = question.get("target_type", "binary")

    if target_type == "continuous" and horizon > 24:
        return "hard"
    if target_type == "continuous" and horizon > 12:
        return "medium"
    if target_type == "binary" and horizon > 24:
        return "medium"
    if horizon <= 6:
        return "easy"
    return "medium"


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class BenchmarkHarness:
    """Evaluation harness for scoring forecasts against benchmarks.

    Supports offline evaluation for binary and continuous targets,
    exact scoring, per-domain breakdowns, cost tracking, and
    benchmark-ready export.
    """

    def __init__(self, cost_tracker: Any | None = None) -> None:
        self.cost_tracker = cost_tracker
        self.results: list[BenchmarkResult] = []
        self._calibration_engine = CalibrationEngine()

    # ------------------------------------------------------------------
    # Binary evaluation
    # ------------------------------------------------------------------

    def evaluate_binary(
        self,
        predictions: list[float],
        outcomes: list[int],
    ) -> BenchmarkResult:
        """Score binary predictions against known outcomes.

        Parameters
        ----------
        predictions:
            Predicted probabilities in [0, 1].
        outcomes:
            Binary outcomes (0 or 1).

        Returns
        -------
        BenchmarkResult
            Contains Brier score, log score, calibration error,
            sharpness, and resolution.
        """
        p = np.asarray(predictions, dtype=np.float64)
        o = np.asarray(outcomes, dtype=np.float64)

        if p.shape != o.shape or p.size == 0:
            raise ValueError(
                f"Shape mismatch or empty arrays: predictions {p.shape}, "
                f"outcomes {o.shape}"
            )

        brier_result = self._calibration_engine.compute_brier_score(p, o)
        log_score = self._calibration_engine.compute_log_score(p, o)
        sharpness = self._calibration_engine.compute_sharpness(p)
        resolution = self._calibration_engine.compute_resolution(p, o)

        # Expected Calibration Error (ECE): mean absolute gap per bin.
        cal_bins = self._calibration_engine.compute_calibration_curve(p, o)
        total_weight = 0.0
        ece = 0.0
        for b in cal_bins:
            if b.count > 0:
                ece += b.count * abs(b.mean_predicted - b.mean_observed)
                total_weight += b.count
        ece = ece / total_weight if total_weight > 0 else 0.0

        total_cost = self._get_total_cost()
        result = BenchmarkResult(
            brier_score=brier_result.brier_score,
            log_score=log_score,
            calibration_error=ece,
            sharpness=sharpness,
            resolution=resolution,
            n_forecasts=int(p.size),
            target_type="binary",
            cost_total=total_cost,
            cost_per_question=total_cost / p.size if p.size > 0 else 0.0,
        )
        self.results.append(result)
        return result

    # ------------------------------------------------------------------
    # Continuous evaluation
    # ------------------------------------------------------------------

    def evaluate_continuous(
        self,
        predictions: list[dict[str, float]],
        actuals: list[float],
    ) -> BenchmarkResult:
        """Score continuous predictions (Gaussian: mean, std) against actuals.

        Parameters
        ----------
        predictions:
            List of dicts with ``"mean"`` and ``"std"`` keys representing
            the predicted Gaussian distribution.
        actuals:
            True outcome values.

        Returns
        -------
        BenchmarkResult
            Contains CRPS, MAE, RMSE, and coverage at 50% and 90% levels.
        """
        if len(predictions) != len(actuals) or len(predictions) == 0:
            raise ValueError(
                f"Length mismatch or empty: {len(predictions)} predictions, "
                f"{len(actuals)} actuals"
            )

        crps_values: list[float] = []
        errors: list[float] = []
        sq_errors: list[float] = []

        for pred, actual in zip(predictions, actuals):
            mu = pred["mean"]
            sigma = max(pred.get("std", 1.0), 1e-9)
            crps_values.append(self.compute_crps(mu, sigma, actual))
            error = actual - mu
            errors.append(abs(error))
            sq_errors.append(error ** 2)

        coverage_50 = self.compute_coverage(predictions, actuals, level=0.5)
        coverage_90 = self.compute_coverage(predictions, actuals, level=0.9)

        total_cost = self._get_total_cost()
        n = len(predictions)
        result = BenchmarkResult(
            crps=float(np.mean(crps_values)),
            mae=float(np.mean(errors)),
            rmse=float(np.sqrt(np.mean(sq_errors))),
            coverage_50=coverage_50,
            coverage_90=coverage_90,
            n_forecasts=n,
            target_type="continuous",
            cost_total=total_cost,
            cost_per_question=total_cost / n if n > 0 else 0.0,
        )
        self.results.append(result)
        return result

    # ------------------------------------------------------------------
    # Domain and difficulty breakdowns
    # ------------------------------------------------------------------

    def evaluate_by_domain(
        self,
        results: list[ForecastResult],
        outcomes: dict[str, float],
        questions: dict[str, dict[str, Any]],
    ) -> dict[str, BenchmarkResult]:
        """Break down scores by domain (housing_supply, prices, etc.).

        Parameters
        ----------
        results:
            List of ``ForecastResult`` objects.
        outcomes:
            Mapping of question_id (str) to actual outcome value.
        questions:
            Mapping of question_id (str) to question dict.

        Returns
        -------
        dict[str, BenchmarkResult]
        """
        domain_groups: dict[str, tuple[list[float], list[float], str]] = {}

        for fr in results:
            qid = str(fr.question_id)
            if qid not in outcomes or qid not in questions:
                continue

            question = questions[qid]
            domain = _classify_domain(question)
            target_type = question.get("target_type", "binary")

            if domain not in domain_groups:
                domain_groups[domain] = ([], [], target_type)

            domain_groups[domain][0].append(fr.posterior_value)
            domain_groups[domain][1].append(outcomes[qid])

        result_map: dict[str, BenchmarkResult] = {}
        for domain, (preds, acts, tt) in domain_groups.items():
            if tt == "binary":
                br = self.evaluate_binary(
                    preds, [int(round(a)) for a in acts]
                )
            else:
                pred_dicts = [
                    {"mean": p, "std": max(abs(p) * 0.1, 0.01)}
                    for p in preds
                ]
                br = self.evaluate_continuous(pred_dicts, acts)
            br.domain = domain
            result_map[domain] = br

        return result_map

    def evaluate_by_difficulty(
        self,
        results: list[ForecastResult],
        outcomes: dict[str, float],
        questions: dict[str, dict[str, Any]],
    ) -> dict[str, BenchmarkResult]:
        """Break down scores by estimated difficulty.

        Parameters
        ----------
        results:
            List of ``ForecastResult`` objects.
        outcomes:
            Mapping of question_id (str) to actual outcome value.
        questions:
            Mapping of question_id (str) to question dict.

        Returns
        -------
        dict[str, BenchmarkResult]
        """
        difficulty_groups: dict[str, tuple[list[float], list[float], str]] = {}

        for fr in results:
            qid = str(fr.question_id)
            if qid not in outcomes or qid not in questions:
                continue

            question = questions[qid]
            difficulty = _classify_difficulty(question)
            target_type = question.get("target_type", "binary")

            if difficulty not in difficulty_groups:
                difficulty_groups[difficulty] = ([], [], target_type)

            difficulty_groups[difficulty][0].append(fr.posterior_value)
            difficulty_groups[difficulty][1].append(outcomes[qid])

        result_map: dict[str, BenchmarkResult] = {}
        for difficulty, (preds, acts, tt) in difficulty_groups.items():
            if tt == "binary":
                br = self.evaluate_binary(
                    preds, [int(round(a)) for a in acts]
                )
            else:
                pred_dicts = [
                    {"mean": p, "std": max(abs(p) * 0.1, 0.01)}
                    for p in preds
                ]
                br = self.evaluate_continuous(pred_dicts, acts)
            br.difficulty = difficulty
            result_map[difficulty] = br

        return result_map

    # ------------------------------------------------------------------
    # CRPS and coverage
    # ------------------------------------------------------------------

    @staticmethod
    def compute_crps(
        predicted_mean: float,
        predicted_std: float,
        actual: float,
    ) -> float:
        """Continuous Ranked Probability Score for Gaussian predictions.

        For a Gaussian N(mu, sigma^2), the closed-form CRPS is:

            CRPS = sigma * [ z*(2*Phi(z) - 1) + 2*phi(z) - 1/sqrt(pi) ]

        where z = (actual - mu) / sigma, Phi is the standard normal CDF,
        and phi is the standard normal PDF.

        Parameters
        ----------
        predicted_mean:
            Mean of the predicted Gaussian.
        predicted_std:
            Standard deviation of the predicted Gaussian.
        actual:
            The observed value.

        Returns
        -------
        float
            CRPS value (lower is better).
        """
        sigma = max(predicted_std, 1e-9)
        z = (actual - predicted_mean) / sigma
        phi_z = scipy_stats.norm.pdf(z)
        big_phi_z = scipy_stats.norm.cdf(z)
        return float(
            sigma * (z * (2.0 * big_phi_z - 1.0) + 2.0 * phi_z - 1.0 / math.sqrt(math.pi))
        )

    @staticmethod
    def compute_coverage(
        predictions: list[dict[str, float]] | Sequence[dict[str, float]],
        actuals: list[float] | Sequence[float],
        level: float = 0.9,
    ) -> float:
        """Fraction of actuals falling within prediction intervals.

        Prediction intervals are derived from the Gaussian parameters
        (mean, std) at the requested confidence level.

        Parameters
        ----------
        predictions:
            List of dicts with ``"mean"`` and ``"std"`` keys.
        actuals:
            True outcome values.
        level:
            Confidence level (e.g. 0.9 for 90% interval).

        Returns
        -------
        float
            Coverage fraction in [0, 1].
        """
        if len(predictions) == 0:
            return 0.0

        z = scipy_stats.norm.ppf((1.0 + level) / 2.0)
        in_interval = 0
        for pred, actual in zip(predictions, actuals):
            mu = pred["mean"]
            sigma = max(pred.get("std", 1.0), 1e-9)
            lower = mu - z * sigma
            upper = mu + z * sigma
            if lower <= actual <= upper:
                in_interval += 1

        return in_interval / len(predictions)

    # ------------------------------------------------------------------
    # Export for external benchmarks
    # ------------------------------------------------------------------

    def export_forecastbench(
        self,
        forecasts: list[ForecastResult],
        questions: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Format predictions for ForecastBench submission.

        Parameters
        ----------
        forecasts:
            List of ``ForecastResult`` objects.
        questions:
            Optional question metadata for enrichment.

        Returns
        -------
        dict
            Submission-ready dict with ``"predictions"`` list and
            ``"metadata"``.
        """
        predictions: list[dict[str, Any]] = []
        for fr in forecasts:
            qid = str(fr.question_id)
            target_type = (
                fr.decomposition.target_type
                if fr.decomposition
                else "binary"
            )
            entry: dict[str, Any] = {
                "question_id": qid,
                "forecast_run_id": str(fr.forecast_run_id),
                "timestamp": fr.created_at.isoformat(),
            }

            if target_type == "binary":
                entry["probability"] = round(
                    max(0.001, min(0.999, fr.posterior_value)), 4
                )
            else:
                entry["point_estimate"] = round(fr.posterior_value, 4)
                if fr.confidence_lower is not None:
                    entry["interval_lower"] = round(fr.confidence_lower, 4)
                    entry["interval_upper"] = round(fr.confidence_upper, 4)

            if questions and qid in questions:
                entry["question_title"] = questions[qid].get("title", "")
                entry["domain"] = _classify_domain(questions[qid])

            predictions.append(entry)

        return {
            "format": "forecastbench_v1",
            "model_name": "nyc_housing_forecast",
            "predictions": predictions,
            "metadata": {
                "n_forecasts": len(predictions),
                "export_timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

    def export_metaculus(
        self,
        forecasts: list[ForecastResult],
        questions: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Format predictions for Metaculus bot tournament submission.

        Parameters
        ----------
        forecasts:
            List of ``ForecastResult`` objects.
        questions:
            Optional question metadata for enrichment.

        Returns
        -------
        dict
            Submission-ready dict for Metaculus API.
        """
        submissions: list[dict[str, Any]] = []
        for fr in forecasts:
            qid = str(fr.question_id)
            target_type = (
                fr.decomposition.target_type
                if fr.decomposition
                else "binary"
            )

            entry: dict[str, Any] = {
                "question_id": qid,
            }

            if target_type == "binary":
                entry["prediction"] = round(
                    max(0.001, min(0.999, fr.posterior_value)), 4
                )
            else:
                # Metaculus continuous format: provide distribution via CDF
                # points at specified quantiles.
                mu = fr.posterior_value
                sigma = (
                    (fr.confidence_upper - fr.confidence_lower) / (2 * 1.96)
                    if fr.confidence_upper is not None
                    and fr.confidence_lower is not None
                    else max(abs(mu) * 0.1, 0.01)
                )
                quantiles = [0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99]
                entry["continuous_cdf"] = {
                    str(q): round(
                        float(scipy_stats.norm.ppf(q, loc=mu, scale=sigma)), 4
                    )
                    for q in quantiles
                }

            if questions and qid in questions:
                entry["question_title"] = questions[qid].get("title", "")

            entry["rationale"] = fr.rationale[:500] if fr.rationale else ""
            submissions.append(entry)

        return {
            "format": "metaculus_bot_v1",
            "model_name": "nyc_housing_forecast",
            "submissions": submissions,
            "metadata": {
                "n_submissions": len(submissions),
                "export_timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

    # ------------------------------------------------------------------
    # Report generation
    # ------------------------------------------------------------------

    def generate_report(
        self,
        results: list[BenchmarkResult],
    ) -> BenchmarkReport:
        """Full evaluation report with all metrics and cost summary.

        Parameters
        ----------
        results:
            List of ``BenchmarkResult`` objects (e.g. one per domain).

        Returns
        -------
        BenchmarkReport
        """
        if not results:
            return BenchmarkReport(
                overall=BenchmarkResult(n_forecasts=0),
                summary="No results to report.",
            )

        # Aggregate overall metrics (weighted by n_forecasts).
        total_n = sum(r.n_forecasts for r in results)
        total_cost = sum(r.cost_total for r in results)

        # Aggregate binary metrics.
        binary_results = [r for r in results if r.target_type == "binary"]
        continuous_results = [r for r in results if r.target_type == "continuous"]

        overall = BenchmarkResult(n_forecasts=total_n, cost_total=total_cost)
        overall.cost_per_question = total_cost / total_n if total_n > 0 else 0.0

        if binary_results:
            bn = sum(r.n_forecasts for r in binary_results)
            if bn > 0:
                overall.brier_score = sum(
                    r.brier_score * r.n_forecasts
                    for r in binary_results
                    if r.brier_score is not None
                ) / bn
                overall.log_score = sum(
                    r.log_score * r.n_forecasts
                    for r in binary_results
                    if r.log_score is not None
                ) / bn
                overall.calibration_error = sum(
                    r.calibration_error * r.n_forecasts
                    for r in binary_results
                    if r.calibration_error is not None
                ) / bn

        if continuous_results:
            cn = sum(r.n_forecasts for r in continuous_results)
            if cn > 0:
                overall.crps = sum(
                    r.crps * r.n_forecasts
                    for r in continuous_results
                    if r.crps is not None
                ) / cn
                overall.mae = sum(
                    r.mae * r.n_forecasts
                    for r in continuous_results
                    if r.mae is not None
                ) / cn
                overall.coverage_90 = sum(
                    r.coverage_90 * r.n_forecasts
                    for r in continuous_results
                    if r.coverage_90 is not None
                ) / cn

        # Build breakdowns.
        by_domain: dict[str, BenchmarkResult] = {}
        by_difficulty: dict[str, BenchmarkResult] = {}
        by_target_type: dict[str, BenchmarkResult] = {}

        for r in results:
            if r.domain:
                by_domain[r.domain] = r
            if r.difficulty:
                by_difficulty[r.difficulty] = r
            tt = r.target_type
            if tt not in by_target_type:
                by_target_type[tt] = r

        # Summary text.
        lines = [
            f"Benchmark Report ({total_n} forecasts)",
            f"  Total cost:     ${total_cost:.4f}",
            f"  Cost/question:  ${overall.cost_per_question:.4f}",
        ]
        if overall.brier_score is not None:
            lines.append(f"  Brier score:    {overall.brier_score:.4f}")
        if overall.log_score is not None:
            lines.append(f"  Log score:      {overall.log_score:.4f}")
        if overall.calibration_error is not None:
            lines.append(f"  ECE:            {overall.calibration_error:.4f}")
        if overall.crps is not None:
            lines.append(f"  CRPS:           {overall.crps:.4f}")
        if overall.mae is not None:
            lines.append(f"  MAE:            {overall.mae:.4f}")
        if overall.coverage_90 is not None:
            lines.append(f"  Coverage (90%): {overall.coverage_90:.1%}")
        if by_domain:
            lines.append("  Domains:")
            for d, r in by_domain.items():
                score = r.brier_score if r.brier_score is not None else r.crps
                lines.append(f"    {d}: {score:.4f} (n={r.n_forecasts})")

        return BenchmarkReport(
            overall=overall,
            by_domain=by_domain,
            by_difficulty=by_difficulty,
            by_target_type=by_target_type,
            cost_summary={
                "total": total_cost,
                "per_question": overall.cost_per_question,
                "n_forecasts": float(total_n),
            },
            summary="\n".join(lines),
        )

    # ------------------------------------------------------------------
    # Configuration comparison
    # ------------------------------------------------------------------

    def compare_configs(
        self,
        config_results: dict[str, list[BenchmarkResult]],
    ) -> ConfigComparison:
        """Compare multiple configurations side-by-side.

        Parameters
        ----------
        config_results:
            Mapping of config name to list of ``BenchmarkResult`` objects.

        Returns
        -------
        ConfigComparison
        """
        aggregated: dict[str, BenchmarkResult] = {}
        for name, result_list in config_results.items():
            report = self.generate_report(result_list)
            aggregated[name] = report.overall

        # Rank by primary metric: Brier for binary, CRPS for continuous.
        def _sort_key(item: tuple[str, BenchmarkResult]) -> float:
            r = item[1]
            if r.brier_score is not None:
                return r.brier_score
            if r.crps is not None:
                return r.crps
            if r.mae is not None:
                return r.mae
            return float("inf")

        ranked = sorted(aggregated.items(), key=_sort_key)
        ranking = [name for name, _ in ranked]
        best = ranking[0] if ranking else ""

        # Compute deltas from best config.
        best_result = aggregated.get(best)
        score_deltas: dict[str, dict[str, float]] = {}
        if best_result is not None:
            for name, r in aggregated.items():
                deltas: dict[str, float] = {}
                if r.brier_score is not None and best_result.brier_score is not None:
                    deltas["brier_delta"] = r.brier_score - best_result.brier_score
                if r.crps is not None and best_result.crps is not None:
                    deltas["crps_delta"] = r.crps - best_result.crps
                if r.cost_total > 0 and best_result.cost_total > 0:
                    deltas["cost_delta"] = r.cost_total - best_result.cost_total
                score_deltas[name] = deltas

        lines = ["Configuration Comparison:"]
        for name in ranking:
            r = aggregated[name]
            marker = " [BEST]" if name == best else ""
            score = r.brier_score if r.brier_score is not None else r.crps
            score_str = f"{score:.4f}" if score is not None else "N/A"
            lines.append(
                f"  {name}: score={score_str}, "
                f"cost=${r.cost_total:.4f}, "
                f"n={r.n_forecasts}{marker}"
            )

        return ConfigComparison(
            config_results=aggregated,
            best_config=best,
            ranking=ranking,
            score_deltas=score_deltas,
            summary="\n".join(lines),
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _get_total_cost(self) -> float:
        """Retrieve total cost from cost tracker, if available."""
        if self.cost_tracker is None:
            return 0.0
        if hasattr(self.cost_tracker, "total_cost"):
            return float(self.cost_tracker.total_cost)
        if hasattr(self.cost_tracker, "get_total_cost"):
            return float(self.cost_tracker.get_total_cost())
        return 0.0
