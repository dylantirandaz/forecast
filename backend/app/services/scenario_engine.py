"""Scenario management engine.

Handles creation, parametrisation, and comparison of policy scenarios.
Includes three hardcoded Mamdani scenarios for the NYC rent-stabilisation
system.
"""

from __future__ import annotations

import logging
import uuid
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Sequence

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------

@dataclass
class PolicyAdjustment:
    """A single quantitative policy lever extracted from a scenario."""

    lever_name: str
    direction: str  # "increase" | "decrease" | "freeze" | "neutral"
    magnitude: float  # absolute amount or percentage change
    unit: str  # "percent", "dollars", "units", etc.
    confidence: float  # 0-1 how confident we are in this estimate


@dataclass
class ScenarioShock:
    """Estimated direct effect of a scenario on a target metric."""

    target_metric: str
    shock_value: float  # additive shift to the forecast
    shock_pct: float  # percentage change from baseline
    channels: list[str]  # causal channels through which the shock acts
    rationale: str


@dataclass
class ScenarioComparisonResult:
    """Side-by-side output for comparing scenarios."""

    scenarios: list[dict[str, Any]]
    shocks: dict[str, ScenarioShock]  # keyed by scenario name
    summary: str


# ---------------------------------------------------------------------------
# Hardcoded Mamdani scenarios
# ---------------------------------------------------------------------------

MAMDANI_SCENARIOS: dict[str, dict[str, Any]] = {
    "soft_implementation": {
        "name": "Soft Implementation",
        "narrative": (
            "The Rent Guidelines Board adopts modest guideline increases of "
            "1-2% annually, paired with incremental acceleration of "
            "affordable housing programmes.  No rent freeze; emphasis on "
            "gradual tenant relief without sharply squeezing owner revenue."
        ),
        "intensity": "soft",
        "assumptions": [
            "RGB annual increases of 1-2% for 1-year leases",
            "No significant changes to vacancy decontrol thresholds",
            "Incremental increase in HPD-administered affordable units",
            "421-a successor programme continues at current scale",
            "Operating-cost inflation roughly matches CPI",
        ],
        "policy_levers": {
            "rgb_increase_1yr_pct": 1.5,
            "rgb_increase_2yr_pct": 2.5,
            "affordable_construction_boost_pct": 5.0,
            "vacancy_decontrol_threshold_change": 0,
            "tax_incentive_change_pct": 0.0,
        },
        "timing_start": "2025-07-01",
        "timing_end": "2029-06-30",
        "expected_channels": {
            "rent_levels": "slight_increase",
            "vacancy_rate": "stable",
            "owner_financial_pressure": "low",
            "tenant_displacement": "slight_decrease",
            "new_construction": "stable",
        },
    },
    "full_rent_freeze": {
        "name": "Full Rent Freeze",
        "narrative": (
            "The RGB adopts a near-zero guideline (0% for 1-year leases, "
            "0-1% for 2-year leases) sustained over four consecutive "
            "years.  No accompanying supply-side measures.  Owners face "
            "rising costs without commensurate revenue increases, "
            "potentially triggering deferred maintenance and reduced "
            "investment."
        ),
        "intensity": "aggressive",
        "assumptions": [
            "RGB sets 0% increase for 1-year leases for 4 consecutive years",
            "RGB sets 0-1% increase for 2-year leases",
            "Operating costs continue to rise at 3-4% per year",
            "No new tax incentives or subsidy programmes for owners",
            "No major change in zoning or housing supply policy",
            "Potential increase in deferred maintenance / building deterioration",
        ],
        "policy_levers": {
            "rgb_increase_1yr_pct": 0.0,
            "rgb_increase_2yr_pct": 0.5,
            "affordable_construction_boost_pct": 0.0,
            "vacancy_decontrol_threshold_change": 0,
            "tax_incentive_change_pct": 0.0,
            "owner_cost_squeeze_annual_pct": 3.5,
        },
        "timing_start": "2025-07-01",
        "timing_end": "2029-06-30",
        "expected_channels": {
            "rent_levels": "frozen",
            "vacancy_rate": "decrease",
            "owner_financial_pressure": "high",
            "tenant_displacement": "decrease_short_term",
            "new_construction": "decrease",
            "maintenance_quality": "decrease",
        },
    },
    "freeze_plus_buildout": {
        "name": "Freeze + Major Subsidised Buildout",
        "narrative": (
            "Combines a full rent freeze (0% RGB for 4 years) with a "
            "major public investment push: accelerated subsidised "
            "construction, expanded voucher programmes, and new tax "
            "incentives for affordable-only development.  This is the "
            "most interventionist scenario, aiming to hold rents flat "
            "while materially expanding the affordable stock."
        ),
        "intensity": "aggressive",
        "assumptions": [
            "RGB sets 0% increase for 1-year leases for 4 consecutive years",
            "City commits $5B+ additional capital for affordable housing",
            "New 421-a successor targets 100% affordable projects",
            "Expanded Section 8 / HCV programme (+15,000 vouchers)",
            "Streamlined permitting for affordable projects",
            "Operating costs rise but partly offset by new tax abatements",
        ],
        "policy_levers": {
            "rgb_increase_1yr_pct": 0.0,
            "rgb_increase_2yr_pct": 0.5,
            "affordable_construction_boost_pct": 40.0,
            "voucher_expansion_units": 15000,
            "capital_investment_billions": 5.0,
            "tax_incentive_change_pct": -15.0,
            "vacancy_decontrol_threshold_change": 0,
        },
        "timing_start": "2025-07-01",
        "timing_end": "2029-06-30",
        "expected_channels": {
            "rent_levels": "frozen",
            "vacancy_rate": "increase_medium_term",
            "owner_financial_pressure": "moderate",
            "tenant_displacement": "significant_decrease",
            "new_construction": "significant_increase_affordable",
            "maintenance_quality": "stable_with_abatements",
        },
    },
}


# ---------------------------------------------------------------------------
# Shock-estimation lookup (metric → scenario → estimated shift)
# ---------------------------------------------------------------------------

# These are calibrated rough estimates of how each scenario shifts
# common NYC housing metrics.  Values are in the **natural units**
# of the metric (e.g. percentage-point change in vacancy rate).
_SHOCK_TABLE: dict[str, dict[str, float]] = {
    "median_rent_stabilised": {
        "soft_implementation": 30.0,      # ~$30/month over 4 years
        "full_rent_freeze": -10.0,        # slight decrease (real terms)
        "freeze_plus_buildout": -15.0,
    },
    "vacancy_rate": {
        "soft_implementation": 0.0,
        "full_rent_freeze": -0.3,         # tighter market
        "freeze_plus_buildout": 0.5,      # new supply loosens market
    },
    "rent_burden_pct": {
        "soft_implementation": 0.5,
        "full_rent_freeze": -1.5,
        "freeze_plus_buildout": -2.5,
    },
    "owner_net_operating_income": {
        "soft_implementation": -500.0,
        "full_rent_freeze": -3000.0,
        "freeze_plus_buildout": -2000.0,  # partially offset by abatements
    },
    "homelessness_rate": {
        "soft_implementation": 0.0,
        "full_rent_freeze": -0.2,
        "freeze_plus_buildout": -0.5,
    },
}


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class ScenarioEngine:
    """Create, parameterise, and compare policy scenarios."""

    def __init__(self) -> None:
        self._mamdani = deepcopy(MAMDANI_SCENARIOS)

    # ------------------------------------------------------------------
    # Scenario CRUD
    # ------------------------------------------------------------------

    def create_scenario(
        self,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a new scenario definition.

        Parameters
        ----------
        params:
            Dict with keys ``name``, ``narrative``, ``intensity``,
            ``assumptions``, ``policy_levers``, ``timing_start``,
            ``timing_end``, ``expected_channels``.

        Returns
        -------
        dict
            The scenario dict with a generated ``id``.
        """
        scenario = {
            "id": str(uuid.uuid4()),
            **params,
        }
        logger.info("Created scenario '%s' (id=%s)", params.get("name"), scenario["id"])
        return scenario

    def get_mamdani_scenarios(self) -> dict[str, dict[str, Any]]:
        """Return the three hardcoded Mamdani scenarios.

        Returns
        -------
        dict
            Mapping of scenario key to scenario dict.
        """
        return deepcopy(self._mamdani)

    # ------------------------------------------------------------------
    # Policy extraction
    # ------------------------------------------------------------------

    @staticmethod
    def get_policy_adjustments(
        scenario: dict[str, Any],
    ) -> list[PolicyAdjustment]:
        """Extract quantitative policy parameters from a scenario.

        Parameters
        ----------
        scenario:
            A scenario dict with ``policy_levers``.

        Returns
        -------
        list[PolicyAdjustment]
        """
        levers = scenario.get("policy_levers") or {}
        adjustments: list[PolicyAdjustment] = []

        for lever_name, value in levers.items():
            if isinstance(value, (int, float)):
                if value > 0:
                    direction = "increase"
                elif value < 0:
                    direction = "decrease"
                else:
                    direction = "freeze"

                # Infer unit from lever name.
                if "pct" in lever_name:
                    unit = "percent"
                elif "units" in lever_name or "voucher" in lever_name:
                    unit = "units"
                elif "billions" in lever_name:
                    unit = "billions_usd"
                elif "dollars" in lever_name or "income" in lever_name:
                    unit = "dollars"
                else:
                    unit = "raw"

                adjustments.append(
                    PolicyAdjustment(
                        lever_name=lever_name,
                        direction=direction,
                        magnitude=abs(float(value)),
                        unit=unit,
                        confidence=0.7,
                    )
                )

        return adjustments

    # ------------------------------------------------------------------
    # Shock computation
    # ------------------------------------------------------------------

    def compute_scenario_shock(
        self,
        scenario: dict[str, Any],
        target: str,
    ) -> float:
        """Estimate the direct additive effect of a scenario on a target.

        Looks up the shock table first; if no exact match is found,
        falls back to a heuristic based on policy levers and scenario
        intensity.

        Parameters
        ----------
        scenario:
            Scenario dict (must have ``name`` or ``intensity``).
        target:
            Target metric name (e.g. ``"median_rent_stabilised"``).

        Returns
        -------
        float
            Estimated additive shock in the metric's natural units.
        """
        # Normalise scenario name for lookup.
        name = (
            scenario.get("name", "")
            .lower()
            .replace(" ", "_")
            .replace("-", "_")
        )

        # Try exact lookup.
        metric_shocks = _SHOCK_TABLE.get(target, {})
        if name in metric_shocks:
            shock = metric_shocks[name]
            logger.info(
                "Shock for '%s' on '%s' = %.2f (lookup)",
                name, target, shock,
            )
            return shock

        # Try partial match.
        for key in metric_shocks:
            if key in name or name in key:
                shock = metric_shocks[key]
                logger.info(
                    "Shock for '%s' on '%s' = %.2f (partial match '%s')",
                    name, target, shock, key,
                )
                return shock

        # Heuristic fallback: derive from intensity.
        intensity = scenario.get("intensity", "moderate")
        intensity_multiplier = {
            "soft": 0.3,
            "moderate": 0.6,
            "aggressive": 1.0,
        }.get(intensity, 0.5)

        # Use the sum of absolute policy lever values as a rough proxy
        # for "how much is changing".
        levers = scenario.get("policy_levers") or {}
        lever_sum = sum(
            abs(float(v)) for v in levers.values()
            if isinstance(v, (int, float))
        )

        # Scale down to a plausible additive shock.
        shock = intensity_multiplier * lever_sum * 0.01
        logger.info(
            "Shock for '%s' on '%s' = %.4f (heuristic, intensity=%s)",
            name, target, shock, intensity,
        )
        return shock

    # ------------------------------------------------------------------
    # Scenario comparison
    # ------------------------------------------------------------------

    def compare_scenarios(
        self,
        scenarios: Sequence[dict[str, Any]],
        question: dict[str, Any],
    ) -> ScenarioComparisonResult:
        """Compute and compare scenario shocks for a given question.

        Parameters
        ----------
        scenarios:
            List of scenario dicts.
        question:
            Question dict with at least ``target_metric``.

        Returns
        -------
        ScenarioComparisonResult
        """
        target = question.get("target_metric", "unknown")
        shocks: dict[str, ScenarioShock] = {}
        lines = [f"Scenario comparison for target '{target}':"]

        for sc in scenarios:
            sc_name = sc.get("name", "unnamed")
            shock_val = self.compute_scenario_shock(sc, target)
            adjustments = self.get_policy_adjustments(sc)
            channels = list(
                (sc.get("expected_channels") or {}).keys()
            )

            shock = ScenarioShock(
                target_metric=target,
                shock_value=shock_val,
                shock_pct=0.0,  # would need baseline to compute %
                channels=channels,
                rationale=(
                    f"Scenario '{sc_name}' has {len(adjustments)} policy "
                    f"levers affecting {len(channels)} causal channels."
                ),
            )
            shocks[sc_name] = shock
            lines.append(
                f"  {sc_name}: shock={shock_val:+.2f}, "
                f"channels={channels}"
            )

        return ScenarioComparisonResult(
            scenarios=list(scenarios),
            shocks=shocks,
            summary="\n".join(lines),
        )
