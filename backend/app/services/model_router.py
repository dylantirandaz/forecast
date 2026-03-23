"""Tiered model routing for cost-aware LLM selection.

Routes individual sub-tasks to the cheapest model capable of handling
them well, organised into two tiers:

- **Tier A** (cheap/fast): extraction, classification, summarisation.
  Default: ``gpt-4o-mini``.
- **Tier B** (strong reasoning): synthesis, causal reasoning, deep
  research.  Default: ``gpt-4o`` or ``claude-sonnet-4-6``.

The router also exposes cost-estimation helpers so callers can make
budget-aware decisions *before* invoking a model.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ModelRouter:
    """Route to appropriate model tier based on task type and budget.

    Example::

        router = ModelRouter()
        model = router.get_model("A", task_type="classification")
        est = router.estimate_cost(model, input_tokens=800, output_tokens=200)
    """

    # ------------------------------------------------------------------
    # Tier definitions
    # ------------------------------------------------------------------

    TIER_A_MODELS: dict[str, str] = {
        "default": "gpt-4o-mini",
        "extraction": "gpt-4o-mini",
        "classification": "gpt-4o-mini",
        "summarization": "gpt-4o-mini",
        "base_rate_lookup": "gpt-4o-mini",
        "difficulty_estimation": "gpt-4o-mini",
    }

    TIER_B_MODELS: dict[str, str] = {
        "default": "gpt-4o",
        "synthesis": "claude-sonnet-4-6",
        "causal_reasoning": "claude-sonnet-4-6",
        "deep_research": "gpt-4o",
        "disagreement_resolution": "claude-sonnet-4-6",
        "scenario_analysis": "gpt-4o",
    }

    # Cost per 1 K tokens (approximate as of early 2026).
    MODEL_COSTS: dict[str, dict[str, float]] = {
        "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
        "gpt-4o": {"input": 0.0025, "output": 0.01},
        "claude-sonnet-4-6": {"input": 0.003, "output": 0.015},
        "claude-haiku-4-5-20251001": {"input": 0.0008, "output": 0.004},
    }

    # Ordered cheapest → most expensive for each task class.
    _MODEL_QUALITY_ORDER: list[str] = [
        "gpt-4o-mini",
        "claude-haiku-4-5-20251001",
        "gpt-4o",
        "claude-sonnet-4-6",
    ]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_model(self, tier: str, task_type: str = "default") -> str:
        """Return the model name for a given tier and task type.

        Parameters
        ----------
        tier:
            ``"A"`` (cheap) or ``"B"`` (strong).
        task_type:
            Sub-task label (e.g. ``"classification"``, ``"synthesis"``).
            Falls back to ``"default"`` if the task is not explicitly
            mapped.

        Returns
        -------
        str
            Model identifier string.
        """
        tier = tier.upper()
        if tier == "A":
            return self.TIER_A_MODELS.get(task_type, self.TIER_A_MODELS["default"])
        elif tier == "B":
            return self.TIER_B_MODELS.get(task_type, self.TIER_B_MODELS["default"])
        else:
            logger.warning("Unknown tier '%s'; falling back to Tier A default.", tier)
            return self.TIER_A_MODELS["default"]

    def estimate_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """Estimate the USD cost for a single LLM call.

        Parameters
        ----------
        model:
            Model identifier (key in :pyattr:`MODEL_COSTS`).
        input_tokens:
            Expected prompt token count.
        output_tokens:
            Expected completion token count.

        Returns
        -------
        float
            Estimated cost in USD.
        """
        costs = self.MODEL_COSTS.get(model)
        if costs is None:
            logger.warning(
                "Unknown model '%s'; using gpt-4o-mini rates for estimation.",
                model,
            )
            costs = self.MODEL_COSTS["gpt-4o-mini"]

        return (input_tokens / 1000.0) * costs["input"] + (
            output_tokens / 1000.0
        ) * costs["output"]

    def get_cheapest_model(self, task_type: str = "default") -> str:
        """Return the cheapest available model suitable for *task_type*.

        The cheapest model is always in Tier A.  If *task_type* has an
        explicit Tier A mapping, that model is returned; otherwise the
        global cheapest model is returned.

        Parameters
        ----------
        task_type:
            Sub-task label.

        Returns
        -------
        str
        """
        if task_type in self.TIER_A_MODELS:
            return self.TIER_A_MODELS[task_type]
        # Return the cheapest overall.
        return self._MODEL_QUALITY_ORDER[0]

    def get_best_model(self, task_type: str = "default") -> str:
        """Return the highest-quality model for *task_type*.

        Checks Tier B first; falls back to Tier A if no Tier B mapping
        exists.

        Parameters
        ----------
        task_type:
            Sub-task label.

        Returns
        -------
        str
        """
        if task_type in self.TIER_B_MODELS:
            return self.TIER_B_MODELS[task_type]
        if task_type in self.TIER_A_MODELS:
            return self.TIER_A_MODELS[task_type]
        return self._MODEL_QUALITY_ORDER[-1]

    def get_model_within_budget(
        self,
        task_type: str,
        remaining_budget_usd: float,
        estimated_input_tokens: int = 1500,
        estimated_output_tokens: int = 500,
    ) -> str | None:
        """Return the best model whose estimated cost fits the budget.

        Iterates from strongest to weakest model and returns the first
        that fits.  Returns ``None`` if even the cheapest model would
        exceed the budget.

        Parameters
        ----------
        task_type:
            Sub-task label (used to pick the ideal model per tier).
        remaining_budget_usd:
            Maximum USD allowance for this call.
        estimated_input_tokens:
            Expected prompt tokens.
        estimated_output_tokens:
            Expected completion tokens.

        Returns
        -------
        str or None
        """
        # Try from most expensive to cheapest.
        for model in reversed(self._MODEL_QUALITY_ORDER):
            cost = self.estimate_cost(model, estimated_input_tokens, estimated_output_tokens)
            if cost <= remaining_budget_usd:
                return model
        return None

    def get_tier_for_model(self, model: str) -> str:
        """Return ``"A"`` or ``"B"`` depending on which tier a model belongs to.

        If the model appears in both tiers, Tier B takes precedence.
        If unknown, returns ``"A"`` as a safe default.

        Parameters
        ----------
        model:
            Model identifier.

        Returns
        -------
        str
        """
        if model in self.TIER_B_MODELS.values():
            return "B"
        return "A"

    def list_models(self) -> dict[str, Any]:
        """Return a summary of all available models with cost info.

        Returns
        -------
        dict
            Keys ``"tier_a"``, ``"tier_b"``, ``"costs"``.
        """
        return {
            "tier_a": dict(self.TIER_A_MODELS),
            "tier_b": dict(self.TIER_B_MODELS),
            "costs": dict(self.MODEL_COSTS),
        }
