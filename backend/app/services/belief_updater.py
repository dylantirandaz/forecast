"""Bayesian belief-updating engine.

This is the **core** of the forecasting pipeline.  It takes a prior
(probability for binary outcomes, mean+std for continuous outcomes) and
sequentially incorporates scored evidence to produce a posterior.

Binary updates use the **log-odds** formulation:

    logit(p_new) = logit(p_old) + sum(weight_i * signal_i)

Continuous updates shift the prior mean proportionally to the weighted
evidence and adjust the standard deviation to reflect changed
uncertainty.
"""

from __future__ import annotations

import logging
import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Sequence

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------

@dataclass
class BinaryUpdateResult:
    """Outcome of a single binary-belief update step."""

    prior_prob: float
    posterior_prob: float
    log_odds_prior: float
    log_odds_posterior: float
    shift_applied: float
    was_clamped: bool


@dataclass
class ContinuousUpdateResult:
    """Outcome of a single continuous-belief update step."""

    prior_mean: float
    prior_std: float
    posterior_mean: float
    posterior_std: float
    mean_shift: float
    std_ratio: float


@dataclass
class ForecastUpdateRecord:
    """Plain-object mirror of the ORM ForecastUpdate for pipeline use."""

    id: uuid.UUID
    forecast_run_id: uuid.UUID
    update_order: int
    prior_value: float
    posterior_value: float
    evidence_item_id: uuid.UUID | None
    weight_applied: float
    shift_applied: float
    rationale: str
    created_at: datetime


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Hard probability bounds to prevent degenerate forecasts.
PROB_FLOOR: float = 0.01
PROB_CEIL: float = 0.99

# Maximum single-update shift (in probability space for binary,
# in standard-deviation units for continuous).
DEFAULT_MAX_SHIFT: float = 0.15

# Direction-to-sign mapping.
DIRECTION_SIGN: dict[str, float] = {
    "positive": +1.0,
    "negative": -1.0,
    "neutral": 0.0,
    "ambiguous": 0.0,
}


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class BeliefUpdater:
    """Bayesian belief-update engine for binary and continuous outcomes.

    All methods are **pure functions** (no database access).  The caller
    is responsible for persisting ``ForecastUpdate`` rows.
    """

    # ------------------------------------------------------------------
    # Logit helpers
    # ------------------------------------------------------------------

    @staticmethod
    def logit(p: float) -> float:
        """Convert a probability to log-odds.

        Parameters
        ----------
        p : float
            Probability in the open interval (0, 1).

        Returns
        -------
        float
            log(p / (1 - p))

        Raises
        ------
        ValueError
            If *p* is not in (0, 1).
        """
        if p <= 0.0 or p >= 1.0:
            raise ValueError(
                f"logit requires 0 < p < 1, got p={p}"
            )
        return math.log(p / (1.0 - p))

    @staticmethod
    def inv_logit(x: float) -> float:
        """Convert log-odds back to a probability.

        Parameters
        ----------
        x : float
            Log-odds value (any real number).

        Returns
        -------
        float
            Probability in (0, 1).
        """
        # Guard against overflow.
        if x > 500.0:
            return 1.0
        if x < -500.0:
            return 0.0
        return 1.0 / (1.0 + math.exp(-x))

    # ------------------------------------------------------------------
    # Binary update
    # ------------------------------------------------------------------

    def update_binary(
        self,
        prior_prob: float,
        evidence_scores: Sequence[dict[str, Any]],
        max_shift: float = DEFAULT_MAX_SHIFT,
    ) -> BinaryUpdateResult:
        """Apply one round of log-odds updating for a binary outcome.

        The update formula is:

            logit(p_new) = logit(p_old) + sum(weight_i * signal_i)

        where each ``signal_i`` encodes both the direction and magnitude
        of the evidence:

            signal_i = direction_sign * expected_magnitude * (1 - uncertainty)

        The final probability is clamped to ``[PROB_FLOOR, PROB_CEIL]``
        and safeguarded against excessively large single-round shifts.

        Parameters
        ----------
        prior_prob:
            Current probability estimate, in (0, 1).
        evidence_scores:
            Sequence of dicts, each with keys ``composite_weight``,
            ``directional_effect``, ``expected_magnitude``, and
            ``uncertainty``.
        max_shift:
            Maximum allowed change in probability space per update round.

        Returns
        -------
        BinaryUpdateResult
        """
        # Clamp prior into valid range for logit.
        clamped_prior = max(PROB_FLOOR, min(PROB_CEIL, prior_prob))
        lo_prior = self.logit(clamped_prior)

        total_shift = 0.0
        for score in evidence_scores:
            weight = float(score.get("composite_weight", 0.0))
            direction = DIRECTION_SIGN.get(
                score.get("directional_effect", "neutral"), 0.0
            )
            magnitude = float(score.get("expected_magnitude", 0.5))
            uncertainty = float(score.get("uncertainty", 0.5))

            # Signal: direction * magnitude, attenuated by uncertainty.
            signal = direction * magnitude * (1.0 - uncertainty)
            total_shift += weight * signal

        lo_posterior = lo_prior + total_shift
        raw_posterior = self.inv_logit(lo_posterior)

        # Safeguard: do not move more than max_shift in probability space.
        safeguarded = self.safeguard_update(
            clamped_prior, raw_posterior, max_shift
        )

        # Final clamp.
        final = max(PROB_FLOOR, min(PROB_CEIL, safeguarded))
        was_clamped = (final != raw_posterior)

        return BinaryUpdateResult(
            prior_prob=clamped_prior,
            posterior_prob=final,
            log_odds_prior=lo_prior,
            log_odds_posterior=self.logit(final),
            shift_applied=final - clamped_prior,
            was_clamped=was_clamped,
        )

    # ------------------------------------------------------------------
    # Continuous update
    # ------------------------------------------------------------------

    def update_continuous(
        self,
        prior_mean: float,
        prior_std: float,
        evidence_scores: Sequence[dict[str, Any]],
        max_shift_std: float = 2.0,
    ) -> ContinuousUpdateResult:
        """Update a continuous-valued forecast.

        Mean shift:
            shift = sum(weight_i * direction_i * magnitude_i * prior_std)

        Uncertainty update:
            new_std = prior_std * (1 + sum(uncertainty_adjustments))

        where each ``uncertainty_adjustment`` is:
            - **positive** if the evidence is ambiguous or uncertain
              (widens the interval),
            - **negative** if the evidence is precise and credible
              (narrows the interval).

        Parameters
        ----------
        prior_mean:
            Current point estimate.
        prior_std:
            Current standard deviation of the forecast distribution.
        evidence_scores:
            Same format as for :py:meth:`update_binary`.
        max_shift_std:
            Maximum allowed shift in units of ``prior_std``.

        Returns
        -------
        ContinuousUpdateResult
        """
        total_mean_shift = 0.0
        total_uncertainty_adj = 0.0

        for score in evidence_scores:
            weight = float(score.get("composite_weight", 0.0))
            direction = DIRECTION_SIGN.get(
                score.get("directional_effect", "neutral"), 0.0
            )
            magnitude = float(score.get("expected_magnitude", 0.5))
            uncertainty = float(score.get("uncertainty", 0.5))

            # Mean shift: proportional to prior_std so that evidence
            # "moves" the distribution in its own natural scale.
            total_mean_shift += weight * direction * magnitude * prior_std

            # Uncertainty adjustment: high-uncertainty or ambiguous
            # evidence widens the distribution; precise, credible
            # evidence narrows it.  The formula maps uncertainty
            # [0, 1] → adjustment in [-0.1, +0.1] per evidence item,
            # scaled by weight.
            adj = weight * (uncertainty - 0.5) * 0.2
            total_uncertainty_adj += adj

        # Clamp mean shift.
        max_abs_shift = max_shift_std * prior_std
        clamped_shift = max(-max_abs_shift, min(max_abs_shift, total_mean_shift))

        posterior_mean = prior_mean + clamped_shift

        # Std must remain positive; floor at 1% of prior.
        std_multiplier = 1.0 + total_uncertainty_adj
        std_multiplier = max(std_multiplier, 0.01)
        posterior_std = prior_std * std_multiplier

        return ContinuousUpdateResult(
            prior_mean=prior_mean,
            prior_std=prior_std,
            posterior_mean=posterior_mean,
            posterior_std=posterior_std,
            mean_shift=clamped_shift,
            std_ratio=std_multiplier,
        )

    # ------------------------------------------------------------------
    # Safeguard
    # ------------------------------------------------------------------

    @staticmethod
    def safeguard_update(
        old_value: float,
        new_value: float,
        max_shift: float = DEFAULT_MAX_SHIFT,
    ) -> float:
        """Prevent a single update from shifting the forecast too far.

        If the absolute change exceeds ``max_shift``, the new value is
        pulled back to ``old_value ± max_shift`` in the direction of the
        proposed change.

        Parameters
        ----------
        old_value:
            The value before the update.
        new_value:
            The proposed new value.
        max_shift:
            Maximum allowed absolute change.

        Returns
        -------
        float
            The (possibly capped) new value.
        """
        delta = new_value - old_value
        if abs(delta) <= max_shift:
            return new_value
        sign = 1.0 if delta > 0 else -1.0
        capped = old_value + sign * max_shift
        logger.warning(
            "Safeguard triggered: proposed shift %.4f capped to %.4f "
            "(old=%.4f, new=%.4f, capped=%.4f)",
            delta,
            sign * max_shift,
            old_value,
            new_value,
            capped,
        )
        return capped

    # ------------------------------------------------------------------
    # ORM-aware helpers
    # ------------------------------------------------------------------

    def create_forecast_update(
        self,
        forecast_run_id: uuid.UUID,
        evidence_item_id: uuid.UUID | None,
        update_order: int,
        prior_value: float,
        posterior_value: float,
        weight_applied: float,
        shift_applied: float,
        rationale: str = "",
    ) -> ForecastUpdateRecord:
        """Create a ``ForecastUpdateRecord`` (plain dataclass).

        The caller is responsible for converting this into an ORM object
        and persisting it.

        Parameters
        ----------
        forecast_run_id:
            Parent forecast run UUID.
        evidence_item_id:
            Evidence item that triggered this update (may be ``None``).
        update_order:
            Sequence number within the run.
        prior_value:
            Value before this update step.
        posterior_value:
            Value after this update step.
        weight_applied:
            Composite weight of the evidence.
        shift_applied:
            Actual shift applied (after safeguard).
        rationale:
            Human-readable explanation of the update.

        Returns
        -------
        ForecastUpdateRecord
        """
        return ForecastUpdateRecord(
            id=uuid.uuid4(),
            forecast_run_id=forecast_run_id,
            update_order=update_order,
            prior_value=prior_value,
            posterior_value=posterior_value,
            evidence_item_id=evidence_item_id,
            weight_applied=weight_applied,
            shift_applied=shift_applied,
            rationale=rationale,
            created_at=datetime.now(timezone.utc),
        )

    def batch_update(
        self,
        forecast_run_id: uuid.UUID,
        target_type: str,
        prior_value: float,
        evidence_items_with_scores: Sequence[dict[str, Any]],
        prior_std: float | None = None,
        max_shift: float = DEFAULT_MAX_SHIFT,
    ) -> tuple[float, list[ForecastUpdateRecord]]:
        """Process multiple evidence items sequentially.

        Each evidence item is applied one at a time; the posterior of one
        step becomes the prior of the next.

        Parameters
        ----------
        forecast_run_id:
            Parent forecast run UUID.
        target_type:
            ``"binary"`` or ``"continuous"``.
        prior_value:
            Starting forecast value (probability or point estimate).
        evidence_items_with_scores:
            Sequence of dicts, each containing ``"evidence_item_id"``
            (UUID or None), ``"evidence_score"`` (a dict with scoring
            fields), and an optional ``"rationale"`` string.
        prior_std:
            Required for continuous targets.
        max_shift:
            Per-step shift cap (probability space for binary, absolute
            for continuous).

        Returns
        -------
        tuple[float, list[ForecastUpdateRecord]]
            The final posterior value and the list of update records.
        """
        current_value = prior_value
        current_std = prior_std
        updates: list[ForecastUpdateRecord] = []

        for order, item in enumerate(evidence_items_with_scores, start=1):
            score_dict = item["evidence_score"]
            evidence_id = item.get("evidence_item_id")

            if target_type == "binary":
                result = self.update_binary(
                    prior_prob=current_value,
                    evidence_scores=[score_dict],
                    max_shift=max_shift,
                )
                posterior = result.posterior_prob
                shift = result.shift_applied
                weight = float(score_dict.get("composite_weight", 0.0))
            elif target_type == "continuous":
                if current_std is None:
                    raise ValueError(
                        "prior_std is required for continuous updates."
                    )
                result = self.update_continuous(
                    prior_mean=current_value,
                    prior_std=current_std,
                    evidence_scores=[score_dict],
                )
                posterior = result.posterior_mean
                current_std = result.posterior_std
                shift = result.mean_shift
                weight = float(score_dict.get("composite_weight", 0.0))
            else:
                raise ValueError(f"Unsupported target_type: {target_type}")

            rationale = item.get("rationale", "")
            if not rationale:
                direction = score_dict.get("directional_effect", "neutral")
                rationale = (
                    f"Evidence (direction={direction}, "
                    f"weight={weight:.3f}) shifted forecast by "
                    f"{shift:+.4f}."
                )

            record = self.create_forecast_update(
                forecast_run_id=forecast_run_id,
                evidence_item_id=evidence_id,
                update_order=order,
                prior_value=current_value,
                posterior_value=posterior,
                weight_applied=weight,
                shift_applied=shift,
                rationale=rationale,
            )
            updates.append(record)
            current_value = posterior

        logger.info(
            "Batch update complete for run %s: %d steps, "
            "prior=%.4f → posterior=%.4f",
            forecast_run_id,
            len(updates),
            prior_value,
            current_value,
        )
        return current_value, updates
