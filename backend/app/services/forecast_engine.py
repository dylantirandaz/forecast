"""Top-level forecast orchestration engine.

Coordinates the full pipeline: question decomposition, base-rate
computation, evidence scoring, belief updating, and scenario comparison.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Sequence

from .base_rate_engine import BaseRateEngine
from .belief_updater import BeliefUpdater, ForecastUpdateRecord
from .evidence_scorer import EvidenceScorer, EvidenceScoreResult
from .scenario_engine import ScenarioEngine

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------

@dataclass
class QuestionDecomposition:
    """Structured decomposition of a forecasting question."""

    target_metric: str
    target_type: str  # "binary" | "continuous"
    forecast_horizon_months: int
    geography: str
    causal_channels: list[str]
    evidence_streams: list[str]
    resolution_criteria: str


@dataclass
class ForecastResult:
    """Complete output of a forecast pipeline run."""

    forecast_run_id: uuid.UUID
    question_id: uuid.UUID
    scenario_id: uuid.UUID | None
    model_version_id: uuid.UUID | None

    prior_value: float
    posterior_value: float
    confidence_lower: float | None = None
    confidence_upper: float | None = None

    prior_distribution: dict[str, Any] | None = None
    posterior_distribution: dict[str, Any] | None = None

    updates: list[ForecastUpdateRecord] = field(default_factory=list)
    decomposition: QuestionDecomposition | None = None
    rationale: str = ""
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


@dataclass
class ScenarioComparison:
    """Side-by-side comparison of forecast results across scenarios."""

    question_id: uuid.UUID
    scenario_results: dict[uuid.UUID, ForecastResult]
    summary: str


# ---------------------------------------------------------------------------
# Default causal channels for NYC housing
# ---------------------------------------------------------------------------

_DEFAULT_CAUSAL_CHANNELS: dict[str, list[str]] = {
    "rent": [
        "rgb_guideline_orders",
        "vacancy_rates",
        "income_growth",
        "operating_cost_inflation",
        "new_construction_supply",
        "migration_patterns",
    ],
    "vacancy": [
        "new_construction_supply",
        "rent_levels",
        "eviction_rates",
        "migration_patterns",
        "economic_conditions",
    ],
    "homelessness": [
        "rent_burden",
        "income_levels",
        "eviction_rates",
        "shelter_capacity",
        "social_services_funding",
    ],
    "construction": [
        "zoning_policy",
        "interest_rates",
        "material_costs",
        "labor_availability",
        "421a_tax_incentives",
    ],
}

_DEFAULT_EVIDENCE_STREAMS: list[str] = [
    "official_statistics",
    "rgb_orders_and_testimony",
    "academic_research",
    "news_and_journalism",
    "expert_opinion",
    "model_outputs",
]


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class ForecastEngine:
    """Orchestrate the end-to-end forecast pipeline.

    This engine does **not** interact with the database directly.
    The caller (typically an API route or task worker) is responsible
    for loading ORM objects, passing them in as plain dicts, and
    persisting the results.

    Typical flow::

        engine = ForecastEngine()
        result = engine.create_forecast(
            question=question_dict,
            scenario=scenario_dict,
            historical_data=series,
            evidence_items=evidence_list,
        )
    """

    def __init__(
        self,
        base_rate_engine: BaseRateEngine | None = None,
        evidence_scorer: EvidenceScorer | None = None,
        belief_updater: BeliefUpdater | None = None,
        scenario_engine: ScenarioEngine | None = None,
    ) -> None:
        self.base_rate = base_rate_engine or BaseRateEngine()
        self.scorer = evidence_scorer or EvidenceScorer()
        self.updater = belief_updater or BeliefUpdater()
        self.scenarios = scenario_engine or ScenarioEngine()

    # ------------------------------------------------------------------
    # Question decomposition
    # ------------------------------------------------------------------

    def decompose_question(
        self,
        question: dict[str, Any],
    ) -> QuestionDecomposition:
        """Break a forecasting question into structured components.

        Parameters
        ----------
        question:
            Dict with keys ``title``, ``description``, ``target_type``,
            ``target_metric``, ``forecast_horizon_months``,
            ``unit_of_analysis``, ``resolution_criteria``.

        Returns
        -------
        QuestionDecomposition
        """
        target_metric = question.get("target_metric", "unknown")
        target_type = question.get("target_type", "binary")
        geography = question.get("unit_of_analysis", "nyc")
        horizon = int(question.get("forecast_horizon_months", 12))
        resolution = question.get("resolution_criteria", "")

        # Select causal channels based on target metric keywords.
        channels = _DEFAULT_CAUSAL_CHANNELS.get("rent", [])
        for key, chs in _DEFAULT_CAUSAL_CHANNELS.items():
            if key in target_metric.lower():
                channels = chs
                break

        return QuestionDecomposition(
            target_metric=target_metric,
            target_type=target_type,
            forecast_horizon_months=horizon,
            geography=geography,
            causal_channels=channels,
            evidence_streams=list(_DEFAULT_EVIDENCE_STREAMS),
            resolution_criteria=resolution,
        )

    # ------------------------------------------------------------------
    # Full pipeline
    # ------------------------------------------------------------------

    def create_forecast(
        self,
        question: dict[str, Any],
        historical_data: Sequence[float],
        evidence_items: Sequence[dict[str, Any]],
        scenario: dict[str, Any] | None = None,
        model_version_id: uuid.UUID | None = None,
    ) -> ForecastResult:
        """Run the complete forecast pipeline.

        Steps:
        1. Decompose the question.
        2. Compute base rate from historical data.
        3. Apply scenario shock (if scenario provided).
        4. Score each evidence item.
        5. Sequentially apply Bayesian updates.
        6. Package results.

        Parameters
        ----------
        question:
            Serialised question dict.
        historical_data:
            Historical time series for base-rate computation.
        evidence_items:
            List of evidence item dicts.
        scenario:
            Optional scenario dict.
        model_version_id:
            Optional model version UUID.

        Returns
        -------
        ForecastResult
        """
        decomposition = self.decompose_question(question)
        question_id = uuid.UUID(str(question["id"])) if "id" in question else uuid.uuid4()
        scenario_id = (
            uuid.UUID(str(scenario["id"])) if scenario and "id" in scenario else None
        )
        forecast_run_id = uuid.uuid4()

        # --- Step 1: base rate ---
        base_rate = self.base_rate.compute_base_rate(
            target_metric=decomposition.target_metric,
            geography=decomposition.geography,
            data=historical_data,
        )

        if decomposition.target_type == "binary":
            # For binary, use the historical positive-outcome rate as prior.
            prior_value = base_rate.stats.mean
            prior_value = max(0.01, min(0.99, prior_value))
            prior_std = None
        else:
            prior_value = base_rate.stats.mean
            prior_std = base_rate.stats.std

        # --- Step 2: scenario shock ---
        if scenario:
            shock = self.scenarios.compute_scenario_shock(
                scenario=scenario,
                target=decomposition.target_metric,
            )
            if decomposition.target_type == "binary":
                prior_value = max(0.01, min(0.99, prior_value + shock))
            else:
                prior_value += shock

        # --- Step 3: score evidence ---
        scored_items: list[dict[str, Any]] = []
        existing: list[dict[str, Any]] = []
        for ev in evidence_items:
            score_result = self.scorer.score_evidence(
                evidence_item=ev,
                question=question,
                existing_evidence=existing,
            )
            scored_items.append({
                "evidence_item_id": ev.get("id"),
                "evidence_score": {
                    "composite_weight": score_result.composite_weight,
                    "directional_effect": score_result.directional_effect,
                    "expected_magnitude": score_result.expected_magnitude,
                    "uncertainty": score_result.uncertainty,
                },
            })
            existing.append(ev)

        # --- Step 4: belief updates ---
        posterior_value, updates = self.updater.batch_update(
            forecast_run_id=forecast_run_id,
            target_type=decomposition.target_type,
            prior_value=prior_value,
            evidence_items_with_scores=scored_items,
            prior_std=prior_std,
        )

        # --- Step 5: confidence interval ---
        if decomposition.target_type == "continuous" and prior_std is not None:
            conf_lower = posterior_value - 1.96 * prior_std
            conf_upper = posterior_value + 1.96 * prior_std
        elif decomposition.target_type == "binary":
            # Wilson interval approximation.
            n = max(len(historical_data), 30)
            z = 1.96
            p = posterior_value
            denom = 1 + z ** 2 / n
            centre = (p + z ** 2 / (2 * n)) / denom
            margin = z * ((p * (1 - p) / n + z ** 2 / (4 * n ** 2)) ** 0.5) / denom
            conf_lower = max(0.0, centre - margin)
            conf_upper = min(1.0, centre + margin)
        else:
            conf_lower = None
            conf_upper = None

        rationale = (
            f"Base rate ({decomposition.target_metric}@{decomposition.geography}): "
            f"{base_rate.stats.mean:.4f}. "
            f"After incorporating {len(updates)} evidence items, "
            f"posterior = {posterior_value:.4f}."
        )

        return ForecastResult(
            forecast_run_id=forecast_run_id,
            question_id=question_id,
            scenario_id=scenario_id,
            model_version_id=model_version_id,
            prior_value=prior_value,
            posterior_value=posterior_value,
            confidence_lower=conf_lower,
            confidence_upper=conf_upper,
            updates=updates,
            decomposition=decomposition,
            rationale=rationale,
        )

    # ------------------------------------------------------------------
    # Convenience wrappers
    # ------------------------------------------------------------------

    def run_forecast(
        self,
        question: dict[str, Any],
        historical_data: Sequence[float],
        evidence_items: Sequence[dict[str, Any]],
        scenario: dict[str, Any] | None = None,
        model_version_id: uuid.UUID | None = None,
    ) -> ForecastResult:
        """Alias for :py:meth:`create_forecast` for API symmetry."""
        return self.create_forecast(
            question=question,
            historical_data=historical_data,
            evidence_items=evidence_items,
            scenario=scenario,
            model_version_id=model_version_id,
        )

    def update_forecast(
        self,
        previous_result: ForecastResult,
        new_evidence: Sequence[dict[str, Any]],
        question: dict[str, Any],
    ) -> ForecastResult:
        """Add new evidence to an existing forecast and re-update.

        Parameters
        ----------
        previous_result:
            The most recent ``ForecastResult``.
        new_evidence:
            Newly arrived evidence items.
        question:
            Question dict (needed for scoring context).

        Returns
        -------
        ForecastResult
            Updated forecast with appended update records.
        """
        existing_evidence: list[dict[str, Any]] = []
        scored_items: list[dict[str, Any]] = []
        for ev in new_evidence:
            score_result = self.scorer.score_evidence(
                evidence_item=ev,
                question=question,
                existing_evidence=existing_evidence,
            )
            scored_items.append({
                "evidence_item_id": ev.get("id"),
                "evidence_score": {
                    "composite_weight": score_result.composite_weight,
                    "directional_effect": score_result.directional_effect,
                    "expected_magnitude": score_result.expected_magnitude,
                    "uncertainty": score_result.uncertainty,
                },
            })
            existing_evidence.append(ev)

        target_type = (
            previous_result.decomposition.target_type
            if previous_result.decomposition
            else "binary"
        )
        posterior, new_updates = self.updater.batch_update(
            forecast_run_id=previous_result.forecast_run_id,
            target_type=target_type,
            prior_value=previous_result.posterior_value,
            evidence_items_with_scores=scored_items,
        )

        # Combine old and new updates, adjusting order.
        offset = len(previous_result.updates)
        for u in new_updates:
            u.update_order += offset

        return ForecastResult(
            forecast_run_id=previous_result.forecast_run_id,
            question_id=previous_result.question_id,
            scenario_id=previous_result.scenario_id,
            model_version_id=previous_result.model_version_id,
            prior_value=previous_result.prior_value,
            posterior_value=posterior,
            confidence_lower=previous_result.confidence_lower,
            confidence_upper=previous_result.confidence_upper,
            updates=previous_result.updates + new_updates,
            decomposition=previous_result.decomposition,
            rationale=(
                f"{previous_result.rationale} | "
                f"Updated with {len(new_updates)} new evidence items → "
                f"{posterior:.4f}."
            ),
        )

    def compare_scenarios(
        self,
        question: dict[str, Any],
        scenarios: Sequence[dict[str, Any]],
        historical_data: Sequence[float],
        evidence_items: Sequence[dict[str, Any]],
        model_version_id: uuid.UUID | None = None,
    ) -> ScenarioComparison:
        """Run the same question across multiple scenarios.

        Parameters
        ----------
        question:
            Question dict.
        scenarios:
            List of scenario dicts.
        historical_data:
            Time series for base-rate computation.
        evidence_items:
            Evidence to apply under each scenario.
        model_version_id:
            Optional model version UUID.

        Returns
        -------
        ScenarioComparison
        """
        question_id = uuid.UUID(str(question["id"])) if "id" in question else uuid.uuid4()
        results: dict[uuid.UUID, ForecastResult] = {}

        for sc in scenarios:
            result = self.create_forecast(
                question=question,
                historical_data=historical_data,
                evidence_items=evidence_items,
                scenario=sc,
                model_version_id=model_version_id,
            )
            results[result.forecast_run_id] = result

        # Build summary.
        lines = [f"Scenario comparison for question {question_id}:"]
        for run_id, r in results.items():
            label = r.scenario_id or "baseline"
            lines.append(
                f"  Scenario {label}: prior={r.prior_value:.4f}, "
                f"posterior={r.posterior_value:.4f}"
            )

        return ScenarioComparison(
            question_id=question_id,
            scenario_results=results,
            summary="\n".join(lines),
        )
