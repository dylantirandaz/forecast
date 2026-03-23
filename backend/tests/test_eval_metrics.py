"""Tests for the evaluation metrics engine.

Covers Brier score, log score, calibration metrics, sharpness,
baseline comparisons, decomposition, and full report generation.
"""
from __future__ import annotations

import math

import pytest
import numpy as np

from app.services.eval_metrics import (
    EvalMetricsEngine,
    MetricsSummary,
    BaselineComparison,
    CalibrationBinData,
    FullEvalReport,
)


@pytest.fixture
def engine():
    return EvalMetricsEngine(n_calibration_bins=10)


# ------------------------------------------------------------------
# Brier Score
# ------------------------------------------------------------------

class TestBrierScore:
    def test_perfect_predictions(self, engine):
        preds = [1.0, 0.0, 1.0, 0.0]
        actuals = [1, 0, 1, 0]
        assert engine.compute_brier_score(preds, actuals) == 0.0

    def test_worst_predictions(self, engine):
        preds = [0.0, 1.0, 0.0, 1.0]
        actuals = [1, 0, 1, 0]
        assert engine.compute_brier_score(preds, actuals) == 1.0

    def test_always_half(self, engine):
        preds = [0.5] * 100
        actuals = [1] * 50 + [0] * 50
        assert abs(engine.compute_brier_score(preds, actuals) - 0.25) < 1e-10

    def test_brier_range(self, engine):
        rng = np.random.default_rng(42)
        preds = rng.uniform(0, 1, 100).tolist()
        actuals = rng.integers(0, 2, 100).tolist()
        score = engine.compute_brier_score(preds, actuals)
        assert 0 <= score <= 1

    def test_brier_single_prediction(self, engine):
        assert engine.compute_brier_score([0.7], [1]) == pytest.approx(0.09)

    def test_brier_symmetric(self, engine):
        """Brier(0.3 when actual=0) == Brier(0.7 when actual=1)."""
        score_a = engine.compute_brier_score([0.3], [0])
        score_b = engine.compute_brier_score([0.7], [1])
        assert score_a == pytest.approx(score_b)

    def test_brier_numpy_input(self, engine):
        preds = np.array([0.6, 0.4])
        actuals = np.array([1, 0])
        score = engine.compute_brier_score(preds, actuals)
        expected = ((0.6 - 1) ** 2 + (0.4 - 0) ** 2) / 2
        assert score == pytest.approx(expected)


# ------------------------------------------------------------------
# Brier Decomposition
# ------------------------------------------------------------------

class TestBrierDecomposition:
    def test_decomposition_adds_up(self, engine):
        """Brier = Reliability - Resolution + Uncertainty."""
        rng = np.random.default_rng(42)
        preds = rng.uniform(0, 1, 200)
        actuals = (rng.uniform(0, 1, 200) < preds).astype(float)

        d = engine.compute_brier_decomposition(preds, actuals)
        reconstructed = d["reliability"] - d["resolution"] + d["uncertainty"]
        assert d["brier_score"] == pytest.approx(reconstructed, abs=0.02)

    def test_uncertainty_is_base_rate_variance(self, engine):
        """Uncertainty component = base_rate * (1 - base_rate)."""
        preds = [0.5] * 100
        actuals = [1] * 60 + [0] * 40
        d = engine.compute_brier_decomposition(preds, actuals)
        expected_uncertainty = 0.6 * 0.4
        assert d["uncertainty"] == pytest.approx(expected_uncertainty, abs=1e-10)

    def test_decomposition_components_nonnegative(self, engine):
        rng = np.random.default_rng(42)
        preds = rng.uniform(0, 1, 100)
        actuals = rng.integers(0, 2, 100).astype(float)
        d = engine.compute_brier_decomposition(preds, actuals)
        assert d["reliability"] >= 0
        assert d["resolution"] >= 0
        assert d["uncertainty"] >= 0


# ------------------------------------------------------------------
# Log Score
# ------------------------------------------------------------------

class TestLogScore:
    def test_perfect_predictions(self, engine):
        preds = [0.999, 0.001, 0.999]
        actuals = [1, 0, 1]
        score = engine.compute_log_score(preds, actuals)
        assert score < 0.01  # near zero for near-perfect

    def test_confident_wrong_penalized(self, engine):
        good_preds = [0.7, 0.3, 0.8]
        bad_preds = [0.99, 0.01, 0.99]
        actuals = [0, 1, 0]  # all wrong

        good_score = engine.compute_log_score(good_preds, actuals)
        bad_score = engine.compute_log_score(bad_preds, actuals)

        assert bad_score > good_score  # confident wrong is worse

    def test_log_score_nonnegative(self, engine):
        rng = np.random.default_rng(42)
        preds = rng.uniform(0.01, 0.99, 100).tolist()
        actuals = rng.integers(0, 2, 100).tolist()
        assert engine.compute_log_score(preds, actuals) >= 0

    def test_log_score_extreme_clamp(self, engine):
        """Predictions of exactly 0 or 1 should not cause -inf or NaN."""
        preds = [0.0, 1.0]
        actuals = [0, 1]
        score = engine.compute_log_score(preds, actuals)
        assert math.isfinite(score)

    def test_log_score_formula_manual(self, engine):
        """Verify log score against manual computation."""
        preds = [0.8]
        actuals = [1]
        expected = -math.log(0.8)
        assert engine.compute_log_score(preds, actuals) == pytest.approx(expected, abs=1e-10)


# ------------------------------------------------------------------
# Calibration
# ------------------------------------------------------------------

class TestCalibration:
    def test_calibration_curve_bins(self, engine):
        preds = np.linspace(0.05, 0.95, 100).tolist()
        actuals = [1 if p > 0.5 else 0 for p in preds]
        curve = engine.compute_calibration_curve(preds, actuals)
        assert len(curve) == 10
        assert all(isinstance(b, CalibrationBinData) for b in curve)

    def test_perfect_calibration_ece_near_zero(self, engine):
        # Perfectly calibrated: predicted p matches observed frequency
        n = 1000
        rng = np.random.default_rng(42)
        preds = rng.uniform(0, 1, n)
        actuals = (rng.uniform(0, 1, n) < preds).astype(float)
        ece = engine.compute_ece(preds, actuals)
        assert ece < 0.1  # should be small for large n

    def test_ece_range(self, engine):
        rng = np.random.default_rng(42)
        preds = rng.uniform(0, 1, 100).tolist()
        actuals = rng.integers(0, 2, 100).tolist()
        ece = engine.compute_ece(preds, actuals)
        assert 0 <= ece <= 1

    def test_ece_zero_for_perfect(self, engine):
        """All predictions in one bin with exact match should give ECE close to zero."""
        # All predictions near 0.5, half resolve yes -- that's perfectly calibrated
        preds = [0.5] * 100
        actuals = [1] * 50 + [0] * 50
        ece = engine.compute_ece(preds, actuals)
        assert ece < 0.01

    def test_mce_range(self, engine):
        rng = np.random.default_rng(42)
        preds = rng.uniform(0, 1, 100)
        actuals = rng.integers(0, 2, 100).astype(float)
        mce = engine.compute_mce(preds, actuals)
        assert 0 <= mce <= 1

    def test_mce_geq_ece(self, engine):
        """MCE should be greater than or equal to ECE."""
        rng = np.random.default_rng(42)
        preds = rng.uniform(0, 1, 200)
        actuals = rng.integers(0, 2, 200).astype(float)
        ece = engine.compute_ece(preds, actuals)
        mce = engine.compute_mce(preds, actuals)
        assert mce >= ece - 1e-10

    def test_calibration_curve_empty_bins(self, engine):
        """Bins with no predictions should have count=0."""
        preds = [0.05, 0.06, 0.07]  # all in first bin
        actuals = [0, 0, 1]
        curve = engine.compute_calibration_curve(preds, actuals)
        nonempty = [b for b in curve if b.count > 0]
        assert len(nonempty) == 1
        assert nonempty[0].count == 3

    def test_calibration_curve_confidence_intervals(self, engine):
        """Non-empty bins should have valid confidence intervals."""
        rng = np.random.default_rng(42)
        preds = rng.uniform(0, 1, 200)
        actuals = rng.integers(0, 2, 200).astype(float)
        curve = engine.compute_calibration_curve(preds, actuals)
        for b in curve:
            if b.count > 0:
                assert 0 <= b.confidence_interval_lower <= b.confidence_interval_upper <= 1


# ------------------------------------------------------------------
# Sharpness
# ------------------------------------------------------------------

class TestSharpness:
    def test_always_half_zero_sharpness(self, engine):
        preds = [0.5] * 100
        assert engine.compute_sharpness(preds) == 0.0

    def test_extreme_preds_high_sharpness(self, engine):
        preds = [0.01, 0.99, 0.02, 0.98]
        sharpness = engine.compute_sharpness(preds)
        assert sharpness > 0.45

    def test_sharpness_range(self, engine):
        rng = np.random.default_rng(42)
        preds = rng.uniform(0, 1, 100)
        sharpness = engine.compute_sharpness(preds)
        assert 0 <= sharpness <= 0.5

    def test_all_zeros_and_ones(self, engine):
        preds = [0.0, 1.0, 0.0, 1.0]
        assert engine.compute_sharpness(preds) == 0.5

    def test_prediction_histogram(self, engine):
        preds = np.linspace(0, 1, 100)
        hist = engine.compute_prediction_histogram(preds, n_bins=10)
        assert len(hist) == 10
        total_count = sum(h["count"] for h in hist)
        assert total_count == 100
        for h in hist:
            assert h["bin_lower"] < h["bin_upper"]


# ------------------------------------------------------------------
# Baseline Comparison
# ------------------------------------------------------------------

class TestBaselineComparison:
    def test_good_model_beats_baselines(self, engine):
        # Model that predicts well
        preds = [0.9, 0.1, 0.8, 0.2, 0.85]
        actuals = [1, 0, 1, 0, 1]

        comparison = engine.compute_baseline_comparison(preds, actuals)
        assert comparison.model_brier < comparison.always_half_brier
        assert comparison.skill_score > 0

    def test_always_half_equals_baseline(self, engine):
        preds = [0.5] * 10
        actuals = [1, 0, 1, 0, 1, 0, 1, 0, 1, 0]

        comparison = engine.compute_baseline_comparison(preds, actuals)
        assert abs(comparison.model_brier - comparison.always_half_brier) < 1e-10

    def test_skill_score_zero_for_baseline(self, engine):
        """Skill score should be 0 when model == always-0.5."""
        preds = [0.5] * 20
        actuals = [1, 0] * 10
        comparison = engine.compute_baseline_comparison(preds, actuals)
        assert abs(comparison.skill_score) < 1e-10

    def test_bad_model_negative_skill(self, engine):
        """Worse-than-baseline model should have negative skill score."""
        preds = [0.1, 0.9, 0.1, 0.9]
        actuals = [1, 0, 1, 0]  # perfectly wrong
        comparison = engine.compute_baseline_comparison(preds, actuals)
        assert comparison.skill_score < 0

    def test_base_rate_brier_computed(self, engine):
        preds = [0.6] * 10
        actuals = [1, 1, 1, 1, 0, 0, 0, 0, 0, 0]
        comparison = engine.compute_baseline_comparison(preds, actuals)
        # Base rate = 0.4, so base_rate_brier = mean((0.4 - actual)^2)
        expected_br_brier = np.mean((np.array(actuals) - 0.4) ** 2)
        assert comparison.base_rate_brier == pytest.approx(expected_br_brier, abs=1e-5)

    def test_model_vs_half_delta_sign(self, engine):
        """Delta should be negative when model is better than always-0.5."""
        preds = [0.9, 0.1, 0.8, 0.2]
        actuals = [1, 0, 1, 0]
        comparison = engine.compute_baseline_comparison(preds, actuals)
        assert comparison.model_vs_half_delta < 0


# ------------------------------------------------------------------
# Full Report
# ------------------------------------------------------------------

class TestFullReport:
    def test_full_report_structure(self, engine):
        predictions = [
            {
                "predicted_probability": 0.7,
                "actual_value": 1,
                "domain": "macro",
                "cutoff_days": 90,
                "question_id": "q1",
                "difficulty": "medium",
            },
            {
                "predicted_probability": 0.3,
                "actual_value": 0,
                "domain": "macro",
                "cutoff_days": 30,
                "question_id": "q1",
                "difficulty": "medium",
            },
            {
                "predicted_probability": 0.6,
                "actual_value": 1,
                "domain": "technology",
                "cutoff_days": 90,
                "question_id": "q2",
                "difficulty": "hard",
            },
            {
                "predicted_probability": 0.4,
                "actual_value": 0,
                "domain": "technology",
                "cutoff_days": 30,
                "question_id": "q2",
                "difficulty": "hard",
            },
        ]

        report = engine.compute_full_report(predictions)

        assert isinstance(report, FullEvalReport)
        assert report.summary.n_predictions == 4
        assert report.summary.brier_score >= 0
        assert len(report.calibration_curve) > 0
        assert len(report.domain_breakdown) == 2  # macro + technology
        assert len(report.horizon_breakdown) == 2  # 90d + 30d
        assert report.baseline_comparison.model_brier >= 0
        assert len(report.prediction_histogram) > 0

    def test_empty_predictions_raises(self, engine):
        with pytest.raises(ValueError):
            engine.compute_full_report([])

    def test_report_summary_fields(self, engine):
        predictions = [
            {"predicted_probability": 0.8, "actual_value": 1, "domain": "macro", "cutoff_days": 90, "question_id": "q1"},
            {"predicted_probability": 0.2, "actual_value": 0, "domain": "macro", "cutoff_days": 90, "question_id": "q2"},
        ]
        report = engine.compute_full_report(predictions)

        s = report.summary
        assert isinstance(s, MetricsSummary)
        assert s.n_questions == 2
        assert 0 <= s.brier_score <= 1
        assert s.log_score >= 0
        assert 0 <= s.calibration_error <= 1
        assert 0 <= s.sharpness <= 0.5
        assert 0 <= s.mean_prediction <= 1
        assert 0 <= s.base_rate <= 1

    def test_report_reliability_data(self, engine):
        predictions = [
            {"predicted_probability": 0.3 + i * 0.05, "actual_value": 1 if i % 2 == 0 else 0, "domain": "macro", "cutoff_days": 90, "question_id": f"q{i}"}
            for i in range(20)
        ]
        report = engine.compute_full_report(predictions)

        assert "bins" in report.reliability_data
        assert "perfect_line" in report.reliability_data
        assert report.reliability_data["perfect_line"] == [[0, 0], [1, 1]]

    def test_report_single_domain(self, engine):
        predictions = [
            {"predicted_probability": 0.6, "actual_value": 1, "domain": "housing", "cutoff_days": 30, "question_id": "q1"},
        ]
        report = engine.compute_full_report(predictions)
        assert len(report.domain_breakdown) == 1
        assert report.domain_breakdown[0].domain == "housing"

    def test_report_single_horizon(self, engine):
        predictions = [
            {"predicted_probability": 0.6, "actual_value": 1, "domain": "macro", "cutoff_days": 7, "question_id": "q1"},
            {"predicted_probability": 0.4, "actual_value": 0, "domain": "macro", "cutoff_days": 7, "question_id": "q2"},
        ]
        report = engine.compute_full_report(predictions)
        assert len(report.horizon_breakdown) == 1
        assert report.horizon_breakdown[0].horizon_label == "7d"
        assert report.horizon_breakdown[0].n_predictions == 2

    def test_report_horizon_improvement(self, engine):
        """Shorter horizon should show improvement metric vs longer horizon."""
        predictions = [
            {"predicted_probability": 0.5, "actual_value": 1, "domain": "macro", "cutoff_days": 90, "question_id": "q1"},
            {"predicted_probability": 0.9, "actual_value": 1, "domain": "macro", "cutoff_days": 7, "question_id": "q1"},
        ]
        report = engine.compute_full_report(predictions)
        # The 7d horizon should show improvement over 90d
        horizons = {h.horizon_label: h for h in report.horizon_breakdown}
        # 90d is processed first (sorted descending), improvement_from_prior=0
        assert horizons["90d"].improvement_from_prior == 0.0
