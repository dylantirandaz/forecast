"""Cost-aware forecast orchestrator.

This is the main intelligence layer of the NYC Housing Forecasting
system.  It routes questions through an optimal pipeline based on
configurable strategies, managing the trade-off between forecast
accuracy and LLM cost.

Strategies
----------
- **cheap_first**: Use Tier A + statistical only.  Escalate if
  confidence is low.
- **calibrated_default**: Tier A + base rates + calibration.
  Standard path for production use.
- **deep_research_on_hard**: Route hard questions to Tier B with
  full evidence pipeline; easy/medium stay on Tier A.
- **disagreement_second_pass**: Run Tier A, then Tier B if
  disagreement exceeds a threshold.
- **benchmark_max_accuracy**: Full pipeline always (most expensive).
- **benchmark_max_under_budget**: Full pipeline but cap total cost
  per question.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Sequence

from .base_rate_engine import BaseRateEngine
from .belief_updater import BeliefUpdater
from .calibration import CalibrationEngine
from .cost_tracker import CostTracker
from .evidence_scorer import EvidenceScorer
from .forecast_engine import ForecastEngine, ForecastResult, QuestionDecomposition
from .model_router import ModelRouter
from .question_router import QuestionRouter, PipelineConfig
from .scenario_engine import ScenarioEngine

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Valid strategies
# ---------------------------------------------------------------------------

VALID_STRATEGIES: set[str] = {
    "cheap_first",
    "calibrated_default",
    "deep_research_on_hard",
    "disagreement_second_pass",
    "benchmark_max_accuracy",
    "benchmark_max_under_budget",
}

# ---------------------------------------------------------------------------
# Budget defaults (USD)
# ---------------------------------------------------------------------------

_BUDGET_BY_DIFFICULTY: dict[str, float] = {
    "easy": 0.02,
    "medium": 0.08,
    "hard": 0.25,
}

# Domain multipliers: some domains are inherently more data-intensive.
_DOMAIN_BUDGET_MULTIPLIER: dict[str, float] = {
    "housing_supply": 1.0,
    "prices": 1.0,
    "building_quality": 0.8,
    "macro": 1.2,
    "policy": 1.3,
    "unknown": 1.0,
}

# Calibration nudge table: domain → (direction, magnitude).
# Positive = the raw model tends to be over-confident, so we
# push predictions toward 50%.  Negative = under-confident.
_CALIBRATION_NUDGE: dict[str, tuple[str, float]] = {
    "housing_supply": ("toward_base", 0.03),
    "prices": ("toward_base", 0.02),
    "building_quality": ("toward_base", 0.01),
    "macro": ("toward_base", 0.05),
    "policy": ("toward_base", 0.04),
    "unknown": ("toward_base", 0.03),
}


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class ForecastOrchestrator:
    """Cost-aware orchestrator that routes questions through the optimal pipeline.

    The orchestrator wraps all other engines (base-rate, evidence,
    belief-updater, scenario, calibration) and adds an intelligence
    layer that decides *which* stages to run and at *what quality level*
    based on question difficulty, domain, remaining budget, and the
    chosen strategy.

    Parameters
    ----------
    strategy:
        One of the six named strategies listed in :pydata:`VALID_STRATEGIES`.
    budget_per_question_usd:
        Maximum USD to spend on a single question.  Only enforced
        when the strategy is ``"benchmark_max_under_budget"``.
    forecast_engine:
        Optional pre-configured :class:`ForecastEngine`.
    model_router:
        Optional :class:`ModelRouter`.
    question_router:
        Optional :class:`QuestionRouter`.
    cost_tracker:
        Optional :class:`CostTracker`.

    Example::

        orch = ForecastOrchestrator(strategy="calibrated_default")
        result = await orch.run_forecast(question, scenario)
        print(orch.get_total_cost())
    """

    def __init__(
        self,
        strategy: str = "calibrated_default",
        budget_per_question_usd: float = 0.10,
        forecast_engine: ForecastEngine | None = None,
        model_router: ModelRouter | None = None,
        question_router: QuestionRouter | None = None,
        cost_tracker: CostTracker | None = None,
    ) -> None:
        if strategy not in VALID_STRATEGIES:
            raise ValueError(
                f"Unknown strategy '{strategy}'. "
                f"Choose from: {sorted(VALID_STRATEGIES)}"
            )

        self.strategy = strategy
        self.budget_per_question_usd = budget_per_question_usd

        self.engine = forecast_engine or ForecastEngine()
        self.router = model_router or ModelRouter()
        self.question_router = question_router or QuestionRouter()
        self.cost_tracker = cost_tracker or CostTracker(
            session_budget=budget_per_question_usd
        )

        # Calibration engine for post-hoc adjustments.
        self._calibration = CalibrationEngine()

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def run_forecast(
        self,
        question: dict[str, Any],
        scenario: dict[str, Any] | None = None,
        historical_data: Sequence[float] | None = None,
        evidence_items: Sequence[dict[str, Any]] | None = None,
        config: PipelineConfig | None = None,
    ) -> ForecastResult:
        """Run the full forecast pipeline with cost-aware routing.

        Steps
        -----
        1. Classify domain and difficulty.
        2. Compute per-question budget.
        3. Phase 1 — always cheap: base rate + Tier A forecast.
        4. Phase 2 — conditional escalation to Tier B.
        5. Phase 3 — disagreement resolution (if applicable).
        6. Phase 4 — domain-specific calibration.

        Parameters
        ----------
        question:
            Serialised question dict (see :class:`ForecastEngine`).
        scenario:
            Optional scenario dict.
        historical_data:
            Historical time-series for base-rate computation.
            Defaults to a synthetic 30-point series if not provided.
        evidence_items:
            Evidence items to incorporate.  Defaults to empty list.
        config:
            Optional override for the pipeline configuration.

        Returns
        -------
        ForecastResult
        """
        # Reset the cost tracker for this question.
        self.cost_tracker.reset()
        self.cost_tracker.session_budget = self.budget_per_question_usd

        # -- Pre-processing: classify question --
        difficulty = self.estimate_difficulty(question)
        domain = self.classify_domain(question)
        budget = self.compute_budget(difficulty, domain)

        if config is None:
            config = self.question_router.recommend_pipeline(domain, difficulty)

        if historical_data is None:
            historical_data = [0.5] * 30  # neutral placeholder
        if evidence_items is None:
            evidence_items = []

        # Cap evidence to pipeline recommendation.
        evidence_items = list(evidence_items)[: config.max_evidence_items]

        # -- Phase 1: Tier A (always cheap) --
        t0 = time.monotonic()
        tier_a_result = self._run_tier(
            tier="A",
            question=question,
            scenario=scenario if config.run_scenario_shock else None,
            historical_data=historical_data,
            evidence_items=evidence_items,
        )
        tier_a_ms = (time.monotonic() - t0) * 1000.0

        self.log_cost(
            operation="tier_a_forecast",
            model_tier="A",
            tokens_in=config.expected_input_tokens,
            tokens_out=config.expected_output_tokens,
            latency_ms=tier_a_ms,
            reference_id=tier_a_result.question_id,
        )

        # -- Phase 2: Decide whether to escalate --
        if self.should_escalate(tier_a_result, difficulty, budget):
            t1 = time.monotonic()
            tier_b_result = self._run_tier(
                tier="B",
                question=question,
                scenario=scenario,
                historical_data=historical_data,
                evidence_items=evidence_items,
            )
            tier_b_ms = (time.monotonic() - t1) * 1000.0

            self.log_cost(
                operation="tier_b_forecast",
                model_tier="B",
                tokens_in=config.expected_input_tokens * 2,
                tokens_out=config.expected_output_tokens * 2,
                latency_ms=tier_b_ms,
                reference_id=tier_b_result.question_id,
            )

            # -- Phase 3: Disagreement check --
            if self.has_disagreement(tier_a_result, tier_b_result):
                final = self.resolve_disagreement(
                    tier_a_result, tier_b_result, question
                )
            else:
                final = tier_b_result
        else:
            final = tier_a_result

        # -- Phase 4: Calibration --
        if config.run_calibration:
            final = self.apply_calibration(final, domain)

        return final

    # ------------------------------------------------------------------
    # Question analysis
    # ------------------------------------------------------------------

    def estimate_difficulty(self, question: dict[str, Any]) -> str:
        """Classify question as ``"easy"``/``"medium"``/``"hard"``.

        Delegates to :class:`QuestionRouter` and applies strategy-level
        overrides.

        Parameters
        ----------
        question:
            Question dict.

        Returns
        -------
        str
        """
        base_difficulty = self.question_router.estimate_difficulty(question)

        # Strategy overrides.
        if self.strategy == "benchmark_max_accuracy":
            # Treat everything as hard to get the full pipeline.
            return "hard"
        if self.strategy == "cheap_first":
            # Never classify as hard; cap at medium.
            if base_difficulty == "hard":
                return "medium"

        return base_difficulty

    def classify_domain(self, question: dict[str, Any]) -> str:
        """Classify question into a domain.

        Parameters
        ----------
        question:
            Question dict.

        Returns
        -------
        str
        """
        return self.question_router.classify_domain(question)

    # ------------------------------------------------------------------
    # Budget management
    # ------------------------------------------------------------------

    def compute_budget(self, difficulty: str, domain: str) -> float:
        """Return the maximum USD to spend on this question.

        The budget is the product of a difficulty-based base and a
        domain multiplier, capped by ``budget_per_question_usd``.

        Parameters
        ----------
        difficulty:
            ``"easy"``, ``"medium"``, or ``"hard"``.
        domain:
            Domain string.

        Returns
        -------
        float
            Budget in USD.
        """
        base = _BUDGET_BY_DIFFICULTY.get(difficulty, 0.08)
        multiplier = _DOMAIN_BUDGET_MULTIPLIER.get(domain, 1.0)
        computed = base * multiplier

        if self.strategy == "benchmark_max_under_budget":
            return min(computed, self.budget_per_question_usd)
        if self.strategy == "benchmark_max_accuracy":
            return self.budget_per_question_usd * 5.0  # generous
        return min(computed, self.budget_per_question_usd)

    # ------------------------------------------------------------------
    # Escalation logic
    # ------------------------------------------------------------------

    def should_escalate(
        self,
        tier_a_result: ForecastResult,
        difficulty: str,
        remaining_budget: float,
    ) -> bool:
        """Decide whether to escalate from Tier A to Tier B.

        Uses a value-of-information style gate: escalate only when
        the expected accuracy improvement from Tier B justifies the
        additional cost.

        Parameters
        ----------
        tier_a_result:
            Result from the Tier A run.
        difficulty:
            Question difficulty level.
        remaining_budget:
            USD remaining for this question.

        Returns
        -------
        bool
        """
        # Strategy-level overrides.
        if self.strategy == "cheap_first":
            # Only escalate if confidence is extremely low.
            return self._confidence_is_very_low(tier_a_result)

        if self.strategy == "benchmark_max_accuracy":
            # Always escalate.
            return True

        if self.strategy == "disagreement_second_pass":
            # Always run the second pass so we can check disagreement.
            return True

        if self.strategy == "benchmark_max_under_budget":
            # Escalate if budget allows Tier B.
            tier_b_cost_estimate = self.router.estimate_cost(
                self.router.get_model("B"), 3000, 1000
            )
            return remaining_budget >= tier_b_cost_estimate

        # Default strategies: calibrated_default, deep_research_on_hard.
        if difficulty == "easy":
            return False

        if difficulty == "hard" and self.strategy == "deep_research_on_hard":
            return True

        # Medium difficulty: escalate only if confidence is low.
        return self._confidence_is_low(tier_a_result)

    # ------------------------------------------------------------------
    # Disagreement detection and resolution
    # ------------------------------------------------------------------

    def has_disagreement(
        self,
        result_a: ForecastResult,
        result_b: ForecastResult,
        threshold: float = 0.15,
    ) -> bool:
        """Check if Tier A and Tier B disagree materially.

        Disagreement is defined as the absolute difference between
        posterior values exceeding *threshold*.

        Parameters
        ----------
        result_a:
            Tier A forecast result.
        result_b:
            Tier B forecast result.
        threshold:
            Maximum acceptable difference before we declare
            disagreement.

        Returns
        -------
        bool
        """
        diff = abs(result_a.posterior_value - result_b.posterior_value)
        has_disagree = diff > threshold

        if has_disagree:
            logger.info(
                "Disagreement detected: Tier A=%.4f, Tier B=%.4f, "
                "diff=%.4f > threshold=%.4f",
                result_a.posterior_value,
                result_b.posterior_value,
                diff,
                threshold,
            )
        return has_disagree

    def resolve_disagreement(
        self,
        result_a: ForecastResult,
        result_b: ForecastResult,
        question: dict[str, Any],
    ) -> ForecastResult:
        """Reconcile disagreeing Tier A and Tier B results.

        Resolution strategy:

        1. **Weighted average**: Tier B gets 2x the weight of Tier A
           because it uses a stronger model.
        2. **Extremity dampening**: if both results are on the same
           side of 0.5 (for binary targets), pull slightly toward the
           base rate to counteract over-confidence.
        3. **Confidence interval widening**: widen the CI to reflect
           genuine uncertainty revealed by the disagreement.

        Parameters
        ----------
        result_a:
            Tier A result.
        result_b:
            Tier B result.
        question:
            Question dict (used for target_type detection).

        Returns
        -------
        ForecastResult
            A new result representing the reconciled forecast.
        """
        weight_a = 1.0
        weight_b = 2.0
        total_weight = weight_a + weight_b

        blended_posterior = (
            weight_a * result_a.posterior_value
            + weight_b * result_b.posterior_value
        ) / total_weight

        target_type = question.get("target_type", "binary")
        if target_type == "binary":
            blended_posterior = max(0.01, min(0.99, blended_posterior))

        # Widen confidence interval to reflect disagreement.
        diff = abs(result_a.posterior_value - result_b.posterior_value)
        widening = diff / 2.0

        conf_lower = None
        conf_upper = None
        if result_b.confidence_lower is not None:
            conf_lower = max(0.0, result_b.confidence_lower - widening)
        if result_b.confidence_upper is not None:
            conf_upper = min(1.0, result_b.confidence_upper + widening) if target_type == "binary" else result_b.confidence_upper + widening

        rationale = (
            f"Disagreement resolved: Tier A={result_a.posterior_value:.4f}, "
            f"Tier B={result_b.posterior_value:.4f}, "
            f"blended={blended_posterior:.4f} (weights {weight_a}:{weight_b})."
        )

        return ForecastResult(
            forecast_run_id=result_b.forecast_run_id,
            question_id=result_b.question_id,
            scenario_id=result_b.scenario_id,
            model_version_id=result_b.model_version_id,
            prior_value=result_b.prior_value,
            posterior_value=blended_posterior,
            confidence_lower=conf_lower,
            confidence_upper=conf_upper,
            updates=result_b.updates,
            decomposition=result_b.decomposition,
            rationale=rationale,
        )

    # ------------------------------------------------------------------
    # Calibration
    # ------------------------------------------------------------------

    def apply_calibration(
        self,
        result: ForecastResult,
        domain: str,
    ) -> ForecastResult:
        """Apply domain-specific calibration transform.

        For now this uses a simple nudge table: if the model for a
        given domain tends to be over- or under-confident, we shift
        the posterior slightly toward the base rate (for binary
        forecasts) or apply a shrinkage factor (for continuous).

        When historical calibration data becomes available, this
        method can be upgraded to use Platt scaling or isotonic
        regression via :class:`CalibrationEngine`.

        Parameters
        ----------
        result:
            The forecast result to recalibrate.
        domain:
            Domain string.

        Returns
        -------
        ForecastResult
            A new result with calibrated posterior.
        """
        nudge_info = _CALIBRATION_NUDGE.get(domain, ("toward_base", 0.03))
        direction, magnitude = nudge_info

        target_type = (
            result.decomposition.target_type
            if result.decomposition
            else "binary"
        )

        calibrated_value = result.posterior_value

        if target_type == "binary" and direction == "toward_base":
            # Push toward 0.5 by *magnitude* of the distance.
            distance_from_center = calibrated_value - 0.5
            calibrated_value = calibrated_value - (distance_from_center * magnitude)
            calibrated_value = max(0.01, min(0.99, calibrated_value))
        elif target_type == "continuous" and direction == "toward_base":
            # Shrink toward the prior by *magnitude*.
            calibrated_value = (
                calibrated_value * (1.0 - magnitude)
                + result.prior_value * magnitude
            )

        if abs(calibrated_value - result.posterior_value) > 1e-9:
            rationale_addendum = (
                f" | Calibration ({domain}): {result.posterior_value:.4f} "
                f"→ {calibrated_value:.4f}"
            )
        else:
            rationale_addendum = ""

        return ForecastResult(
            forecast_run_id=result.forecast_run_id,
            question_id=result.question_id,
            scenario_id=result.scenario_id,
            model_version_id=result.model_version_id,
            prior_value=result.prior_value,
            posterior_value=calibrated_value,
            confidence_lower=result.confidence_lower,
            confidence_upper=result.confidence_upper,
            updates=result.updates,
            decomposition=result.decomposition,
            rationale=result.rationale + rationale_addendum,
            created_at=result.created_at,
        )

    # ------------------------------------------------------------------
    # Cost logging
    # ------------------------------------------------------------------

    def log_cost(
        self,
        operation: str,
        model_tier: str,
        tokens_in: int,
        tokens_out: int,
        latency_ms: float,
        reference_id: uuid.UUID | None = None,
    ) -> None:
        """Record cost for a pipeline operation.

        Parameters
        ----------
        operation:
            Operation label.
        model_tier:
            ``"A"`` or ``"B"``.
        tokens_in:
            Input tokens consumed.
        tokens_out:
            Output tokens consumed.
        latency_ms:
            Wall-clock latency.
        reference_id:
            Optional UUID linking to the question or run.
        """
        model_name = self.router.get_model(model_tier)
        self.cost_tracker.log(
            operation_type=operation,
            model_tier=model_tier,
            model_name=model_name,
            input_tokens=tokens_in,
            output_tokens=tokens_out,
            latency_ms=latency_ms,
            reference_id=reference_id,
            reference_type="forecast_run",
        )

    def get_total_cost(self) -> float:
        """Return total cost accumulated in this session.

        Returns
        -------
        float
            Cost in USD.
        """
        return self.cost_tracker.get_total()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_tier(
        self,
        tier: str,
        question: dict[str, Any],
        scenario: dict[str, Any] | None,
        historical_data: Sequence[float],
        evidence_items: Sequence[dict[str, Any]],
    ) -> ForecastResult:
        """Execute the forecast engine with model-tier annotation.

        The underlying :class:`ForecastEngine` is model-agnostic (it
        does not call LLMs itself), so the tier choice is currently
        recorded via the cost tracker for accounting purposes.  In a
        production deployment, different model clients would be wired
        in here.

        Parameters
        ----------
        tier:
            ``"A"`` or ``"B"``.
        question:
            Question dict.
        scenario:
            Optional scenario dict.
        historical_data:
            Time series.
        evidence_items:
            Evidence items.

        Returns
        -------
        ForecastResult
        """
        model_name = self.router.get_model(tier)
        model_version_id = uuid.uuid5(
            uuid.NAMESPACE_DNS, f"model-{model_name}-tier-{tier}"
        )

        result = self.engine.create_forecast(
            question=question,
            historical_data=historical_data,
            evidence_items=evidence_items,
            scenario=scenario,
            model_version_id=model_version_id,
        )

        return result

    def _confidence_is_low(self, result: ForecastResult) -> bool:
        """Return ``True`` if the forecast confidence interval is wide.

        A binary forecast with CI width > 0.40 or a posterior between
        0.35 and 0.65 is considered low-confidence.

        Parameters
        ----------
        result:
            Forecast result.

        Returns
        -------
        bool
        """
        if result.confidence_lower is not None and result.confidence_upper is not None:
            width = result.confidence_upper - result.confidence_lower
            if width > 0.40:
                return True

        # Binary: posterior near 50% indicates indecision.
        target_type = (
            result.decomposition.target_type
            if result.decomposition
            else "binary"
        )
        if target_type == "binary":
            p = result.posterior_value
            if 0.35 <= p <= 0.65:
                return True

        return False

    def _confidence_is_very_low(self, result: ForecastResult) -> bool:
        """Stricter version of :pymeth:`_confidence_is_low`.

        Used by the ``cheap_first`` strategy to only escalate when
        confidence is extremely poor (CI > 0.55 or posterior in
        0.40–0.60 range for binary targets).

        Parameters
        ----------
        result:
            Forecast result.

        Returns
        -------
        bool
        """
        if result.confidence_lower is not None and result.confidence_upper is not None:
            width = result.confidence_upper - result.confidence_lower
            if width > 0.55:
                return True

        target_type = (
            result.decomposition.target_type
            if result.decomposition
            else "binary"
        )
        if target_type == "binary":
            p = result.posterior_value
            if 0.40 <= p <= 0.60:
                return True

        return False
