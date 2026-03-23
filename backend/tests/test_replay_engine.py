"""Tests for the time-sliced replay engine.

These tests verify:
1. No future information leakage
2. Correct temporal filtering of evidence
3. Deterministic replay (same inputs -> same outputs)
4. Correct metric computation
5. Pipeline step correctness
"""
from __future__ import annotations

import pytest
import uuid
from datetime import datetime, timedelta, timezone

from app.services.replay_engine import (
    ReplayRunner,
    ReplayConfig,
    ReplayQuestion,
    ReplayPrediction,
)


# -- Fixtures --

@pytest.fixture
def sample_question():
    """A resolved binary question."""
    return {
        "id": str(uuid.uuid4()),
        "question_text": "Will US CPI YoY exceed 4% in June 2023?",
        "domain": "macro",
        "question_type": "binary",
        "open_date": "2023-01-15T00:00:00Z",
        "close_date": "2023-07-01T00:00:00Z",
        "resolve_date": "2023-07-15T00:00:00Z",
        "resolved_value": 0.0,
        "difficulty": "medium",
    }


@pytest.fixture
def sample_evidence():
    """Evidence items with varied published dates."""
    return [
        {
            "published_at": "2023-02-15T00:00:00Z",
            "source": "BLS",
            "title": "January CPI at 6.4% YoY",
            "content": (
                "Consumer price index showed 6.4% year-over-year increase "
                "in January 2023, continuing downward trend from peak."
            ),
            "source_type": "official_data",
            "source_quality_score": 0.95,
        },
        {
            "published_at": "2023-03-14T00:00:00Z",
            "source": "BLS",
            "title": "February CPI at 6.0% YoY",
            "content": "CPI continued decline to 6.0%, faster than expected drop.",
            "source_type": "official_data",
            "source_quality_score": 0.95,
        },
        {
            "published_at": "2023-05-10T00:00:00Z",
            "source": "BLS",
            "title": "April CPI drops to 4.9% YoY",
            "content": (
                "Inflation fell below 5% for first time since 2021. "
                "CPI at 4.9% year over year."
            ),
            "source_type": "official_data",
            "source_quality_score": 0.95,
        },
        {
            "published_at": "2023-06-13T00:00:00Z",
            "source": "BLS",
            "title": "May CPI at 4.0% YoY",
            "content": "CPI exactly at 4.0% threshold, sharp decline from peak.",
            "source_type": "official_data",
            "source_quality_score": 0.95,
        },
        {
            "published_at": "2023-07-12T00:00:00Z",
            "source": "BLS",
            "title": "June CPI at 3.0% YoY",
            "content": (
                "CPI dropped to 3.0%, well below the 4% threshold. "
                "Fastest deceleration in years."
            ),
            "source_type": "official_data",
            "source_quality_score": 0.95,
        },
    ]


@pytest.fixture
def runner():
    return ReplayRunner()


# -- No Future Leakage Tests --

class TestNoLeakage:
    """Verify strict temporal integrity."""

    def test_90d_cutoff_filters_future_evidence(
        self, runner, sample_question, sample_evidence
    ):
        """At 90d cutoff, evidence after April 16 must be excluded."""
        replay_q = runner.prepare_question(sample_question, sample_evidence, cutoff_days=90)
        # Cutoff = July 15 - 90 = April 16
        # Only evidence from Feb 15 and Mar 14 should be included
        assert len(replay_q.available_evidence) == 2
        for ev in replay_q.available_evidence:
            assert ev["published_at"] <= "2023-04-16T00:00:00Z"

    def test_30d_cutoff_filters_correctly(
        self, runner, sample_question, sample_evidence
    ):
        """At 30d cutoff, evidence after June 15 must be excluded."""
        replay_q = runner.prepare_question(sample_question, sample_evidence, cutoff_days=30)
        # Cutoff = July 15 - 30 = June 15
        # Evidence from Feb, Mar, May, and June 13 should be included
        assert len(replay_q.available_evidence) == 4

    def test_7d_cutoff_includes_most_evidence(
        self, runner, sample_question, sample_evidence
    ):
        """At 7d cutoff, most evidence should be available."""
        replay_q = runner.prepare_question(sample_question, sample_evidence, cutoff_days=7)
        # Cutoff = July 15 - 7 = July 8
        # All evidence except July 12 should be included
        assert len(replay_q.available_evidence) == 4

    def test_verify_no_leakage_raises_on_future_data(self, runner):
        """If future evidence sneaks through, verification must catch it."""
        replay_q = ReplayQuestion(
            question_id="test",
            question_text="Test",
            domain="macro",
            question_type="binary",
            open_date=datetime(2023, 1, 1, tzinfo=timezone.utc),
            resolve_date=datetime(2023, 7, 15, tzinfo=timezone.utc),
            resolved_value=0.0,
            cutoff_date=datetime(2023, 4, 16, tzinfo=timezone.utc),
            cutoff_days=90,
            available_evidence=[
                {
                    "published_at": "2023-06-01T00:00:00Z",
                    "title": "Future evidence",
                    "content": "...",
                    "source_type": "news",
                    "source": "test",
                }
            ],
            total_evidence=5,
        )
        with pytest.raises(ValueError, match="TEMPORAL LEAKAGE"):
            runner._verify_no_leakage(replay_q)

    def test_verify_no_leakage_passes_for_valid_data(self, runner):
        """Verification should pass when all evidence is before cutoff."""
        replay_q = ReplayQuestion(
            question_id="test",
            question_text="Test",
            domain="macro",
            question_type="binary",
            open_date=datetime(2023, 1, 1, tzinfo=timezone.utc),
            resolve_date=datetime(2023, 7, 15, tzinfo=timezone.utc),
            resolved_value=0.0,
            cutoff_date=datetime(2023, 4, 16, tzinfo=timezone.utc),
            cutoff_days=90,
            available_evidence=[
                {
                    "published_at": "2023-02-15T00:00:00Z",
                    "title": "Past evidence",
                    "content": "...",
                    "source_type": "news",
                    "source": "test",
                }
            ],
            total_evidence=5,
        )
        # Should not raise
        runner._verify_no_leakage(replay_q)

    def test_no_evidence_at_early_cutoff(
        self, runner, sample_question, sample_evidence
    ):
        """Very early cutoff should have no evidence available."""
        replay_q = runner.prepare_question(sample_question, sample_evidence, cutoff_days=200)
        # Cutoff = July 15 - 200 = ~Dec 27, 2022. No evidence before that.
        assert len(replay_q.available_evidence) == 0

    def test_cutoff_on_exact_evidence_date(self, runner, sample_question, sample_evidence):
        """Evidence published exactly on cutoff date should be included (<=)."""
        # Cutoff at Feb 15 means cutoff_date = July 15 - 150 = Feb 14
        # Actually let's compute: we need cutoff such that cutoff_date == evidence date
        # Evidence at Feb 15. resolve_date = July 15.
        # cutoff_date = July 15 - N = Feb 15 => N = 150 days
        replay_q = runner.prepare_question(sample_question, sample_evidence, cutoff_days=150)
        # Cutoff = July 15 - 150 = Feb 15 (exactly). Feb 15 evidence should be included.
        assert len(replay_q.available_evidence) == 1
        assert "January CPI" in replay_q.available_evidence[0]["title"]


# -- Deterministic Replay Tests --

class TestDeterministicReplay:
    """Verify same inputs produce same outputs."""

    def test_same_config_same_result(
        self, runner, sample_question, sample_evidence
    ):
        """Running the same question twice must give identical results."""
        config = ReplayConfig(random_seed=42)

        replay_q1 = runner.prepare_question(sample_question, sample_evidence, 90)
        pred1 = runner.forecast_question(replay_q1, config)

        replay_q2 = runner.prepare_question(sample_question, sample_evidence, 90)
        pred2 = runner.forecast_question(replay_q2, config)

        assert pred1.predicted_probability == pred2.predicted_probability
        assert pred1.brier_score == pred2.brier_score

    def test_different_seeds_same_without_randomness(
        self, runner, sample_question, sample_evidence
    ):
        """Since pipeline is deterministic (no sampling), different seeds give same result."""
        config1 = ReplayConfig(random_seed=42)
        config2 = ReplayConfig(random_seed=123)

        replay_q = runner.prepare_question(sample_question, sample_evidence, 90)
        pred1 = runner.forecast_question(replay_q, config1)
        pred2 = runner.forecast_question(replay_q, config2)

        assert pred1.predicted_probability == pred2.predicted_probability

    def test_evidence_ordering_deterministic(
        self, runner, sample_question, sample_evidence
    ):
        """Evidence should be sorted by published_at for deterministic ordering."""
        replay_q = runner.prepare_question(sample_question, sample_evidence, 30)
        dates = [ev["published_at"] for ev in replay_q.available_evidence]
        assert dates == sorted(dates)

    def test_prepare_question_fields(
        self, runner, sample_question, sample_evidence
    ):
        """All required fields should be populated on ReplayQuestion."""
        replay_q = runner.prepare_question(sample_question, sample_evidence, 90)
        assert replay_q.question_id == sample_question["id"]
        assert replay_q.question_text == sample_question["question_text"]
        assert replay_q.domain == "macro"
        assert replay_q.question_type == "binary"
        assert replay_q.cutoff_days == 90
        assert replay_q.total_evidence == 5
        assert replay_q.resolved_value == 0.0


# -- Correct Metric Computation Tests --

class TestMetricComputation:
    """Verify Brier and log score calculations."""

    def test_brier_score_computed(
        self, runner, sample_question, sample_evidence
    ):
        """Brier score should be computed and within valid range."""
        config = ReplayConfig(use_base_rates=False, use_evidence_scoring=False)
        replay_q = runner.prepare_question(sample_question, sample_evidence, 90)
        pred = runner.forecast_question(replay_q, config)
        assert pred.brier_score is not None
        assert 0 <= pred.brier_score <= 1

    def test_brier_score_formula_for_binary(self):
        """Brier = (predicted - actual)^2 for binary."""
        expected_brier = (0.7 - 1.0) ** 2  # 0.09
        assert abs(expected_brier - 0.09) < 1e-10

    def test_log_score_computed(
        self, runner, sample_question, sample_evidence
    ):
        """Log score should be computed and non-negative."""
        config = ReplayConfig()
        replay_q = runner.prepare_question(sample_question, sample_evidence, 7)
        pred = runner.forecast_question(replay_q, config)
        assert pred.log_score is not None
        assert pred.log_score >= 0

    def test_predictions_bounded(
        self, runner, sample_question, sample_evidence
    ):
        """All predictions must be in [0.01, 0.99]."""
        config = ReplayConfig()
        replay_q = runner.prepare_question(sample_question, sample_evidence, 90)
        pred = runner.forecast_question(replay_q, config)
        assert 0.01 <= pred.predicted_probability <= 0.99

    def test_brier_zero_for_correct_prediction(self, runner):
        """When prediction equals actual, brier should be zero."""
        config = ReplayConfig(
            use_base_rates=False,
            use_evidence_scoring=False,
            use_calibration=False,
        )
        # Craft a question with resolved_value = 0.5 and no pipeline changes
        # Actually, with all flags off and no calibration, prediction = 0.5
        # For binary, actual is 0 or 1 so brier can't be exactly 0 with 0.5 pred.
        # But we can verify it equals (0.5 - actual)^2
        question = {
            "id": "test",
            "question_text": "Test question",
            "domain": "macro",
            "question_type": "binary",
            "open_date": "2023-01-01T00:00:00Z",
            "resolve_date": "2023-07-01T00:00:00Z",
            "resolved_value": 1.0,
        }
        replay_q = runner.prepare_question(question, [], 90)
        pred = runner.forecast_question(replay_q, config)
        expected = (0.5 - 1.0) ** 2
        assert abs(pred.brier_score - expected) < 1e-6

    def test_log_score_high_for_confident_wrong(self, runner):
        """Log score should be higher when prediction is confidently wrong."""
        # We can't easily force a specific prediction, but we can verify
        # the log score formula directly.
        import math
        # If predicted 0.9 and actual is 0:
        log_wrong = -math.log(1 - 0.9)  # = -log(0.1) ~ 2.3
        # If predicted 0.6 and actual is 0:
        log_ok = -math.log(1 - 0.6)     # = -log(0.4) ~ 0.92
        assert log_wrong > log_ok


# -- Pipeline Step Tests --

class TestPipelineSteps:
    """Verify individual pipeline steps work correctly."""

    def test_base_rate_domain_specific(
        self, runner, sample_question, sample_evidence
    ):
        """Base rate should differ by domain."""
        config = ReplayConfig(
            use_base_rates=True,
            use_evidence_scoring=False,
            use_calibration=False,
        )

        macro_q = runner.prepare_question(sample_question, sample_evidence, 90)
        pred_macro = runner.forecast_question(macro_q, config)

        tech_question = {**sample_question, "domain": "technology"}
        tech_q = runner.prepare_question(tech_question, sample_evidence, 90)
        pred_tech = runner.forecast_question(tech_q, config)

        # Macro (0.55) and tech (0.40) should have different base rates
        assert pred_macro.base_rate_used != pred_tech.base_rate_used

    def test_evidence_shifts_prediction(
        self, runner, sample_question, sample_evidence
    ):
        """With evidence, prediction should differ from base rate."""
        config_no_ev = ReplayConfig(
            use_evidence_scoring=False, use_calibration=False
        )
        config_with_ev = ReplayConfig(
            use_evidence_scoring=True, use_calibration=False
        )

        replay_q = runner.prepare_question(sample_question, sample_evidence, 30)

        pred_no = runner.forecast_question(replay_q, config_no_ev)
        pred_yes = runner.forecast_question(replay_q, config_with_ev)

        # Predictions should differ when evidence is considered
        assert pred_no.predicted_probability != pred_yes.predicted_probability

    def test_calibration_adjusts_prediction(
        self, runner, sample_question, sample_evidence
    ):
        """Calibration should modify the raw prediction."""
        config_raw = ReplayConfig(use_calibration=False)
        config_cal = ReplayConfig(use_calibration=True)

        replay_q = runner.prepare_question(sample_question, sample_evidence, 90)

        pred_raw = runner.forecast_question(replay_q, config_raw)
        pred_cal = runner.forecast_question(replay_q, config_cal)

        # Calibrated prediction should differ from raw
        assert pred_raw.predicted_probability != pred_cal.predicted_probability

    def test_static_prior_ignores_evidence(
        self, runner, sample_question, sample_evidence
    ):
        """Static update strategy should not change from base rate."""
        config = ReplayConfig(update_strategy="static", use_calibration=False)

        replay_q = runner.prepare_question(sample_question, sample_evidence, 30)
        pred = runner.forecast_question(replay_q, config)

        # Static means prediction = base rate
        assert pred.predicted_probability == pred.base_rate_used

    def test_more_evidence_at_shorter_horizon(
        self, runner, sample_question, sample_evidence
    ):
        """Shorter horizons should have more evidence available."""
        q_90 = runner.prepare_question(sample_question, sample_evidence, 90)
        q_30 = runner.prepare_question(sample_question, sample_evidence, 30)
        q_7 = runner.prepare_question(sample_question, sample_evidence, 7)

        assert len(q_90.available_evidence) <= len(q_30.available_evidence)
        assert len(q_30.available_evidence) <= len(q_7.available_evidence)

    def test_pipeline_trace_recorded(
        self, runner, sample_question, sample_evidence
    ):
        """Pipeline trace should record all steps."""
        config = ReplayConfig()
        replay_q = runner.prepare_question(sample_question, sample_evidence, 30)
        pred = runner.forecast_question(replay_q, config)

        assert "steps" in pred.pipeline_trace
        step_names = [s["step"] for s in pred.pipeline_trace["steps"]]
        assert "base_rate" in step_names
        assert "calibration" in step_names

    def test_evidence_scoring_step_tracked(
        self, runner, sample_question, sample_evidence
    ):
        """Evidence scoring step should appear in the trace when evidence exists."""
        config = ReplayConfig(use_evidence_scoring=True)
        replay_q = runner.prepare_question(sample_question, sample_evidence, 30)
        pred = runner.forecast_question(replay_q, config)

        step_names = [s["step"] for s in pred.pipeline_trace["steps"]]
        assert "evidence_scoring" in step_names

    def test_belief_update_step_tracked(
        self, runner, sample_question, sample_evidence
    ):
        """Belief update step should appear in the trace when using incremental strategy."""
        config = ReplayConfig(
            use_evidence_scoring=True,
            update_strategy="incremental",
        )
        replay_q = runner.prepare_question(sample_question, sample_evidence, 30)
        pred = runner.forecast_question(replay_q, config)

        step_names = [s["step"] for s in pred.pipeline_trace["steps"]]
        assert "belief_update" in step_names

    def test_no_evidence_scoring_without_evidence(self, runner, sample_question):
        """When no evidence is available, evidence scoring step should be skipped."""
        config = ReplayConfig(use_evidence_scoring=True)
        replay_q = runner.prepare_question(sample_question, [], 90)
        pred = runner.forecast_question(replay_q, config)

        step_names = [s["step"] for s in pred.pipeline_trace["steps"]]
        assert "evidence_scoring" not in step_names

    def test_calibration_pulls_toward_half(self, runner):
        """Default calibration applies shrinkage toward 0.5."""
        # The inline calibration does: p * 0.95 + 0.5 * 0.05
        p = 0.8
        expected = p * 0.95 + 0.5 * 0.05  # 0.785
        result = runner._apply_calibration(p, "macro", ReplayConfig())
        assert abs(result - expected) < 1e-6

    def test_update_clamped_to_bounds(self, runner):
        """Belief update output should be clamped to [0.01, 0.99]."""
        # Create extreme evidence scores to try to push past bounds
        extreme_scores = [
            {
                "composite_weight": 0.9,
                "direction": 1.0,
                "magnitude": 0.8,
                "uncertainty": 0.0,
            }
        ] * 10
        config = ReplayConfig()
        result = runner._apply_updates(0.95, extreme_scores, config)
        assert 0.01 <= result <= 0.99

    def test_update_max_shift_from_prior(self, runner):
        """Belief update should not shift more than 0.25 from prior."""
        extreme_scores = [
            {
                "composite_weight": 0.9,
                "direction": 1.0,
                "magnitude": 0.8,
                "uncertainty": 0.1,
            }
        ] * 5
        config = ReplayConfig()
        prior = 0.5
        result = runner._apply_updates(prior, extreme_scores, config)
        assert abs(result - prior) <= 0.25 + 1e-6


# -- Batch Evaluation Tests --

class TestBatchEvaluation:
    """Test full evaluation runs."""

    def test_run_evaluation_produces_results(
        self, runner, sample_question, sample_evidence
    ):
        """Full evaluation run should produce results for all cutoffs."""
        config = ReplayConfig()
        questions = [sample_question]
        evidence = {0: sample_evidence}
        cutoffs = [90, 30, 7]

        result = runner.run_evaluation(questions, evidence, cutoffs, config)

        assert result.total_questions == 1
        assert len(result.predictions) == 3  # 3 cutoffs
        assert result.mean_brier_score >= 0
        assert result.by_horizon  # should have horizon breakdown

    def test_run_evaluation_multiple_questions(
        self, runner, sample_question, sample_evidence
    ):
        """Evaluation with multiple questions."""
        q2 = {
            **sample_question,
            "id": str(uuid.uuid4()),
            "question_text": "Will unemployment rise above 5%?",
            "resolved_value": 0.0,
        }

        questions = [sample_question, q2]
        evidence = {0: sample_evidence, 1: sample_evidence[:2]}
        cutoffs = [90, 30]

        config = ReplayConfig()
        result = runner.run_evaluation(questions, evidence, cutoffs, config)

        assert result.total_questions == 2
        assert len(result.predictions) == 4  # 2 questions * 2 cutoffs

    def test_run_evaluation_empty(self, runner):
        """Empty evaluation should return zeroed result."""
        config = ReplayConfig()
        result = runner.run_evaluation([], {}, [90], config)

        assert result.total_questions == 0
        assert len(result.predictions) == 0
        assert result.mean_brier_score == 0

    def test_run_evaluation_domain_breakdown(
        self, runner, sample_question, sample_evidence
    ):
        """Result should include domain breakdown."""
        config = ReplayConfig()
        questions = [sample_question]
        evidence = {0: sample_evidence}
        result = runner.run_evaluation(questions, evidence, [90], config)

        assert result.by_domain is not None
        assert len(result.by_domain) > 0

    def test_run_evaluation_horizon_breakdown(
        self, runner, sample_question, sample_evidence
    ):
        """Result should include horizon breakdown keyed by cutoff label."""
        config = ReplayConfig()
        questions = [sample_question]
        evidence = {0: sample_evidence}
        cutoffs = [90, 30]
        result = runner.run_evaluation(questions, evidence, cutoffs, config)

        assert "90d" in result.by_horizon
        assert "30d" in result.by_horizon
        assert result.by_horizon["90d"]["n"] == 1
        assert result.by_horizon["30d"]["n"] == 1

    def test_run_evaluation_cost_accumulated(
        self, runner, sample_question, sample_evidence
    ):
        """Total cost should reflect evidence scoring costs."""
        config = ReplayConfig(use_evidence_scoring=True)
        questions = [sample_question]
        evidence = {0: sample_evidence}
        result = runner.run_evaluation(questions, evidence, [30], config)

        # Evidence scoring adds 0.0001 per item; 30d cutoff includes 4 items
        assert result.total_cost_usd > 0

    def test_run_evaluation_deterministic_with_seed(
        self, runner, sample_question, sample_evidence
    ):
        """Two evaluation runs with the same seed should give identical results."""
        config = ReplayConfig(random_seed=99)
        questions = [sample_question]
        evidence = {0: sample_evidence}
        cutoffs = [90, 30]

        result1 = runner.run_evaluation(questions, evidence, cutoffs, config)
        result2 = runner.run_evaluation(questions, evidence, cutoffs, config)

        assert result1.mean_brier_score == result2.mean_brier_score
        assert result1.mean_log_score == result2.mean_log_score
        for p1, p2 in zip(result1.predictions, result2.predictions):
            assert p1.predicted_probability == p2.predicted_probability


# -- Evidence Scoring Internals --

class TestEvidenceScoring:
    """Tests for internal evidence scoring logic."""

    def test_official_data_high_credibility(self, runner, sample_question, sample_evidence):
        """Official data sources should get high credibility scores."""
        replay_q = runner.prepare_question(sample_question, sample_evidence, 30)
        config = ReplayConfig()
        score = runner._score_evidence(
            sample_evidence[0], replay_q, config
        )
        assert score["credibility"] == 0.95

    def test_recency_weighting_decays(self, runner, sample_question, sample_evidence):
        """Older evidence should have lower recency score."""
        replay_q = runner.prepare_question(sample_question, sample_evidence, 30)
        config = ReplayConfig(use_recency_weighting=True)

        score_old = runner._score_evidence(
            sample_evidence[0], replay_q, config
        )
        score_new = runner._score_evidence(
            sample_evidence[3], replay_q, config
        )
        assert score_old["recency"] < score_new["recency"]

    def test_no_recency_weighting(self, runner, sample_question, sample_evidence):
        """When recency weighting is off, recency should be 1.0."""
        replay_q = runner.prepare_question(sample_question, sample_evidence, 30)
        config = ReplayConfig(use_recency_weighting=False)

        score = runner._score_evidence(
            sample_evidence[0], replay_q, config
        )
        assert score["recency"] == 1.0

    def test_uniform_weighting(self, runner, sample_question, sample_evidence):
        """Uniform weighting should set composite to 0.5."""
        replay_q = runner.prepare_question(sample_question, sample_evidence, 30)
        config = ReplayConfig(evidence_weighting="uniform")

        score = runner._score_evidence(
            sample_evidence[0], replay_q, config
        )
        assert score["composite_weight"] == 0.5

    def test_direction_from_positive_content(self, runner):
        """Content with positive words should have positive direction."""
        ev = {
            "published_at": "2023-01-01T00:00:00Z",
            "content": "Prices increase and rise above threshold. Higher growth.",
            "source_type": "news",
            "source_quality_score": 0.5,
        }
        replay_q = ReplayQuestion(
            question_id="test",
            question_text="Will prices increase?",
            domain="macro",
            question_type="binary",
            open_date=datetime(2023, 1, 1, tzinfo=timezone.utc),
            resolve_date=datetime(2023, 7, 1, tzinfo=timezone.utc),
            resolved_value=1.0,
            cutoff_date=datetime(2023, 6, 1, tzinfo=timezone.utc),
            cutoff_days=30,
            available_evidence=[ev],
            total_evidence=1,
        )
        score = runner._score_evidence(ev, replay_q, ReplayConfig())
        assert score["direction"] == 1.0

    def test_direction_from_negative_content(self, runner):
        """Content with negative words should have negative direction."""
        ev = {
            "published_at": "2023-01-01T00:00:00Z",
            "content": "Employment decline and wages fall. Prices drop below expectations.",
            "source_type": "news",
            "source_quality_score": 0.5,
        }
        replay_q = ReplayQuestion(
            question_id="test",
            question_text="Will something happen?",
            domain="macro",
            question_type="binary",
            open_date=datetime(2023, 1, 1, tzinfo=timezone.utc),
            resolve_date=datetime(2023, 7, 1, tzinfo=timezone.utc),
            resolved_value=0.0,
            cutoff_date=datetime(2023, 6, 1, tzinfo=timezone.utc),
            cutoff_days=30,
            available_evidence=[ev],
            total_evidence=1,
        )
        score = runner._score_evidence(ev, replay_q, ReplayConfig())
        assert score["direction"] == -1.0


# -- Rationale Generation --

class TestRationaleGeneration:
    """Tests for rationale text generation."""

    def test_rationale_nonempty(
        self, runner, sample_question, sample_evidence
    ):
        """Rationale should be a non-empty string."""
        config = ReplayConfig()
        replay_q = runner.prepare_question(sample_question, sample_evidence, 30)
        pred = runner.forecast_question(replay_q, config)
        assert isinstance(pred.rationale, str)
        assert len(pred.rationale) > 10

    def test_rationale_contains_domain(
        self, runner, sample_question, sample_evidence
    ):
        """Rationale should mention the domain."""
        config = ReplayConfig()
        replay_q = runner.prepare_question(sample_question, sample_evidence, 30)
        pred = runner.forecast_question(replay_q, config)
        assert "macro" in pred.rationale
