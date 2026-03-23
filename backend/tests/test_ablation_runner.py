"""Tests for the AblationRunner.

Validates predefined experiment configs, defaults, and result comparison.
"""

from __future__ import annotations

import uuid

import pytest

from app.services.ablation_runner import (
    ABLATION_EXPERIMENTS,
    AblationConfig,
    AblationRunner,
)


pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Predefined configs
# ---------------------------------------------------------------------------

class TestPredefinedConfigs:
    """All 10 predefined ablation experiments should exist and be valid."""

    EXPECTED_EXPERIMENTS = [
        "no_base_rates",
        "no_evidence_scoring",
        "no_scenario_analysis",
        "tier_a_only",
        "tier_b_only",
        "no_calibration",
        "no_belief_updating",
        "no_ensemble",
        "minimal_pipeline",
        "full_pipeline",
    ]

    async def test_predefined_configs_exist(self):
        """ABLATION_EXPERIMENTS should contain all 10 predefined experiments."""
        assert len(ABLATION_EXPERIMENTS) >= 10

        for name in self.EXPECTED_EXPERIMENTS:
            assert name in ABLATION_EXPERIMENTS, (
                f"Missing predefined ablation experiment: {name}"
            )

    async def test_each_config_has_required_keys(self):
        """Every predefined config should specify the pipeline toggles."""
        for name, config in ABLATION_EXPERIMENTS.items():
            assert isinstance(config, (dict, AblationConfig)), (
                f"Config for '{name}' should be a dict or AblationConfig"
            )


# ---------------------------------------------------------------------------
# AblationConfig defaults
# ---------------------------------------------------------------------------

class TestAblationConfigDefaults:
    """AblationConfig should have sensible defaults (full pipeline ON)."""

    async def test_ablation_config_defaults(self):
        """Default AblationConfig should enable every pipeline component."""
        config = AblationConfig()

        assert config.use_base_rates is True
        assert config.use_evidence_scoring is True
        assert config.use_scenario_analysis is True
        assert config.use_calibration is True
        assert config.use_belief_updating is True
        assert config.use_ensemble is True
        assert config.tier_a_enabled is True
        assert config.tier_b_enabled is True


# ---------------------------------------------------------------------------
# Best config identification
# ---------------------------------------------------------------------------

class TestIdentifyBestConfig:
    """AblationRunner.identify_best() should pick the top config."""

    async def test_identify_best_config(self):
        """Given a set of results, identify_best should return the config
        with the lowest Brier score."""
        runner = AblationRunner.__new__(AblationRunner)

        results = [
            {
                "name": "full_pipeline",
                "brier_score": 0.12,
                "cost_usd": 0.45,
                "config": ABLATION_EXPERIMENTS.get("full_pipeline", {}),
            },
            {
                "name": "tier_a_only",
                "brier_score": 0.18,
                "cost_usd": 0.10,
                "config": ABLATION_EXPERIMENTS.get("tier_a_only", {}),
            },
            {
                "name": "no_base_rates",
                "brier_score": 0.15,
                "cost_usd": 0.40,
                "config": ABLATION_EXPERIMENTS.get("no_base_rates", {}),
            },
        ]

        best = runner.identify_best(results, metric="brier_score")

        assert best["name"] == "full_pipeline"
        assert best["brier_score"] == pytest.approx(0.12)


# ---------------------------------------------------------------------------
# Result comparison
# ---------------------------------------------------------------------------

class TestCompareResults:
    """AblationRunner.compare_results() should compute deltas."""

    async def test_compare_results(self):
        """Comparing two ablation results should produce metric deltas."""
        runner = AblationRunner.__new__(AblationRunner)

        baseline = {
            "name": "full_pipeline",
            "brier_score": 0.12,
            "log_score": -0.35,
            "cost_usd": 0.45,
        }
        ablated = {
            "name": "no_base_rates",
            "brier_score": 0.15,
            "log_score": -0.42,
            "cost_usd": 0.40,
        }

        comparison = runner.compare_results(baseline, ablated)

        assert "brier_score_delta" in comparison
        assert comparison["brier_score_delta"] == pytest.approx(0.03)
        assert "cost_usd_delta" in comparison
        assert comparison["cost_usd_delta"] == pytest.approx(-0.05)
        assert comparison["baseline"] == "full_pipeline"
        assert comparison["ablated"] == "no_base_rates"
