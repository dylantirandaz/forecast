"""Evidence scoring engine.

Evaluates each piece of evidence across multiple quality dimensions and
produces a composite weight that the belief updater consumes.
"""

from __future__ import annotations

import logging
import math
import re
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Scoring rubric constants
# ---------------------------------------------------------------------------

# Source credibility: official data is most trusted, expert opinion less so.
SOURCE_CREDIBILITY_MAP: dict[str, float] = {
    "official_data": 0.95,   # Census, HVS, NYCHVS, HPD, RGB orders
    "research": 0.85,        # Peer-reviewed / think-tank reports
    "model_output": 0.75,    # Our own or third-party models
    "news": 0.55,            # Reputable journalism
    "expert": 0.65,          # Named expert opinion or testimony
}

# Named-source bonuses (additive, capped at 1.0).
SOURCE_NAME_BONUS: dict[str, float] = {
    "us_census_bureau": 0.05,
    "nychvs": 0.05,
    "nyc_hpd": 0.05,
    "rgb": 0.05,             # Rent Guidelines Board
    "furman_center": 0.04,
    "comptroller": 0.03,
    "reuters": 0.02,
    "associated_press": 0.02,
}

# Recency half-life in days.  Evidence older than this is exponentially
# down-weighted.  180 days ≈ 6 months is calibrated for housing-market
# pace of change.
RECENCY_HALF_LIFE_DAYS: float = 180.0

# Keyword pools used for lightweight relevance matching.
HOUSING_KEYWORDS: set[str] = {
    "rent", "housing", "apartment", "tenant", "landlord",
    "vacancy", "stabilised", "stabilized", "affordable",
    "eviction", "hpd", "rgb", "lease", "shelter", "homelessness",
    "construction", "permit", "zoning", "mortgage", "hcv",
    "section 8", "nycha", "cpi", "inflation", "interest rate",
    "property tax", "assessment", "maintenance", "capital",
    "displacement", "gentrification", "median income",
}


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------

@dataclass
class EvidenceScoreResult:
    """All scoring dimensions plus the composite weight."""

    source_credibility: float
    recency: float
    relevance: float
    redundancy: float  # 0 = fully redundant, 1 = entirely novel
    composite_weight: float
    directional_effect: str  # "positive" | "negative" | "neutral" | "ambiguous"
    expected_magnitude: float  # 0-1 scale
    uncertainty: float  # 0-1 scale
    details: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class EvidenceScorer:
    """Score evidence items along multiple quality dimensions.

    The scorer is stateless: you create one instance and call
    :py:meth:`score_evidence` for each evidence item.  The composite
    weight is a weighted combination of the individual dimension scores.

    Dimension weights (must sum to 1.0):
        source_credibility  0.30
        recency             0.25
        relevance           0.30
        redundancy          0.15
    """

    # Dimension weights for the composite score.
    W_CREDIBILITY: float = 0.30
    W_RECENCY: float = 0.25
    W_RELEVANCE: float = 0.30
    W_REDUNDANCY: float = 0.15

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def score_evidence(
        self,
        evidence_item: dict[str, Any],
        question: dict[str, Any],
        existing_evidence: Sequence[dict[str, Any]] | None = None,
        reference_date: date | None = None,
    ) -> EvidenceScoreResult:
        """Score a single evidence item against a forecasting question.

        Parameters
        ----------
        evidence_item:
            Dict-like representation with at least ``source_type``,
            ``source_name`` (optional), ``published_date`` (str or date),
            ``content_summary``, ``directional_effect``,
            ``expected_magnitude``, and ``uncertainty``.
        question:
            Dict-like with at least ``title`` and ``description``.
        existing_evidence:
            Previously scored evidence items used for redundancy check.
        reference_date:
            Date against which to measure recency.  Defaults to today.

        Returns
        -------
        EvidenceScoreResult
        """
        if reference_date is None:
            reference_date = date.today()

        source_cred = self.compute_source_credibility(
            source_type=evidence_item.get("source_type", "news"),
            source_name=evidence_item.get("source_name"),
        )

        pub_date = evidence_item.get("published_date")
        if isinstance(pub_date, str):
            pub_date = date.fromisoformat(pub_date)
        recency = self.compute_recency(pub_date, reference_date)

        relevance = self.compute_relevance(
            evidence_summary=evidence_item.get("content_summary", ""),
            question_description=(
                f"{question.get('title', '')} {question.get('description', '')}"
            ),
        )

        redundancy = self.compute_redundancy(
            evidence_item, existing_evidence or []
        )

        composite = self.compute_composite_weight(
            source_credibility=source_cred,
            recency=recency,
            relevance=relevance,
            redundancy=redundancy,
        )

        directional = evidence_item.get("directional_effect", "neutral")
        magnitude = float(evidence_item.get("expected_magnitude", 0.5))
        uncertainty = float(evidence_item.get("uncertainty", 0.5))

        return EvidenceScoreResult(
            source_credibility=source_cred,
            recency=recency,
            relevance=relevance,
            redundancy=redundancy,
            composite_weight=composite,
            directional_effect=directional,
            expected_magnitude=magnitude,
            uncertainty=uncertainty,
        )

    # ------------------------------------------------------------------
    # Dimension scorers
    # ------------------------------------------------------------------

    @staticmethod
    def compute_source_credibility(
        source_type: str,
        source_name: str | None = None,
    ) -> float:
        """Score source credibility on a 0-1 scale.

        The base score comes from `SOURCE_CREDIBILITY_MAP`; known
        high-authority source names receive an additive bonus, capped at
        1.0.

        Parameters
        ----------
        source_type:
            One of ``"official_data"``, ``"research"``, ``"model_output"``,
            ``"news"``, ``"expert"``.
        source_name:
            Optional canonical name of the source organisation.

        Returns
        -------
        float  (0-1)
        """
        base = SOURCE_CREDIBILITY_MAP.get(source_type, 0.40)

        bonus = 0.0
        if source_name:
            normalised = (
                source_name.lower().replace(" ", "_").replace("-", "_")
            )
            bonus = SOURCE_NAME_BONUS.get(normalised, 0.0)

        return min(base + bonus, 1.0)

    @staticmethod
    def compute_recency(
        published_date: date | None,
        reference_date: date,
        half_life_days: float = RECENCY_HALF_LIFE_DAYS,
    ) -> float:
        """Exponential-decay recency score.

        score = 2^(-age_days / half_life_days)

        A piece of evidence published *today* scores 1.0; after one
        half-life it scores 0.5; after two half-lives 0.25, etc.

        If ``published_date`` is ``None``, returns a conservative 0.3
        (roughly 1.3 half-lives old).

        Parameters
        ----------
        published_date:
            When the evidence was published.
        reference_date:
            The "now" date for the forecast.
        half_life_days:
            Exponential decay half-life in days.

        Returns
        -------
        float  (0-1)
        """
        if published_date is None:
            return 0.30

        age_days = (reference_date - published_date).days
        if age_days < 0:
            # Future-dated evidence: full score.
            return 1.0

        return math.pow(2.0, -age_days / half_life_days)

    @staticmethod
    def compute_relevance(
        evidence_summary: str,
        question_description: str,
    ) -> float:
        """Keyword-overlap relevance score.

        Tokenises both strings, intersects with the domain keyword pool,
        then computes a Jaccard-like overlap ratio boosted by absolute
        match count.

        The score blends:
            - keyword_overlap_ratio  (Jaccard index of domain tokens)
            - raw_overlap_bonus      (more matching keywords → higher)

        Parameters
        ----------
        evidence_summary:
            Free-text summary of the evidence.
        question_description:
            Concatenation of question title and description.

        Returns
        -------
        float  (0-1)
        """

        def _tokenise(text: str) -> set[str]:
            return set(re.findall(r"[a-z0-9]+", text.lower()))

        ev_tokens = _tokenise(evidence_summary) & HOUSING_KEYWORDS
        q_tokens = _tokenise(question_description) & HOUSING_KEYWORDS

        if not q_tokens:
            # If the question has no recognisable domain tokens, fall
            # back to direct token overlap.
            ev_all = _tokenise(evidence_summary)
            q_all = _tokenise(question_description)
            if not q_all:
                return 0.5  # neutral
            overlap = len(ev_all & q_all)
            return min(overlap / max(len(q_all), 1), 1.0)

        union = ev_tokens | q_tokens
        intersection = ev_tokens & q_tokens

        if not union:
            return 0.3

        jaccard = len(intersection) / len(union)

        # Bonus: each additional keyword hit adds 0.05, capped at 0.3.
        raw_bonus = min(len(intersection) * 0.05, 0.30)

        score = 0.6 * jaccard + 0.4 * (raw_bonus / 0.30)
        return min(max(score, 0.0), 1.0)

    @staticmethod
    def compute_redundancy(
        evidence: dict[str, Any],
        existing_evidence: Sequence[dict[str, Any]],
    ) -> float:
        """Novelty score (1 = fully novel, 0 = fully redundant).

        Uses simple token-overlap between the new evidence summary and
        all previously scored evidence summaries.  If the maximum overlap
        exceeds a threshold, the score decreases proportionally.

        Parameters
        ----------
        evidence:
            The new evidence item (must have ``content_summary``).
        existing_evidence:
            Previously scored items.

        Returns
        -------
        float  (0-1)
        """
        if not existing_evidence:
            return 1.0

        def _tokens(text: str) -> set[str]:
            return set(re.findall(r"[a-z0-9]+", text.lower()))

        new_tokens = _tokens(evidence.get("content_summary", ""))
        if not new_tokens:
            return 1.0

        max_overlap = 0.0
        for existing in existing_evidence:
            old_tokens = _tokens(existing.get("content_summary", ""))
            if not old_tokens:
                continue
            overlap = len(new_tokens & old_tokens) / len(new_tokens)
            max_overlap = max(max_overlap, overlap)

        # Overlap > 0.7 → highly redundant.
        if max_overlap > 0.7:
            return max(1.0 - max_overlap, 0.05)
        return 1.0 - 0.5 * max_overlap

    # ------------------------------------------------------------------
    # Composite weight
    # ------------------------------------------------------------------

    def compute_composite_weight(
        self,
        source_credibility: float,
        recency: float,
        relevance: float,
        redundancy: float,
    ) -> float:
        """Weighted combination of all dimension scores.

        Parameters
        ----------
        source_credibility, recency, relevance, redundancy:
            Individual dimension scores, each on 0-1.

        Returns
        -------
        float  (0-1)
        """
        composite = (
            self.W_CREDIBILITY * source_credibility
            + self.W_RECENCY * recency
            + self.W_RELEVANCE * relevance
            + self.W_REDUNDANCY * redundancy
        )
        return min(max(composite, 0.0), 1.0)
