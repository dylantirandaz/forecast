"""Ablation runner for comparing forecast pipeline configurations.

Runs controlled experiments that systematically disable or modify
pipeline components to measure their contribution to forecast accuracy
and cost efficiency.
"""

from __future__ import annotations

import copy
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Sequence

import numpy as np

from .benchmark_harness import BenchmarkHarness, BenchmarkResult
from .forecast_engine import ForecastEngine, ForecastResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class AblationConfig:
    """Configuration for a single ablation experiment.

    Each flag controls whether a pipeline component is active.
    The runner modifies the forecast engine behaviour based on
    these flags before running predictions.
    """

    name: str
    description: str

    # Feature flags
    use_base_rates: bool = True
    use_evidence_scoring: bool = True
    use_recency_weighting: bool = True
    use_novelty_filter: bool = True
    use_calibration: bool = True

    # Calibration scope
    calibration_scope: str = "global"  # "global", "domain_specific", "target_specific"

    # Evidence weighting strategy
    evidence_weighting: str = "credibility"  # "uniform", "credibility"

    # Model tier selection
    model_tier: str = "A"  # "A", "B", "A+B"

    # Second pass on disagreement
    use_disagreement_second_pass: bool = False

    # Value-of-information gating
    use_voi_gating: bool = True

    # Rolling update vs static prior
    update_strategy: str = "incremental"  # "incremental", "static"

    # Cost control
    max_budget_per_question: float = 0.10

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for storage."""
        return {
            "name": self.name,
            "description": self.description,
            "use_base_rates": self.use_base_rates,
            "use_evidence_scoring": self.use_evidence_scoring,
            "use_recency_weighting": self.use_recency_weighting,
            "use_novelty_filter": self.use_novelty_filter,
            "use_calibration": self.use_calibration,
            "calibration_scope": self.calibration_scope,
            "evidence_weighting": self.evidence_weighting,
            "model_tier": self.model_tier,
            "use_disagreement_second_pass": self.use_disagreement_second_pass,
            "use_voi_gating": self.use_voi_gating,
            "update_strategy": self.update_strategy,
            "max_budget_per_question": self.max_budget_per_question,
        }


# ---------------------------------------------------------------------------
# Predefined ablation experiments (the canonical 10)
# ---------------------------------------------------------------------------

ABLATION_EXPERIMENTS: dict[str, AblationConfig] = {
    "1_no_base_rates": AblationConfig(
        name="No Base Rates",
        description="Forecast without historical base rates as anchors",
        use_base_rates=False,
    ),
    "2_one_shot_direct": AblationConfig(
        name="One-Shot Direct",
        description="Single LLM call without structured evidence pipeline",
        use_evidence_scoring=False,
        use_base_rates=False,
        model_tier="B",
    ),
    "3_raw_vs_calibrated": AblationConfig(
        name="Raw Posterior (No Calibration)",
        description="Skip calibration transform on outputs",
        use_calibration=False,
    ),
    "4_uniform_evidence": AblationConfig(
        name="Uniform Evidence Weights",
        description="All evidence weighted equally regardless of credibility",
        evidence_weighting="uniform",
    ),
    "5_no_recency": AblationConfig(
        name="No Recency Weighting",
        description="Don't decay evidence weight by age",
        use_recency_weighting=False,
    ),
    "6_no_novelty": AblationConfig(
        name="No Novelty Filter",
        description="Don't filter redundant/duplicate evidence",
        use_novelty_filter=False,
    ),
    "7_disagreement_pass": AblationConfig(
        name="Disagreement Second Pass",
        description="Run Tier B model when Tier A confidence is low",
        use_disagreement_second_pass=True,
        model_tier="A+B",
    ),
    "8_always_deep_research": AblationConfig(
        name="Always Deep Research",
        description="Always use full Tier B pipeline (no VoI gating)",
        use_voi_gating=False,
        model_tier="B",
    ),
    "9_domain_calibration": AblationConfig(
        name="Domain-Specific Calibration",
        description="Calibrate per-domain instead of globally",
        calibration_scope="domain_specific",
    ),
    "10_static_prior": AblationConfig(
        name="Static Prior (No Rolling Updates)",
        description="Use base rate only, never update with new evidence",
        update_strategy="static",
    ),
}


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------

@dataclass
class ExperimentResult:
    """Results from a single ablation experiment run."""

    experiment_id: uuid.UUID
    config: AblationConfig
    forecasts: list[ForecastResult] = field(default_factory=list)
    benchmark: BenchmarkResult | None = None
    cost_total: float = 0.0
    cost_per_question: float = 0.0
    n_questions: int = 0
    duration_seconds: float = 0.0
    started_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    completed_at: datetime | None = None
    errors: list[str] = field(default_factory=list)


@dataclass
class AblationComparison:
    """Comparison of ablation experiment results."""

    baseline_name: str
    experiment_results: dict[str, ExperimentResult] = field(default_factory=dict)
    score_deltas: dict[str, dict[str, float]] = field(default_factory=dict)
    cost_deltas: dict[str, float] = field(default_factory=dict)
    best_config: str = ""
    best_budget_config: str = ""
    ranking: list[str] = field(default_factory=list)
    summary: str = ""
    chart_data: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Pipeline modifier
# ---------------------------------------------------------------------------

class _PipelineModifier:
    """Applies ablation config flags to modify pipeline behaviour.

    This class mutates the evidence items and engine parameters to
    implement each ablation condition without requiring changes to
    the core engine code.
    """

    @staticmethod
    def prepare_evidence(
        evidence_items: Sequence[dict[str, Any]],
        config: AblationConfig,
    ) -> list[dict[str, Any]]:
        """Filter and modify evidence items according to ablation config.

        Parameters
        ----------
        evidence_items:
            Raw evidence items.
        config:
            The ablation configuration flags.

        Returns
        -------
        list[dict[str, Any]]
            Modified evidence items ready for the pipeline.
        """
        items = [dict(ev) for ev in evidence_items]

        if not config.use_evidence_scoring:
            # One-shot mode: skip all evidence
            return []

        if config.evidence_weighting == "uniform":
            # Override source types to remove credibility differentiation.
            for item in items:
                item["source_type"] = "uniform_source"
                item["_uniform_weight"] = True

        if not config.use_recency_weighting:
            # Remove date information so recency decay cannot fire.
            for item in items:
                item["_skip_recency"] = True

        if not config.use_novelty_filter:
            # Mark items to skip novelty/redundancy filtering.
            for item in items:
                item["_skip_novelty"] = True

        return items

    @staticmethod
    def prepare_historical_data(
        historical_data: Sequence[float],
        config: AblationConfig,
    ) -> list[float]:
        """Modify historical data based on ablation config.

        Parameters
        ----------
        historical_data:
            Original time series.
        config:
            The ablation configuration flags.

        Returns
        -------
        list[float]
            Modified time series.
        """
        data = list(historical_data)

        if not config.use_base_rates:
            # Without base rates, provide a flat uninformative prior.
            # Return a minimal series centered at 0.5 for binary or
            # the mean for continuous.
            if data:
                mean_val = float(np.mean(data))
                return [mean_val, mean_val]
            return [0.5, 0.5]

        return data

    @staticmethod
    def apply_post_processing(
        result: ForecastResult,
        config: AblationConfig,
        calibration_transform: Any | None = None,
    ) -> ForecastResult:
        """Apply post-processing modifications based on config.

        Parameters
        ----------
        result:
            Raw forecast result.
        config:
            The ablation configuration flags.
        calibration_transform:
            Optional calibration transform function.

        Returns
        -------
        ForecastResult
            Modified result.
        """
        if config.update_strategy == "static":
            # Static prior: revert posterior to the prior value.
            result.posterior_value = result.prior_value
            result.rationale += " [ABLATION: static prior, no evidence updates applied]"

        if config.use_calibration and calibration_transform is not None:
            # Apply calibration transform.
            target_type = (
                result.decomposition.target_type
                if result.decomposition
                else "binary"
            )
            if target_type == "binary":
                calibrated = calibration_transform(
                    np.array([result.posterior_value])
                )
                result.posterior_value = float(
                    np.clip(calibrated[0], 0.001, 0.999)
                )

        if not config.use_calibration:
            result.rationale += " [ABLATION: no calibration applied]"

        return result


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class AblationRunner:
    """Runs ablation experiments comparing different forecast configurations.

    Each experiment applies a specific ``AblationConfig`` to modify the
    forecast pipeline and then evaluates results against known outcomes.
    """

    def __init__(
        self,
        forecast_engine: ForecastEngine,
        orchestrator: Any | None = None,
        benchmark_harness: BenchmarkHarness | None = None,
        cost_tracker: Any | None = None,
    ) -> None:
        self.forecast_engine = forecast_engine
        self.orchestrator = orchestrator
        self.benchmark_harness = benchmark_harness or BenchmarkHarness(
            cost_tracker=cost_tracker
        )
        self.cost_tracker = cost_tracker
        self._modifier = _PipelineModifier()
        self._calibration_transforms: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Single experiment
    # ------------------------------------------------------------------

    async def run_experiment(
        self,
        config: AblationConfig,
        questions: list[dict[str, Any]],
        scenarios: list[dict[str, Any]],
        historical_data: dict[str, Sequence[float]] | None = None,
        evidence_items: dict[str, Sequence[dict[str, Any]]] | None = None,
        outcomes: dict[str, float] | None = None,
    ) -> ExperimentResult:
        """Run a single ablation configuration across all questions.

        Parameters
        ----------
        config:
            The ablation configuration to test.
        questions:
            List of question dicts. Each must have an ``"id"`` key.
        scenarios:
            List of scenario dicts. May be empty for no-scenario runs.
        historical_data:
            Optional mapping of question_id to time series. If not
            provided, a default flat series is used.
        evidence_items:
            Optional mapping of question_id to evidence item lists.
        outcomes:
            Optional mapping of question_id to actual outcome values
            for scoring.

        Returns
        -------
        ExperimentResult
        """
        experiment_id = uuid.uuid4()
        started_at = datetime.now(timezone.utc)

        logger.info(
            "Starting ablation experiment '%s' (id=%s) on %d questions.",
            config.name,
            experiment_id,
            len(questions),
        )

        historical_data = historical_data or {}
        evidence_items = evidence_items or {}
        outcomes = outcomes or {}

        forecasts: list[ForecastResult] = []
        errors: list[str] = []
        cost_before = self._get_current_cost()

        for question in questions:
            qid = str(question.get("id", uuid.uuid4()))

            # Get data for this question.
            q_data = list(historical_data.get(qid, [0.5, 0.5, 0.5]))
            q_evidence = list(evidence_items.get(qid, []))
            scenario = scenarios[0] if scenarios else None

            try:
                # Apply ablation modifications.
                modified_data = self._modifier.prepare_historical_data(
                    q_data, config
                )
                modified_evidence = self._modifier.prepare_evidence(
                    q_evidence, config
                )

                # Check budget constraint.
                current_cost = self._get_current_cost() - cost_before
                per_q_cost = (
                    current_cost / max(len(forecasts), 1)
                    if forecasts
                    else 0.0
                )
                if per_q_cost > config.max_budget_per_question:
                    logger.warning(
                        "Budget exceeded for experiment '%s': "
                        "$%.4f/question > $%.4f limit. Skipping remaining.",
                        config.name,
                        per_q_cost,
                        config.max_budget_per_question,
                    )
                    errors.append(
                        f"Budget exceeded at question {qid}: "
                        f"${per_q_cost:.4f}/q > ${config.max_budget_per_question:.4f}"
                    )
                    break

                # Run the forecast.
                result = self.forecast_engine.create_forecast(
                    question=question,
                    historical_data=modified_data,
                    evidence_items=modified_evidence,
                    scenario=scenario,
                )

                # Apply post-processing (calibration, static prior, etc.).
                cal_transform = self._calibration_transforms.get(
                    config.calibration_scope
                )
                result = self._modifier.apply_post_processing(
                    result, config, cal_transform
                )

                # Disagreement second pass: if enabled and we have an
                # orchestrator, re-run with Tier B when confidence is low.
                if config.use_disagreement_second_pass and self.orchestrator:
                    result = await self._run_disagreement_pass(
                        result, question, modified_data,
                        modified_evidence, scenario, config,
                    )

                forecasts.append(result)

            except Exception as exc:
                error_msg = (
                    f"Error forecasting question {qid} in "
                    f"experiment '{config.name}': {exc}"
                )
                logger.error(error_msg)
                errors.append(error_msg)

        # Score the forecasts if outcomes are available.
        benchmark = None
        if outcomes and forecasts:
            benchmark = self._score_forecasts(forecasts, outcomes, questions)

        cost_after = self._get_current_cost()
        total_cost = cost_after - cost_before
        completed_at = datetime.now(timezone.utc)
        duration = (completed_at - started_at).total_seconds()

        experiment_result = ExperimentResult(
            experiment_id=experiment_id,
            config=config,
            forecasts=forecasts,
            benchmark=benchmark,
            cost_total=total_cost,
            cost_per_question=(
                total_cost / len(forecasts) if forecasts else 0.0
            ),
            n_questions=len(forecasts),
            duration_seconds=duration,
            started_at=started_at,
            completed_at=completed_at,
            errors=errors,
        )

        logger.info(
            "Experiment '%s' complete: %d forecasts, cost=$%.4f, "
            "duration=%.1fs, errors=%d",
            config.name,
            len(forecasts),
            total_cost,
            duration,
            len(errors),
        )

        return experiment_result

    # ------------------------------------------------------------------
    # Run all ablations
    # ------------------------------------------------------------------

    async def run_all_ablations(
        self,
        questions: list[dict[str, Any]],
        scenarios: list[dict[str, Any]],
        configs: dict[str, AblationConfig] | None = None,
        historical_data: dict[str, Sequence[float]] | None = None,
        evidence_items: dict[str, Sequence[dict[str, Any]]] | None = None,
        outcomes: dict[str, float] | None = None,
    ) -> dict[str, ExperimentResult]:
        """Run all predefined ablation experiments.

        Parameters
        ----------
        questions:
            List of question dicts.
        scenarios:
            List of scenario dicts.
        configs:
            Optional custom config set; defaults to ``ABLATION_EXPERIMENTS``.
        historical_data:
            Optional per-question time series.
        evidence_items:
            Optional per-question evidence.
        outcomes:
            Optional per-question outcomes for scoring.

        Returns
        -------
        dict[str, ExperimentResult]
        """
        if configs is None:
            configs = ABLATION_EXPERIMENTS

        results: dict[str, ExperimentResult] = {}
        for name, config in configs.items():
            logger.info("Running ablation: %s", name)
            results[name] = await self.run_experiment(
                config=config,
                questions=questions,
                scenarios=scenarios,
                historical_data=historical_data,
                evidence_items=evidence_items,
                outcomes=outcomes,
            )

        return results

    # ------------------------------------------------------------------
    # Comparison and analysis
    # ------------------------------------------------------------------

    def compare_results(
        self,
        results: dict[str, ExperimentResult],
        baseline_name: str = "baseline",
    ) -> AblationComparison:
        """Compare ablation results: score deltas, cost deltas, best config.

        Parameters
        ----------
        results:
            Mapping of experiment name to ``ExperimentResult``.
        baseline_name:
            Name of the baseline experiment for delta computation.
            If not present, uses the best-scoring experiment.

        Returns
        -------
        AblationComparison
        """
        if not results:
            return AblationComparison(
                baseline_name=baseline_name,
                summary="No results to compare.",
            )

        # Determine baseline.
        if baseline_name not in results:
            baseline_name = self._find_best(results, "brier")

        baseline = results.get(baseline_name)
        baseline_score = self._primary_score(baseline) if baseline else None
        baseline_cost = baseline.cost_total if baseline else 0.0

        # Compute deltas from baseline.
        score_deltas: dict[str, dict[str, float]] = {}
        cost_deltas: dict[str, float] = {}

        for name, exp in results.items():
            exp_score = self._primary_score(exp)
            deltas: dict[str, float] = {}

            if exp_score is not None and baseline_score is not None:
                deltas["score_delta"] = exp_score - baseline_score
                if baseline_score > 0:
                    deltas["score_pct_change"] = (
                        (exp_score - baseline_score) / baseline_score * 100.0
                    )

            if exp.benchmark and baseline and baseline.benchmark:
                if (
                    exp.benchmark.brier_score is not None
                    and baseline.benchmark.brier_score is not None
                ):
                    deltas["brier_delta"] = (
                        exp.benchmark.brier_score - baseline.benchmark.brier_score
                    )
                if (
                    exp.benchmark.crps is not None
                    and baseline.benchmark.crps is not None
                ):
                    deltas["crps_delta"] = (
                        exp.benchmark.crps - baseline.benchmark.crps
                    )

            score_deltas[name] = deltas
            cost_deltas[name] = exp.cost_total - baseline_cost

        # Rank by primary score (lower is better).
        ranking = sorted(
            results.keys(),
            key=lambda n: self._primary_score(results[n]) or float("inf"),
        )

        best_config = ranking[0] if ranking else ""

        # Best under budget: find the best-scoring experiment that stays
        # under the median cost.
        costs = [e.cost_per_question for e in results.values() if e.cost_per_question > 0]
        median_cost = float(np.median(costs)) if costs else float("inf")
        budget_candidates = [
            n for n in ranking
            if results[n].cost_per_question <= median_cost or results[n].cost_per_question == 0.0
        ]
        best_budget = budget_candidates[0] if budget_candidates else best_config

        # Chart data for visualisation.
        chart_data = self._build_chart_data(results, ranking)

        # Summary.
        lines = [
            f"Ablation Comparison (baseline='{baseline_name}', {len(results)} experiments)",
            "",
        ]
        for name in ranking:
            exp = results[name]
            score = self._primary_score(exp)
            score_str = f"{score:.4f}" if score is not None else "N/A"
            delta = score_deltas.get(name, {}).get("score_delta")
            delta_str = f" ({delta:+.4f})" if delta is not None else ""
            marker = ""
            if name == best_config:
                marker = " [BEST]"
            elif name == best_budget:
                marker = " [BEST-BUDGET]"
            lines.append(
                f"  {name}: score={score_str}{delta_str}, "
                f"cost=${exp.cost_total:.4f}, "
                f"n={exp.n_questions}{marker}"
            )

        lines.append("")
        lines.append(f"Best overall: {best_config}")
        lines.append(f"Best under budget: {best_budget}")

        return AblationComparison(
            baseline_name=baseline_name,
            experiment_results=results,
            score_deltas=score_deltas,
            cost_deltas=cost_deltas,
            best_config=best_config,
            best_budget_config=best_budget,
            ranking=ranking,
            summary="\n".join(lines),
            chart_data=chart_data,
        )

    def identify_best_config(
        self,
        results: dict[str, ExperimentResult],
        optimize_for: str = "brier",
        budget_constraint: float | None = None,
    ) -> str:
        """Find the best configuration, optionally under budget constraint.

        Parameters
        ----------
        results:
            Mapping of experiment name to ``ExperimentResult``.
        optimize_for:
            Metric to optimise: ``"brier"``, ``"crps"``, ``"mae"``,
            ``"log_score"``, or ``"cost_adjusted"`` (score / cost).
        budget_constraint:
            Maximum cost per question. If set, only experiments
            within budget are considered.

        Returns
        -------
        str
            Name of the best configuration.
        """
        candidates = dict(results)

        # Apply budget filter.
        if budget_constraint is not None:
            candidates = {
                name: exp
                for name, exp in candidates.items()
                if exp.cost_per_question <= budget_constraint
                or exp.cost_per_question == 0.0
            }

        if not candidates:
            logger.warning(
                "No experiments within budget $%.4f/question.",
                budget_constraint or 0.0,
            )
            return self._find_best(results, optimize_for)

        return self._find_best(candidates, optimize_for)

    def generate_ablation_report(
        self,
        comparison: AblationComparison,
    ) -> dict[str, Any]:
        """Generate a full report with tables and chart data.

        Parameters
        ----------
        comparison:
            An ``AblationComparison`` from ``compare_results``.

        Returns
        -------
        dict
            Report with ``"summary"``, ``"table"``, ``"chart_data"``,
            and ``"recommendations"``.
        """
        table_rows: list[dict[str, Any]] = []
        for name in comparison.ranking:
            exp = comparison.experiment_results.get(name)
            if exp is None:
                continue

            row: dict[str, Any] = {
                "experiment": name,
                "config_name": exp.config.name,
                "n_questions": exp.n_questions,
                "cost_total": round(exp.cost_total, 4),
                "cost_per_question": round(exp.cost_per_question, 4),
                "duration_seconds": round(exp.duration_seconds, 1),
                "errors": len(exp.errors),
            }

            if exp.benchmark:
                row["brier_score"] = (
                    round(exp.benchmark.brier_score, 4)
                    if exp.benchmark.brier_score is not None
                    else None
                )
                row["log_score"] = (
                    round(exp.benchmark.log_score, 4)
                    if exp.benchmark.log_score is not None
                    else None
                )
                row["crps"] = (
                    round(exp.benchmark.crps, 4)
                    if exp.benchmark.crps is not None
                    else None
                )
                row["mae"] = (
                    round(exp.benchmark.mae, 4)
                    if exp.benchmark.mae is not None
                    else None
                )
                row["coverage_90"] = (
                    round(exp.benchmark.coverage_90, 4)
                    if exp.benchmark.coverage_90 is not None
                    else None
                )

            deltas = comparison.score_deltas.get(name, {})
            row["score_delta"] = deltas.get("score_delta")
            row["score_pct_change"] = deltas.get("score_pct_change")
            row["cost_delta"] = comparison.cost_deltas.get(name, 0.0)

            table_rows.append(row)

        # Generate recommendations.
        recommendations: list[str] = []
        if comparison.best_config:
            best_exp = comparison.experiment_results.get(comparison.best_config)
            if best_exp:
                recommendations.append(
                    f"Best overall config: '{comparison.best_config}' "
                    f"({best_exp.config.description})"
                )

        if (
            comparison.best_budget_config
            and comparison.best_budget_config != comparison.best_config
        ):
            budget_exp = comparison.experiment_results.get(
                comparison.best_budget_config
            )
            if budget_exp:
                recommendations.append(
                    f"Best budget-efficient config: "
                    f"'{comparison.best_budget_config}' "
                    f"(${budget_exp.cost_per_question:.4f}/question)"
                )

        # Identify which components matter most (largest negative delta
        # when removed).
        impactful: list[tuple[str, float]] = []
        for name, deltas in comparison.score_deltas.items():
            sd = deltas.get("score_delta")
            if sd is not None and sd > 0:
                impactful.append((name, sd))
        impactful.sort(key=lambda x: x[1], reverse=True)
        if impactful:
            recommendations.append(
                "Most impactful components (removing them hurts most):"
            )
            for name, delta in impactful[:3]:
                recommendations.append(f"  - {name}: +{delta:.4f} score degradation")

        return {
            "summary": comparison.summary,
            "table": table_rows,
            "chart_data": comparison.chart_data,
            "recommendations": recommendations,
            "best_config": comparison.best_config,
            "best_budget_config": comparison.best_budget_config,
            "n_experiments": len(comparison.experiment_results),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Calibration transform management
    # ------------------------------------------------------------------

    def register_calibration_transform(
        self,
        scope: str,
        transform: Any,
    ) -> None:
        """Register a calibration transform for a given scope.

        Parameters
        ----------
        scope:
            ``"global"``, ``"domain_specific"``, or a specific domain name.
        transform:
            A callable that takes a numpy array of predictions and
            returns recalibrated predictions.
        """
        self._calibration_transforms[scope] = transform

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _run_disagreement_pass(
        self,
        first_result: ForecastResult,
        question: dict[str, Any],
        historical_data: Sequence[float],
        evidence_items: Sequence[dict[str, Any]],
        scenario: dict[str, Any] | None,
        config: AblationConfig,
    ) -> ForecastResult:
        """Run a second-pass Tier B forecast when confidence is low.

        If the confidence interval width exceeds 40% of the posterior
        value (for continuous) or the probability is between 0.3 and 0.7
        (for binary), re-run with modified parameters and average.
        """
        target_type = (
            first_result.decomposition.target_type
            if first_result.decomposition
            else "binary"
        )

        needs_second_pass = False
        if target_type == "binary":
            p = first_result.posterior_value
            needs_second_pass = 0.3 < p < 0.7
        else:
            if (
                first_result.confidence_lower is not None
                and first_result.confidence_upper is not None
            ):
                width = first_result.confidence_upper - first_result.confidence_lower
                needs_second_pass = (
                    width > 0.4 * abs(first_result.posterior_value)
                    if first_result.posterior_value != 0
                    else width > 1.0
                )

        if not needs_second_pass:
            return first_result

        logger.info(
            "Disagreement detected for question %s, running second pass.",
            first_result.question_id,
        )

        # Second pass: re-run with the same engine (simulating Tier B).
        try:
            second_result = self.forecast_engine.create_forecast(
                question=question,
                historical_data=list(historical_data),
                evidence_items=list(evidence_items),
                scenario=scenario,
            )

            # Average the two posteriors.
            averaged = (
                first_result.posterior_value + second_result.posterior_value
            ) / 2.0
            if target_type == "binary":
                averaged = max(0.001, min(0.999, averaged))

            first_result.posterior_value = averaged
            first_result.rationale += (
                f" [ABLATION: disagreement second pass, "
                f"Tier A={first_result.posterior_value:.4f}, "
                f"Tier B={second_result.posterior_value:.4f}, "
                f"averaged={averaged:.4f}]"
            )
        except Exception as exc:
            logger.warning("Second pass failed: %s", exc)

        return first_result

    def _score_forecasts(
        self,
        forecasts: list[ForecastResult],
        outcomes: dict[str, float],
        questions: list[dict[str, Any]],
    ) -> BenchmarkResult | None:
        """Score a list of forecasts against known outcomes."""
        binary_preds: list[float] = []
        binary_outcomes: list[int] = []
        continuous_preds: list[dict[str, float]] = []
        continuous_actuals: list[float] = []

        for fr in forecasts:
            qid = str(fr.question_id)
            if qid not in outcomes:
                continue

            target_type = (
                fr.decomposition.target_type
                if fr.decomposition
                else "binary"
            )

            if target_type == "binary":
                binary_preds.append(fr.posterior_value)
                binary_outcomes.append(int(round(outcomes[qid])))
            else:
                sigma = (
                    (fr.confidence_upper - fr.confidence_lower) / (2 * 1.96)
                    if fr.confidence_upper is not None
                    and fr.confidence_lower is not None
                    else max(abs(fr.posterior_value) * 0.1, 0.01)
                )
                continuous_preds.append({
                    "mean": fr.posterior_value,
                    "std": sigma,
                })
                continuous_actuals.append(outcomes[qid])

        if binary_preds:
            return self.benchmark_harness.evaluate_binary(
                binary_preds, binary_outcomes
            )
        if continuous_preds:
            return self.benchmark_harness.evaluate_continuous(
                continuous_preds, continuous_actuals
            )
        return None

    def _find_best(
        self,
        results: dict[str, ExperimentResult],
        metric: str,
    ) -> str:
        """Find the best experiment by a given metric (lower is better)."""
        def _get_score(exp: ExperimentResult) -> float:
            if exp.benchmark is None:
                return float("inf")
            if metric == "brier" and exp.benchmark.brier_score is not None:
                return exp.benchmark.brier_score
            if metric == "crps" and exp.benchmark.crps is not None:
                return exp.benchmark.crps
            if metric == "mae" and exp.benchmark.mae is not None:
                return exp.benchmark.mae
            if metric == "log_score" and exp.benchmark.log_score is not None:
                return exp.benchmark.log_score
            if metric == "cost_adjusted":
                score = (
                    exp.benchmark.brier_score
                    or exp.benchmark.crps
                    or exp.benchmark.mae
                )
                if score is not None and exp.cost_per_question > 0:
                    return score * (1.0 + exp.cost_per_question)
                if score is not None:
                    return score
            # Fallback: try any available score.
            if exp.benchmark.brier_score is not None:
                return exp.benchmark.brier_score
            if exp.benchmark.crps is not None:
                return exp.benchmark.crps
            return float("inf")

        ranked = sorted(results.items(), key=lambda x: _get_score(x[1]))
        return ranked[0][0] if ranked else ""

    @staticmethod
    def _primary_score(exp: ExperimentResult | None) -> float | None:
        """Extract the primary score from an experiment result."""
        if exp is None or exp.benchmark is None:
            return None
        if exp.benchmark.brier_score is not None:
            return exp.benchmark.brier_score
        if exp.benchmark.crps is not None:
            return exp.benchmark.crps
        if exp.benchmark.mae is not None:
            return exp.benchmark.mae
        return None

    @staticmethod
    def _build_chart_data(
        results: dict[str, ExperimentResult],
        ranking: list[str],
    ) -> dict[str, Any]:
        """Build chart-ready data for visualisation."""
        labels: list[str] = []
        scores: list[float | None] = []
        costs: list[float] = []
        n_questions: list[int] = []

        for name in ranking:
            exp = results.get(name)
            if exp is None:
                continue
            labels.append(exp.config.name)
            if exp.benchmark:
                score = (
                    exp.benchmark.brier_score
                    or exp.benchmark.crps
                    or exp.benchmark.mae
                )
                scores.append(score)
            else:
                scores.append(None)
            costs.append(exp.cost_total)
            n_questions.append(exp.n_questions)

        return {
            "labels": labels,
            "scores": scores,
            "costs": costs,
            "n_questions": n_questions,
            "score_metric": "brier_score",
        }

    def _get_current_cost(self) -> float:
        """Retrieve current cumulative cost from cost tracker."""
        if self.cost_tracker is None:
            return 0.0
        if hasattr(self.cost_tracker, "total_cost"):
            return float(self.cost_tracker.total_cost)
        if hasattr(self.cost_tracker, "get_total_cost"):
            return float(self.cost_tracker.get_total_cost())
        return 0.0
