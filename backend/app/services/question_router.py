"""Question routing by domain and difficulty.

Classifies incoming forecast questions by subject-matter domain and
estimated difficulty so the orchestrator can allocate compute
resources (model tier, evidence depth, number of passes) optimally.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Sequence

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------

@dataclass
class PipelineConfig:
    """Recommended pipeline configuration for a question.

    Produced by :pymeth:`QuestionRouter.recommend_pipeline` and consumed
    by the orchestrator to decide which stages to run and at what
    quality level.
    """

    model_tier: str                    # "A" or "B"
    run_base_rate: bool                # whether to compute base rate
    run_evidence_scoring: bool         # whether to score evidence
    run_calibration: bool              # whether to apply recalibration
    run_scenario_shock: bool           # whether scenario shocks apply
    escalation_allowed: bool           # whether Tier B escalation is ok
    max_evidence_items: int            # cap on evidence to process
    expected_input_tokens: int         # rough token budget estimate
    expected_output_tokens: int        # rough token budget estimate
    rationale: str                     # human-readable explanation


# ---------------------------------------------------------------------------
# Domain keyword mapping
# ---------------------------------------------------------------------------

DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "housing_supply": [
        "permit", "starts", "completion", "construction", "building",
        "units", "development", "pipeline", "new housing", "421-a",
        "421a", "zoning lot", "certificate of occupancy",
    ],
    "prices": [
        "rent", "price", "sale", "market", "affordable", "median rent",
        "asking rent", "listing price", "rent stabilized",
        "rent burden", "cost-burdened",
    ],
    "building_quality": [
        "complaint", "violation", "maintenance", "repair", "hpd",
        "dob", "inspection", "lead paint", "mold", "heat",
        "elevator", "boiler", "facade",
    ],
    "macro": [
        "inflation", "employment", "interest", "gdp", "wage",
        "unemployment", "cpi", "federal funds", "mortgage rate",
        "recession", "labor market",
    ],
    "policy": [
        "legislation", "regulation", "zoning", "rent control",
        "stabiliz", "rgb", "rent guidelines board", "good cause",
        "eviction", "voucher", "section 8", "hcv", "ceqr",
    ],
}

# ---------------------------------------------------------------------------
# Difficulty signal heuristics
# ---------------------------------------------------------------------------

# Thresholds used by the difficulty classifier.
_EASY_MAX_CHANNELS = 2
_EASY_MAX_HORIZON_MONTHS = 12
_MEDIUM_MAX_CHANNELS = 5
_MEDIUM_MAX_HORIZON_MONTHS = 36

# Words that signal higher complexity.
_HARD_SIGNAL_WORDS: list[str] = [
    "interact", "compound", "nonlinear", "second-order",
    "unprecedented", "structural change", "regime shift",
    "counterfactual", "causal", "endogen",
]


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class QuestionRouter:
    """Route questions by domain and difficulty for optimal resource allocation.

    This class performs lightweight, heuristic-based classification so
    that the orchestrator does not need to call an LLM just to figure
    out *how* to call an LLM.

    Usage::

        router = QuestionRouter()
        domain = router.classify_domain(question_dict)
        difficulty = router.estimate_difficulty(question_dict)
        config = router.recommend_pipeline(domain, difficulty)
    """

    # ------------------------------------------------------------------
    # Domain classification
    # ------------------------------------------------------------------

    def classify_domain(self, question: dict[str, Any]) -> str:
        """Classify a question into one of the known NYC-housing domains.

        Scoring is based on keyword overlap between the question text
        (title + description + target_metric) and each domain's keyword
        list.  The domain with the highest overlap wins.  Ties are
        broken alphabetically.

        Parameters
        ----------
        question:
            Dict with optional keys ``title``, ``description``,
            ``target_metric``.

        Returns
        -------
        str
            One of ``"housing_supply"``, ``"prices"``,
            ``"building_quality"``, ``"macro"``, ``"policy"``, or
            ``"unknown"`` if no keywords match.
        """
        text = self._extract_text(question).lower()
        scores: dict[str, int] = {}

        for domain, keywords in DOMAIN_KEYWORDS.items():
            score = 0
            for kw in keywords:
                # Count each unique keyword at most once to avoid
                # inflating score with repeated words.
                if kw in text:
                    score += 1
            scores[domain] = score

        if not scores or max(scores.values()) == 0:
            return "unknown"

        best_domain = max(scores, key=lambda d: (scores[d], d))
        logger.debug("Domain classification: %s  (scores=%s)", best_domain, scores)
        return best_domain

    # ------------------------------------------------------------------
    # Difficulty estimation
    # ------------------------------------------------------------------

    def estimate_difficulty(
        self,
        question: dict[str, Any],
        available_base_rates: Sequence[str] | None = None,
    ) -> str:
        """Classify question difficulty as ``"easy"``, ``"medium"``, or ``"hard"``.

        Heuristics considered:

        1. **Forecast horizon**: longer horizons are harder.
        2. **Number of causal channels**: more channels = harder.
        3. **Base-rate availability**: if no historical base rate exists
           for the target metric, the question is harder.
        4. **Complexity signals**: presence of words like
           ``"nonlinear"``, ``"unprecedented"`` etc.

        Parameters
        ----------
        question:
            Question dict (same schema as :pymeth:`classify_domain`).
        available_base_rates:
            Optional list of metric names for which base-rate data is
            available.  If the question's ``target_metric`` is in this
            list, difficulty is reduced.

        Returns
        -------
        str
            ``"easy"``, ``"medium"``, or ``"hard"``.
        """
        score = 0  # higher = harder

        # --- Horizon ---
        horizon = int(question.get("forecast_horizon_months", 12))
        if horizon > _MEDIUM_MAX_HORIZON_MONTHS:
            score += 3
        elif horizon > _EASY_MAX_HORIZON_MONTHS:
            score += 1

        # --- Causal channels ---
        channels = question.get("causal_channels", [])
        if isinstance(channels, list):
            n_channels = len(channels)
        else:
            n_channels = 0
        if n_channels > _MEDIUM_MAX_CHANNELS:
            score += 3
        elif n_channels > _EASY_MAX_CHANNELS:
            score += 1

        # --- Base-rate availability ---
        target_metric = question.get("target_metric", "")
        has_base_rate = False
        if available_base_rates is not None:
            has_base_rate = target_metric in available_base_rates
        else:
            # If we don't know, assume base rate exists for common metrics.
            common_metrics = {
                "median_rent_stabilised", "vacancy_rate",
                "rent_burden_pct", "homelessness_rate",
                "owner_net_operating_income",
            }
            has_base_rate = target_metric in common_metrics

        if not has_base_rate:
            score += 2

        # --- Complexity signal words ---
        text = self._extract_text(question).lower()
        complexity_hits = sum(1 for w in _HARD_SIGNAL_WORDS if w in text)
        score += min(complexity_hits, 3)  # cap contribution

        # --- Target type ---
        # Continuous targets are slightly harder than binary.
        if question.get("target_type", "binary") == "continuous":
            score += 1

        # --- Classify ---
        if score <= 2:
            difficulty = "easy"
        elif score <= 5:
            difficulty = "medium"
        else:
            difficulty = "hard"

        logger.debug(
            "Difficulty estimation: %s  (score=%d, horizon=%d, channels=%d, "
            "has_base_rate=%s, complexity_hits=%d)",
            difficulty, score, horizon, n_channels,
            has_base_rate, complexity_hits,
        )
        return difficulty

    # ------------------------------------------------------------------
    # Pipeline recommendation
    # ------------------------------------------------------------------

    def recommend_pipeline(
        self,
        domain: str,
        difficulty: str,
    ) -> PipelineConfig:
        """Produce a recommended pipeline configuration.

        Maps ``(domain, difficulty)`` to a concrete set of pipeline
        toggles and resource estimates.

        Parameters
        ----------
        domain:
            Domain string from :pymeth:`classify_domain`.
        difficulty:
            Difficulty string from :pymeth:`estimate_difficulty`.

        Returns
        -------
        PipelineConfig
        """
        if difficulty == "easy":
            return PipelineConfig(
                model_tier="A",
                run_base_rate=True,
                run_evidence_scoring=True,
                run_calibration=True,
                run_scenario_shock=domain == "policy",
                escalation_allowed=False,
                max_evidence_items=5,
                expected_input_tokens=1000,
                expected_output_tokens=300,
                rationale=(
                    f"Easy {domain} question: Tier A with base rate and "
                    f"light evidence scoring is sufficient."
                ),
            )
        elif difficulty == "medium":
            return PipelineConfig(
                model_tier="A",
                run_base_rate=True,
                run_evidence_scoring=True,
                run_calibration=True,
                run_scenario_shock=True,
                escalation_allowed=True,
                max_evidence_items=10,
                expected_input_tokens=2000,
                expected_output_tokens=600,
                rationale=(
                    f"Medium {domain} question: start with Tier A, allow "
                    f"escalation to Tier B if confidence is low."
                ),
            )
        else:  # hard
            return PipelineConfig(
                model_tier="B",
                run_base_rate=True,
                run_evidence_scoring=True,
                run_calibration=True,
                run_scenario_shock=True,
                escalation_allowed=True,
                max_evidence_items=20,
                expected_input_tokens=4000,
                expected_output_tokens=1200,
                rationale=(
                    f"Hard {domain} question: route directly to Tier B "
                    f"with full evidence pipeline and calibration."
                ),
            )

    def recommend_model_tier(self, difficulty: str) -> str:
        """Return the recommended starting model tier for a difficulty level.

        Parameters
        ----------
        difficulty:
            ``"easy"``, ``"medium"``, or ``"hard"``.

        Returns
        -------
        str
            ``"A"`` or ``"B"``.
        """
        if difficulty == "hard":
            return "B"
        return "A"

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_text(question: dict[str, Any]) -> str:
        """Concatenate all relevant text fields from a question dict."""
        parts: list[str] = []
        for key in ("title", "description", "target_metric", "resolution_criteria"):
            val = question.get(key)
            if val:
                parts.append(str(val))
        return " ".join(parts)
