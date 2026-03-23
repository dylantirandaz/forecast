"""Tests for the EvidenceScorer engine.

Validates source credibility lookups, recency decay, and composite
weight calculation.
"""

from __future__ import annotations

import math
from datetime import date, timedelta

import pytest

from app.services.evidence_scorer import (
    RECENCY_HALF_LIFE_DAYS,
    SOURCE_CREDIBILITY_MAP,
    EvidenceScorer,
)


@pytest.fixture()
def scorer() -> EvidenceScorer:
    return EvidenceScorer()


# ------------------------------------------------------------------
# Source credibility
# ------------------------------------------------------------------

class TestSourceCredibility:
    """Source type to credibility score mapping."""

    def test_source_credibility_official_data_high(self, scorer: EvidenceScorer):
        """Official data sources should receive the highest credibility."""
        cred = scorer.compute_source_credibility(source_type="official_data")
        assert cred == pytest.approx(0.95, abs=1e-10)
        # It should be the maximum in the lookup table.
        assert cred == max(SOURCE_CREDIBILITY_MAP.values())

    def test_source_credibility_news_medium(self, scorer: EvidenceScorer):
        """News sources should receive a moderate credibility score."""
        cred = scorer.compute_source_credibility(source_type="news")
        assert cred == pytest.approx(0.55, abs=1e-10)
        assert 0.4 < cred < 0.7

    def test_source_credibility_research(self, scorer: EvidenceScorer):
        cred = scorer.compute_source_credibility(source_type="research")
        assert cred == pytest.approx(0.85, abs=1e-10)

    def test_source_credibility_unknown_type_fallback(self, scorer: EvidenceScorer):
        """Unknown source types should get the default fallback score."""
        cred = scorer.compute_source_credibility(source_type="random_blog")
        assert cred == pytest.approx(0.40, abs=1e-10)

    def test_source_credibility_with_bonus(self, scorer: EvidenceScorer):
        """Known authoritative source names should receive a bonus."""
        cred = scorer.compute_source_credibility(
            source_type="official_data",
            source_name="US Census Bureau",
        )
        assert cred > 0.95
        assert cred <= 1.0


# ------------------------------------------------------------------
# Recency
# ------------------------------------------------------------------

class TestRecency:
    """Exponential-decay recency scoring."""

    def test_recency_recent_high_score(self, scorer: EvidenceScorer):
        """Evidence published today should score very close to 1.0."""
        ref = date(2026, 3, 1)
        score = scorer.compute_recency(
            published_date=ref,
            reference_date=ref,
        )
        assert score == pytest.approx(1.0, abs=1e-10)

    def test_recency_one_halflife_is_half(self, scorer: EvidenceScorer):
        """After exactly one half-life, the score should be ~0.5."""
        ref = date(2026, 3, 1)
        published = ref - timedelta(days=int(RECENCY_HALF_LIFE_DAYS))
        score = scorer.compute_recency(
            published_date=published,
            reference_date=ref,
        )
        assert score == pytest.approx(0.5, abs=0.01)

    def test_recency_old_low_score(self, scorer: EvidenceScorer):
        """Evidence published two years ago should have a very low score."""
        ref = date(2026, 3, 1)
        published = ref - timedelta(days=730)
        score = scorer.compute_recency(
            published_date=published,
            reference_date=ref,
        )
        assert score < 0.15
        assert score > 0.0

    def test_recency_future_dated_full_score(self, scorer: EvidenceScorer):
        """Future-dated evidence should receive full recency credit."""
        ref = date(2026, 3, 1)
        published = ref + timedelta(days=30)
        score = scorer.compute_recency(
            published_date=published,
            reference_date=ref,
        )
        assert score == pytest.approx(1.0, abs=1e-10)

    def test_recency_none_date_conservative(self, scorer: EvidenceScorer):
        """Missing publication date should get a conservative fallback."""
        score = scorer.compute_recency(
            published_date=None,
            reference_date=date(2026, 3, 1),
        )
        assert score == pytest.approx(0.30, abs=1e-10)


# ------------------------------------------------------------------
# Composite weight
# ------------------------------------------------------------------

class TestCompositeWeight:
    """Weighted combination of dimension scores."""

    def test_composite_weight_calculation(self, scorer: EvidenceScorer):
        """The composite weight should be a weighted sum of sub-scores."""
        composite = scorer.compute_composite_weight(
            source_credibility=0.9,
            recency=0.8,
            relevance=0.7,
            redundancy=0.9,  # novelty score
        )
        expected = (
            scorer.W_CREDIBILITY * 0.9
            + scorer.W_RECENCY * 0.8
            + scorer.W_RELEVANCE * 0.7
            + scorer.W_REDUNDANCY * 0.9
        )
        assert composite == pytest.approx(expected, abs=1e-10)

    def test_composite_weight_all_perfect(self, scorer: EvidenceScorer):
        """All 1.0 sub-scores should yield composite = 1.0."""
        composite = scorer.compute_composite_weight(
            source_credibility=1.0,
            recency=1.0,
            relevance=1.0,
            redundancy=1.0,
        )
        assert composite == pytest.approx(1.0, abs=1e-10)

    def test_composite_weight_all_zero(self, scorer: EvidenceScorer):
        """All 0.0 sub-scores should yield composite = 0.0."""
        composite = scorer.compute_composite_weight(
            source_credibility=0.0,
            recency=0.0,
            relevance=0.0,
            redundancy=0.0,
        )
        assert composite == pytest.approx(0.0, abs=1e-10)

    def test_composite_weight_bounded(self, scorer: EvidenceScorer):
        """Composite weight should always be in [0, 1]."""
        for cred in [0.0, 0.5, 1.0]:
            for rec in [0.0, 0.5, 1.0]:
                for rel in [0.0, 0.5, 1.0]:
                    for red in [0.0, 0.5, 1.0]:
                        w = scorer.compute_composite_weight(cred, rec, rel, red)
                        assert 0.0 <= w <= 1.0


# ------------------------------------------------------------------
# Full scoring pipeline
# ------------------------------------------------------------------

class TestScoreEvidence:
    """End-to-end evidence scoring."""

    def test_score_evidence_returns_all_dimensions(self, scorer: EvidenceScorer):
        """score_evidence should populate every dimension field."""
        evidence = {
            "source_type": "official_data",
            "source_name": "NYC HPD",
            "published_date": date(2026, 2, 1),
            "content_summary": (
                "HPD reports a 15% increase in housing maintenance complaints "
                "across rent-stabilised buildings in Manhattan."
            ),
            "directional_effect": "negative",
            "expected_magnitude": 0.6,
            "uncertainty": 0.3,
        }
        question = {
            "title": "Will rent-stabilised apartment maintenance quality decline?",
            "description": "Tracks maintenance quality in stabilised housing.",
        }
        result = scorer.score_evidence(
            evidence_item=evidence,
            question=question,
            reference_date=date(2026, 3, 1),
        )

        assert 0.0 <= result.source_credibility <= 1.0
        assert 0.0 <= result.recency <= 1.0
        assert 0.0 <= result.relevance <= 1.0
        assert 0.0 <= result.redundancy <= 1.0
        assert 0.0 <= result.composite_weight <= 1.0
        assert result.directional_effect == "negative"
        assert result.expected_magnitude == pytest.approx(0.6)
        assert result.uncertainty == pytest.approx(0.3)
