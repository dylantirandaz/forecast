"""Tests for baseline predictors.

Covers AlwaysHalfPredictor, BaseRatePredictor, NaiveDirectionalPredictor,
DifficultyAwareBaseRatePredictor, and the BASELINE_PREDICTORS registry.
"""
from __future__ import annotations

import pytest

from app.services.baseline_predictors import (
    AlwaysHalfPredictor,
    BaseRatePredictor,
    NaiveDirectionalPredictor,
    DifficultyAwareBaseRatePredictor,
    BaselinePrediction,
    BASELINE_PREDICTORS,
)


# ------------------------------------------------------------------
# AlwaysHalfPredictor
# ------------------------------------------------------------------

class TestAlwaysHalf:
    def test_always_returns_half(self):
        predictor = AlwaysHalfPredictor()
        q = {"id": "1", "question_text": "Will it rain?", "domain": "other"}
        pred = predictor.predict(q)
        assert pred.predicted_probability == 0.5

    def test_batch_all_half(self):
        predictor = AlwaysHalfPredictor()
        questions = [
            {"id": str(i), "question_text": f"Q{i}", "domain": "other"}
            for i in range(10)
        ]
        preds = predictor.predict_batch(questions)
        assert len(preds) == 10
        assert all(p.predicted_probability == 0.5 for p in preds)

    def test_returns_baseline_prediction(self):
        predictor = AlwaysHalfPredictor()
        pred = predictor.predict({"id": "x"})
        assert isinstance(pred, BaselinePrediction)

    def test_model_name(self):
        predictor = AlwaysHalfPredictor()
        pred = predictor.predict({"id": "x"})
        assert pred.model_name == "always_0.5"

    def test_missing_id_handled(self):
        predictor = AlwaysHalfPredictor()
        pred = predictor.predict({"question_text": "No id?"})
        assert pred.predicted_probability == 0.5
        assert pred.question_id == ""

    def test_ignores_domain(self):
        predictor = AlwaysHalfPredictor()
        for domain in ["macro", "technology", "housing", "other"]:
            pred = predictor.predict({"id": "1", "domain": domain})
            assert pred.predicted_probability == 0.5


# ------------------------------------------------------------------
# BaseRatePredictor
# ------------------------------------------------------------------

class TestBaseRate:
    def test_domain_specific_rates(self):
        predictor = BaseRatePredictor()
        macro_q = {"id": "1", "question_text": "GDP?", "domain": "macro"}
        tech_q = {"id": "2", "question_text": "Tech?", "domain": "technology"}

        assert (
            predictor.predict(macro_q).predicted_probability
            != predictor.predict(tech_q).predicted_probability
        )

    def test_macro_rate(self):
        predictor = BaseRatePredictor()
        pred = predictor.predict({"id": "1", "domain": "macro"})
        assert pred.predicted_probability == 0.55

    def test_technology_rate(self):
        predictor = BaseRatePredictor()
        pred = predictor.predict({"id": "1", "domain": "technology"})
        assert pred.predicted_probability == 0.40

    def test_unknown_domain_defaults(self):
        predictor = BaseRatePredictor()
        pred = predictor.predict({"id": "1", "domain": "unknown_domain"})
        assert pred.predicted_probability == 0.50

    def test_missing_domain_uses_other(self):
        predictor = BaseRatePredictor()
        pred = predictor.predict({"id": "1"})
        assert pred.predicted_probability == 0.50

    def test_calibrate_from_data(self):
        predictor = BaseRatePredictor()
        questions = [
            {"domain": "macro", "resolved_value": 1.0},
            {"domain": "macro", "resolved_value": 1.0},
            {"domain": "macro", "resolved_value": 0.0},
            {"domain": "macro", "resolved_value": 1.0},
            {"domain": "macro", "resolved_value": 0.0},
            {"domain": "macro", "resolved_value": 1.0},
        ]
        predictor.calibrate_from_data(questions)
        # 4/6 resolved yes = 0.6667
        pred = predictor.predict({"id": "1", "domain": "macro"})
        assert abs(pred.predicted_probability - 0.6667) < 0.01

    def test_calibrate_needs_minimum_sample(self):
        predictor = BaseRatePredictor()
        original_rate = predictor.domain_rates["macro"]
        # Only 3 samples -- below minimum of 5
        questions = [
            {"domain": "macro", "resolved_value": 1.0},
            {"domain": "macro", "resolved_value": 1.0},
            {"domain": "macro", "resolved_value": 1.0},
        ]
        predictor.calibrate_from_data(questions)
        # Rate should be unchanged because sample too small
        assert predictor.domain_rates["macro"] == original_rate

    def test_custom_domain_rates(self):
        predictor = BaseRatePredictor(domain_rates={"custom": 0.75})
        pred = predictor.predict({"id": "1", "domain": "custom"})
        assert pred.predicted_probability == 0.75

    def test_metadata_included(self):
        predictor = BaseRatePredictor()
        pred = predictor.predict({"id": "1", "domain": "macro"})
        assert pred.metadata["domain"] == "macro"
        assert pred.metadata["rate"] == 0.55

    def test_batch_prediction(self):
        predictor = BaseRatePredictor()
        questions = [
            {"id": "1", "domain": "macro"},
            {"id": "2", "domain": "technology"},
            {"id": "3", "domain": "other"},
        ]
        preds = predictor.predict_batch(questions)
        assert len(preds) == 3
        assert preds[0].predicted_probability == 0.55
        assert preds[1].predicted_probability == 0.40
        assert preds[2].predicted_probability == 0.50


# ------------------------------------------------------------------
# NaiveDirectionalPredictor
# ------------------------------------------------------------------

class TestNaiveDirectional:
    def test_positive_words_increase(self):
        predictor = NaiveDirectionalPredictor()
        q = {"id": "1", "question_text": "Will GDP increase and prices rise?"}
        pred = predictor.predict(q)
        assert pred.predicted_probability > 0.5

    def test_negative_words_decrease(self):
        predictor = NaiveDirectionalPredictor()
        q = {"id": "1", "question_text": "Will employment decline and wages fall?"}
        pred = predictor.predict(q)
        assert pred.predicted_probability < 0.5

    def test_neutral_stays_near_half(self):
        predictor = NaiveDirectionalPredictor()
        q = {"id": "1", "question_text": "Will something happen?"}
        pred = predictor.predict(q)
        assert abs(pred.predicted_probability - 0.5) < 0.1

    def test_bounded_predictions(self):
        predictor = NaiveDirectionalPredictor()
        # Many positive words should still be capped at 0.85
        q = {"id": "1", "question_text": "Will things increase rise grow exceed above more higher gain surge accelerate expand improve?"}
        pred = predictor.predict(q)
        assert pred.predicted_probability <= 0.85

    def test_bounded_predictions_lower(self):
        predictor = NaiveDirectionalPredictor()
        q = {"id": "1", "question_text": "Will things decrease fall decline below less lower drop reduce contract worsen shrink?"}
        pred = predictor.predict(q)
        assert pred.predicted_probability >= 0.15

    def test_case_insensitive(self):
        predictor = NaiveDirectionalPredictor()
        q_lower = {"id": "1", "question_text": "Will prices increase?"}
        q_upper = {"id": "2", "question_text": "Will prices INCREASE?"}
        assert predictor.predict(q_lower).predicted_probability == predictor.predict(q_upper).predicted_probability

    def test_metadata_signal_counts(self):
        predictor = NaiveDirectionalPredictor()
        q = {"id": "1", "question_text": "Will GDP increase and employment decline?"}
        pred = predictor.predict(q)
        assert pred.metadata["pos_signals"] >= 1
        assert pred.metadata["neg_signals"] >= 1

    def test_model_name(self):
        predictor = NaiveDirectionalPredictor()
        pred = predictor.predict({"id": "1", "question_text": "Test?"})
        assert pred.model_name == "naive_directional"

    def test_missing_question_text(self):
        predictor = NaiveDirectionalPredictor()
        pred = predictor.predict({"id": "1"})
        assert pred.predicted_probability == 0.5

    def test_batch_prediction(self):
        predictor = NaiveDirectionalPredictor()
        questions = [
            {"id": "1", "question_text": "Will prices increase?"},
            {"id": "2", "question_text": "Will growth decline?"},
            {"id": "3", "question_text": "Will something happen?"},
        ]
        preds = predictor.predict_batch(questions)
        assert len(preds) == 3
        assert preds[0].predicted_probability > 0.5
        assert preds[1].predicted_probability < 0.5


# ------------------------------------------------------------------
# DifficultyAwareBaseRatePredictor
# ------------------------------------------------------------------

class TestDifficultyAware:
    def test_hard_questions_lower(self):
        predictor = DifficultyAwareBaseRatePredictor()
        easy_q = {"id": "1", "domain": "macro", "difficulty": "easy"}
        hard_q = {"id": "2", "domain": "macro", "difficulty": "hard"}

        easy_pred = predictor.predict(easy_q)
        hard_pred = predictor.predict(hard_q)

        assert hard_pred.predicted_probability < easy_pred.predicted_probability

    def test_medium_between_easy_and_hard(self):
        predictor = DifficultyAwareBaseRatePredictor()
        easy = predictor.predict({"id": "1", "domain": "macro", "difficulty": "easy"})
        medium = predictor.predict({"id": "2", "domain": "macro", "difficulty": "medium"})
        hard = predictor.predict({"id": "3", "domain": "macro", "difficulty": "hard"})

        assert hard.predicted_probability <= medium.predicted_probability <= easy.predicted_probability

    def test_easy_same_as_base_rate(self):
        predictor = DifficultyAwareBaseRatePredictor()
        pred = predictor.predict({"id": "1", "domain": "macro", "difficulty": "easy"})
        # Easy has 0 adjustment, so should equal base rate for macro
        assert pred.predicted_probability == 0.55

    def test_metadata_includes_adjustment(self):
        predictor = DifficultyAwareBaseRatePredictor()
        pred = predictor.predict({"id": "1", "domain": "macro", "difficulty": "hard"})
        assert "adjustment" in pred.metadata
        assert pred.metadata["adjustment"] == -0.08

    def test_bounded_after_adjustment(self):
        predictor = DifficultyAwareBaseRatePredictor()
        # Even with extreme adjustments, should stay in [0.10, 0.90]
        pred = predictor.predict({"id": "1", "domain": "technology", "difficulty": "hard"})
        assert 0.10 <= pred.predicted_probability <= 0.90

    def test_unknown_difficulty_no_adjustment(self):
        predictor = DifficultyAwareBaseRatePredictor()
        pred = predictor.predict({"id": "1", "domain": "macro", "difficulty": "unknown"})
        # Unknown difficulty gets 0 adjustment, same as easy
        assert pred.predicted_probability == 0.55

    def test_default_difficulty_is_medium(self):
        predictor = DifficultyAwareBaseRatePredictor()
        pred_no_diff = predictor.predict({"id": "1", "domain": "macro"})
        pred_medium = predictor.predict({"id": "2", "domain": "macro", "difficulty": "medium"})
        assert pred_no_diff.predicted_probability == pred_medium.predicted_probability

    def test_uses_custom_base_predictor(self):
        custom_base = BaseRatePredictor(domain_rates={"custom": 0.80})
        predictor = DifficultyAwareBaseRatePredictor(base_predictor=custom_base)
        pred = predictor.predict({"id": "1", "domain": "custom", "difficulty": "hard"})
        # 0.80 + (-0.08) = 0.72
        assert pred.predicted_probability == pytest.approx(0.72, abs=0.01)

    def test_model_name(self):
        predictor = DifficultyAwareBaseRatePredictor()
        pred = predictor.predict({"id": "1", "domain": "macro", "difficulty": "medium"})
        assert pred.model_name == "difficulty_aware_base_rate"

    def test_batch_prediction(self):
        predictor = DifficultyAwareBaseRatePredictor()
        questions = [
            {"id": "1", "domain": "macro", "difficulty": "easy"},
            {"id": "2", "domain": "macro", "difficulty": "hard"},
        ]
        preds = predictor.predict_batch(questions)
        assert len(preds) == 2
        assert preds[0].predicted_probability > preds[1].predicted_probability


# ------------------------------------------------------------------
# Registry
# ------------------------------------------------------------------

class TestRegistry:
    def test_all_baselines_registered(self):
        assert "always_half" in BASELINE_PREDICTORS
        assert "base_rate" in BASELINE_PREDICTORS
        assert "naive_directional" in BASELINE_PREDICTORS
        assert "difficulty_aware" in BASELINE_PREDICTORS

    def test_registry_count(self):
        assert len(BASELINE_PREDICTORS) == 4

    def test_all_baselines_instantiable(self):
        for name, cls in BASELINE_PREDICTORS.items():
            instance = cls()
            q = {
                "id": "1",
                "question_text": "Test?",
                "domain": "other",
                "difficulty": "medium",
            }
            pred = instance.predict(q)
            assert isinstance(pred, BaselinePrediction)
            assert 0 <= pred.predicted_probability <= 1

    def test_registry_maps_to_correct_classes(self):
        assert BASELINE_PREDICTORS["always_half"] is AlwaysHalfPredictor
        assert BASELINE_PREDICTORS["base_rate"] is BaseRatePredictor
        assert BASELINE_PREDICTORS["naive_directional"] is NaiveDirectionalPredictor
        assert BASELINE_PREDICTORS["difficulty_aware"] is DifficultyAwareBaseRatePredictor

    def test_all_baselines_support_batch(self):
        questions = [
            {"id": str(i), "question_text": f"Q{i}?", "domain": "other", "difficulty": "medium"}
            for i in range(5)
        ]
        for name, cls in BASELINE_PREDICTORS.items():
            instance = cls()
            preds = instance.predict_batch(questions)
            assert len(preds) == 5
            assert all(isinstance(p, BaselinePrediction) for p in preds)
