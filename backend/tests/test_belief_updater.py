"""Tests for the BeliefUpdater engine.

Covers logit/inv_logit round-tripping, binary and continuous updates,
clamping behaviour, safeguard limits, and sequential batch updates.
"""

from __future__ import annotations

import math
import uuid

import pytest

from app.services.belief_updater import (
    DIRECTION_SIGN,
    PROB_CEIL,
    PROB_FLOOR,
    BeliefUpdater,
)


@pytest.fixture()
def updater() -> BeliefUpdater:
    return BeliefUpdater()


# ------------------------------------------------------------------
# Logit helpers
# ------------------------------------------------------------------

class TestLogitInvLogit:
    """Verify logit <-> inv_logit are proper inverses."""

    @pytest.mark.parametrize("p", [0.01, 0.1, 0.25, 0.5, 0.75, 0.9, 0.99])
    def test_logit_inv_logit_roundtrip(self, updater: BeliefUpdater, p: float):
        """inv_logit(logit(p)) should return the original p."""
        result = updater.inv_logit(updater.logit(p))
        assert result == pytest.approx(p, abs=1e-10)

    def test_logit_of_half_is_zero(self, updater: BeliefUpdater):
        assert updater.logit(0.5) == pytest.approx(0.0, abs=1e-12)

    def test_inv_logit_of_zero_is_half(self, updater: BeliefUpdater):
        assert updater.inv_logit(0.0) == pytest.approx(0.5, abs=1e-12)

    def test_logit_rejects_zero(self, updater: BeliefUpdater):
        with pytest.raises(ValueError):
            updater.logit(0.0)

    def test_logit_rejects_one(self, updater: BeliefUpdater):
        with pytest.raises(ValueError):
            updater.logit(1.0)

    def test_inv_logit_overflow_protection(self, updater: BeliefUpdater):
        """Extreme log-odds should not raise but saturate to 0 or 1."""
        assert updater.inv_logit(1000.0) == 1.0
        assert updater.inv_logit(-1000.0) == 0.0


# ------------------------------------------------------------------
# Binary update
# ------------------------------------------------------------------

class TestUpdateBinary:
    """Binary Bayesian updates via log-odds shifting."""

    def test_update_binary_with_positive_evidence(self, updater: BeliefUpdater):
        """Positive evidence starting from 0.5 should raise the posterior."""
        evidence = [{
            "composite_weight": 0.8,
            "directional_effect": "positive",
            "expected_magnitude": 0.6,
            "uncertainty": 0.3,
        }]
        result = updater.update_binary(prior_prob=0.5, evidence_scores=evidence)
        assert result.posterior_prob > 0.5
        assert result.prior_prob == pytest.approx(0.5, abs=1e-10)

    def test_update_binary_with_negative_evidence(self, updater: BeliefUpdater):
        """Negative evidence starting from 0.5 should lower the posterior."""
        evidence = [{
            "composite_weight": 0.8,
            "directional_effect": "negative",
            "expected_magnitude": 0.6,
            "uncertainty": 0.3,
        }]
        result = updater.update_binary(prior_prob=0.5, evidence_scores=evidence)
        assert result.posterior_prob < 0.5

    def test_update_binary_clamping(self, updater: BeliefUpdater):
        """Extreme evidence should not push the posterior outside [PROB_FLOOR, PROB_CEIL]."""
        # Very strong positive evidence on an already-high prior.
        evidence = [{
            "composite_weight": 1.0,
            "directional_effect": "positive",
            "expected_magnitude": 1.0,
            "uncertainty": 0.0,
        }]
        result = updater.update_binary(prior_prob=0.98, evidence_scores=evidence)
        assert result.posterior_prob <= PROB_CEIL
        assert result.posterior_prob >= PROB_FLOOR

        # Very strong negative evidence on a low prior.
        evidence_neg = [{
            "composite_weight": 1.0,
            "directional_effect": "negative",
            "expected_magnitude": 1.0,
            "uncertainty": 0.0,
        }]
        result_neg = updater.update_binary(
            prior_prob=0.02, evidence_scores=evidence_neg
        )
        assert result_neg.posterior_prob >= PROB_FLOOR
        assert result_neg.posterior_prob <= PROB_CEIL

    def test_neutral_evidence_no_change(self, updater: BeliefUpdater):
        """Neutral evidence should leave the prior unchanged."""
        evidence = [{
            "composite_weight": 0.9,
            "directional_effect": "neutral",
            "expected_magnitude": 0.8,
            "uncertainty": 0.2,
        }]
        result = updater.update_binary(prior_prob=0.6, evidence_scores=evidence)
        assert result.posterior_prob == pytest.approx(0.6, abs=1e-10)

    def test_ambiguous_evidence_no_change(self, updater: BeliefUpdater):
        """Ambiguous evidence maps to sign=0 and should not change the prior."""
        evidence = [{
            "composite_weight": 0.9,
            "directional_effect": "ambiguous",
            "expected_magnitude": 0.8,
            "uncertainty": 0.2,
        }]
        result = updater.update_binary(prior_prob=0.6, evidence_scores=evidence)
        assert result.posterior_prob == pytest.approx(0.6, abs=1e-10)


# ------------------------------------------------------------------
# Safeguard
# ------------------------------------------------------------------

class TestSafeguard:
    """Verify the safeguard prevents excessively large shifts."""

    def test_safeguard_limits_large_shifts(self, updater: BeliefUpdater):
        """A proposed shift of 0.5 with max_shift=0.15 should be capped."""
        capped = updater.safeguard_update(
            old_value=0.4,
            new_value=0.9,
            max_shift=0.15,
        )
        assert capped == pytest.approx(0.55, abs=1e-10)

    def test_safeguard_allows_small_shifts(self, updater: BeliefUpdater):
        """A shift within the allowed range should pass through unchanged."""
        result = updater.safeguard_update(
            old_value=0.5,
            new_value=0.6,
            max_shift=0.15,
        )
        assert result == pytest.approx(0.6, abs=1e-10)

    def test_safeguard_negative_direction(self, updater: BeliefUpdater):
        """Safeguard should also cap large negative shifts."""
        result = updater.safeguard_update(
            old_value=0.5,
            new_value=0.1,
            max_shift=0.15,
        )
        assert result == pytest.approx(0.35, abs=1e-10)


# ------------------------------------------------------------------
# Continuous update
# ------------------------------------------------------------------

class TestUpdateContinuous:
    """Continuous distribution updates (mean shift + uncertainty change)."""

    def test_update_continuous_shifts_mean(self, updater: BeliefUpdater):
        """Positive evidence should shift the mean upwards."""
        evidence = [{
            "composite_weight": 0.8,
            "directional_effect": "positive",
            "expected_magnitude": 0.5,
            "uncertainty": 0.3,
        }]
        result = updater.update_continuous(
            prior_mean=1500.0,
            prior_std=100.0,
            evidence_scores=evidence,
        )
        assert result.posterior_mean > result.prior_mean
        assert result.mean_shift > 0

    def test_update_continuous_negative_shifts_mean_down(self, updater: BeliefUpdater):
        """Negative evidence should shift the mean downwards."""
        evidence = [{
            "composite_weight": 0.7,
            "directional_effect": "negative",
            "expected_magnitude": 0.6,
            "uncertainty": 0.4,
        }]
        result = updater.update_continuous(
            prior_mean=1500.0,
            prior_std=100.0,
            evidence_scores=evidence,
        )
        assert result.posterior_mean < result.prior_mean

    def test_update_continuous_widens_uncertainty(self, updater: BeliefUpdater):
        """Uncertain evidence (uncertainty > 0.5) should widen the std."""
        evidence = [{
            "composite_weight": 0.8,
            "directional_effect": "positive",
            "expected_magnitude": 0.5,
            "uncertainty": 0.8,  # high uncertainty
        }]
        result = updater.update_continuous(
            prior_mean=1500.0,
            prior_std=100.0,
            evidence_scores=evidence,
        )
        assert result.posterior_std > result.prior_std
        assert result.std_ratio > 1.0

    def test_update_continuous_narrows_uncertainty(self, updater: BeliefUpdater):
        """Precise evidence (uncertainty < 0.5) should narrow the std."""
        evidence = [{
            "composite_weight": 0.8,
            "directional_effect": "positive",
            "expected_magnitude": 0.5,
            "uncertainty": 0.1,  # low uncertainty
        }]
        result = updater.update_continuous(
            prior_mean=1500.0,
            prior_std=100.0,
            evidence_scores=evidence,
        )
        assert result.posterior_std < result.prior_std
        assert result.std_ratio < 1.0


# ------------------------------------------------------------------
# Batch update
# ------------------------------------------------------------------

class TestBatchUpdate:
    """Sequential application of multiple evidence items."""

    def test_batch_update_sequential(self, updater: BeliefUpdater):
        """Each step's posterior becomes the next step's prior."""
        run_id = uuid.uuid4()
        items = [
            {
                "evidence_item_id": uuid.uuid4(),
                "evidence_score": {
                    "composite_weight": 0.7,
                    "directional_effect": "positive",
                    "expected_magnitude": 0.5,
                    "uncertainty": 0.3,
                },
            },
            {
                "evidence_item_id": uuid.uuid4(),
                "evidence_score": {
                    "composite_weight": 0.6,
                    "directional_effect": "negative",
                    "expected_magnitude": 0.4,
                    "uncertainty": 0.4,
                },
            },
            {
                "evidence_item_id": uuid.uuid4(),
                "evidence_score": {
                    "composite_weight": 0.9,
                    "directional_effect": "positive",
                    "expected_magnitude": 0.7,
                    "uncertainty": 0.2,
                },
            },
        ]

        final_value, records = updater.batch_update(
            forecast_run_id=run_id,
            target_type="binary",
            prior_value=0.5,
            evidence_items_with_scores=items,
        )

        # Should have produced three update records.
        assert len(records) == 3

        # Update orders should be sequential.
        assert [r.update_order for r in records] == [1, 2, 3]

        # Each record's posterior should match the next record's prior.
        for i in range(len(records) - 1):
            assert records[i].posterior_value == pytest.approx(
                records[i + 1].prior_value, abs=1e-10
            )

        # The final posterior should match the returned value.
        assert records[-1].posterior_value == pytest.approx(final_value, abs=1e-10)

        # With net positive evidence (two positive, one negative), the
        # final value should be above the starting prior of 0.5.
        assert final_value > 0.5

    def test_batch_update_empty_evidence(self, updater: BeliefUpdater):
        """No evidence should return the prior unchanged with no records."""
        final_value, records = updater.batch_update(
            forecast_run_id=uuid.uuid4(),
            target_type="binary",
            prior_value=0.65,
            evidence_items_with_scores=[],
        )
        assert final_value == pytest.approx(0.65, abs=1e-10)
        assert len(records) == 0
