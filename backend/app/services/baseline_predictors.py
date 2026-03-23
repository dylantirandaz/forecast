"""Baseline predictors for evaluation comparison.

These baselines provide reference points to measure whether the
forecasting pipeline adds value beyond simple strategies.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BaselinePrediction:
    """Prediction from a baseline model."""
    question_id: str
    predicted_probability: float
    model_name: str
    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            object.__setattr__(self, "metadata", {})


# ---------------------------------------------------------------------------
# Baseline predictors
# ---------------------------------------------------------------------------

class AlwaysHalfPredictor:
    """Always predicts 0.5. The simplest possible baseline.

    Brier score = 0.25 when base rate = 0.5.
    Any useful model should beat this.
    """
    name = "always_0.5"

    def predict(self, question: dict) -> BaselinePrediction:
        return BaselinePrediction(
            question_id=question.get("id", ""),
            predicted_probability=0.5,
            model_name=self.name,
        )

    def predict_batch(self, questions: list[dict]) -> list[BaselinePrediction]:
        return [self.predict(q) for q in questions]


class BaseRatePredictor:
    """Predicts the historical base rate for each domain.

    Uses domain-specific resolution frequencies as predictions.
    This is the minimum-information principled baseline.
    """
    name = "base_rate"

    def __init__(self, domain_rates: dict[str, float] | None = None):
        self.domain_rates = domain_rates or {
            "macro": 0.55,
            "politics": 0.48,
            "technology": 0.40,
            "business": 0.52,
            "science": 0.45,
            "housing": 0.50,
            "energy": 0.50,
            "health": 0.50,
            "geopolitics": 0.45,
            "other": 0.50,
        }

    def calibrate_from_data(self, questions: list[dict]) -> None:
        """Calibrate domain rates from resolved questions."""
        domain_counts: dict[str, list[float]] = {}
        for q in questions:
            d = q.get("domain", "other")
            domain_counts.setdefault(d, []).append(q["resolved_value"])

        for domain, values in domain_counts.items():
            if len(values) >= 5:  # need minimum sample
                self.domain_rates[domain] = round(float(np.mean(values)), 4)

        logger.info(f"Calibrated base rates from {len(questions)} questions: {self.domain_rates}")

    def predict(self, question: dict) -> BaselinePrediction:
        domain = question.get("domain", "other")
        rate = self.domain_rates.get(domain, 0.50)
        return BaselinePrediction(
            question_id=question.get("id", ""),
            predicted_probability=rate,
            model_name=self.name,
            metadata={"domain": domain, "rate": rate},
        )

    def predict_batch(self, questions: list[dict]) -> list[BaselinePrediction]:
        return [self.predict(q) for q in questions]


class NaiveDirectionalPredictor:
    """Uses simple keyword matching to predict direction.

    Looks for positive/negative signal words in the question
    and adjusts from 0.5 accordingly. A step above always-0.5
    but still very simple.
    """
    name = "naive_directional"

    POSITIVE_SIGNALS = {
        "increase", "rise", "grow", "exceed", "above", "more", "higher",
        "gain", "surge", "accelerate", "expand", "improve",
    }
    NEGATIVE_SIGNALS = {
        "decrease", "fall", "decline", "below", "less", "lower",
        "drop", "reduce", "contract", "worsen", "shrink",
    }

    def predict(self, question: dict) -> BaselinePrediction:
        text = question.get("question_text", "").lower()

        pos = sum(1 for w in self.POSITIVE_SIGNALS if w in text)
        neg = sum(1 for w in self.NEGATIVE_SIGNALS if w in text)

        # Modest adjustment from 0.5
        adjustment = (pos - neg) * 0.05
        prob = max(0.15, min(0.85, 0.5 + adjustment))

        return BaselinePrediction(
            question_id=question.get("id", ""),
            predicted_probability=round(prob, 4),
            model_name=self.name,
            metadata={"pos_signals": pos, "neg_signals": neg},
        )

    def predict_batch(self, questions: list[dict]) -> list[BaselinePrediction]:
        return [self.predict(q) for q in questions]


class DifficultyAwareBaseRatePredictor:
    """Adjusts base rate by question difficulty.

    Hard questions tend to resolve "no" more often (they ask about
    unlikely or uncertain events), so we adjust accordingly.
    """
    name = "difficulty_aware_base_rate"

    DIFFICULTY_ADJUSTMENTS = {
        "easy": 0.0,    # no adjustment
        "medium": -0.03, # slightly toward no
        "hard": -0.08,   # harder questions resolve no more often
    }

    def __init__(self, base_predictor: BaseRatePredictor | None = None):
        self.base_predictor = base_predictor or BaseRatePredictor()

    def predict(self, question: dict) -> BaselinePrediction:
        base = self.base_predictor.predict(question)
        difficulty = question.get("difficulty", "medium")
        adj = self.DIFFICULTY_ADJUSTMENTS.get(difficulty, 0.0)
        prob = max(0.10, min(0.90, base.predicted_probability + adj))

        return BaselinePrediction(
            question_id=question.get("id", ""),
            predicted_probability=round(prob, 4),
            model_name=self.name,
            metadata={
                "base_rate": base.predicted_probability,
                "difficulty": difficulty,
                "adjustment": adj,
            },
        )

    def predict_batch(self, questions: list[dict]) -> list[BaselinePrediction]:
        return [self.predict(q) for q in questions]


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

BASELINE_PREDICTORS = {
    "always_half": AlwaysHalfPredictor,
    "base_rate": BaseRatePredictor,
    "naive_directional": NaiveDirectionalPredictor,
    "difficulty_aware": DifficultyAwareBaseRatePredictor,
}
