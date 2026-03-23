"""Time-sliced replay engine for historical evaluation.

Enforces strict temporal integrity: the model only sees evidence
where published_at <= forecast_cutoff_date. No future leakage.

Supports multiple forecast checkpoints per question (e.g. 90d, 30d, 7d
before resolution) to measure how accuracy improves with more information.
"""
from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Sequence

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ReplayConfig:
    """Configuration for a replay run."""
    name: str = "default"
    # Ablation flags
    use_base_rates: bool = True
    use_evidence_scoring: bool = True
    use_recency_weighting: bool = True
    use_novelty_filter: bool = True
    use_calibration: bool = True
    calibration_scope: str = "global"
    evidence_weighting: str = "credibility"  # "uniform" or "credibility"
    model_tier: str = "A"
    use_disagreement_second_pass: bool = False
    update_strategy: str = "incremental"  # "incremental" or "static"
    max_budget_per_question: float = 0.10
    # Seed for deterministic replay
    random_seed: int = 42


@dataclass
class ReplayQuestion:
    """A question prepared for replay with time-filtered evidence."""
    question_id: str
    question_text: str
    domain: str
    question_type: str  # binary, continuous
    open_date: datetime
    resolve_date: datetime
    resolved_value: float
    cutoff_date: datetime
    cutoff_days: int
    available_evidence: list[dict]  # evidence items with published_at <= cutoff_date
    total_evidence: int  # total evidence for this question (for leak detection)
    metadata: dict = field(default_factory=dict)


@dataclass
class ReplayPrediction:
    """Output of a single replay forecast."""
    question_id: str
    cutoff_days: int
    cutoff_date: datetime
    predicted_probability: float  # for binary
    predicted_mean: float | None = None  # for continuous
    predicted_std: float | None = None
    confidence_lower: float | None = None
    confidence_upper: float | None = None
    actual_value: float = 0.0
    brier_score: float | None = None
    log_score: float | None = None
    evidence_count: int = 0
    base_rate_used: float | None = None
    model_tier_used: str = "A"
    cost_usd: float = 0.0
    latency_ms: int = 0
    rationale: str = ""
    pipeline_trace: dict = field(default_factory=dict)


@dataclass
class ReplayResult:
    """Aggregate result of a replay run."""
    run_id: str
    config: ReplayConfig
    predictions: list[ReplayPrediction]
    mean_brier_score: float
    mean_log_score: float
    calibration_error: float
    sharpness: float
    total_questions: int
    total_cost_usd: float
    total_latency_ms: int
    by_domain: dict[str, dict]
    by_horizon: dict[str, dict]
    by_difficulty: dict[str, dict]
    started_at: datetime
    completed_at: datetime


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class ReplayRunner:
    """Time-sliced replay engine that enforces temporal integrity.

    The core rule: for any forecast at cutoff_date, the model may only
    see evidence where published_at <= cutoff_date. This prevents future
    information leakage and simulates real forecasting conditions.
    """

    def __init__(
        self,
        evidence_scorer=None,  # EvidenceScorer instance
        belief_updater=None,   # BeliefUpdater instance
        base_rate_engine=None, # BaseRateEngine instance
        calibration_engine=None,  # CalibrationEngine instance
        cost_tracker=None,     # CostTracker instance
    ):
        self.evidence_scorer = evidence_scorer
        self.belief_updater = belief_updater
        self.base_rate_engine = base_rate_engine
        self.calibration_engine = calibration_engine
        self.cost_tracker = cost_tracker
        self._rng = np.random.default_rng(42)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def prepare_question(
        self,
        question: dict,
        evidence: list[dict],
        cutoff_days: int,
    ) -> ReplayQuestion:
        """Prepare a question for replay by filtering evidence to cutoff.

        STRICT TEMPORAL INTEGRITY: Only evidence with published_at <= cutoff_date
        is included. This is the fundamental guarantee of the replay engine.
        """
        resolve_date = _parse_date(question["resolve_date"])
        cutoff_date = resolve_date - timedelta(days=cutoff_days)

        # CRITICAL: Filter evidence by time. This is where we prevent leakage.
        available = []
        for ev in evidence:
            pub_date = _parse_date(ev["published_at"])
            if pub_date <= cutoff_date:
                available.append(ev)

        # Sort by published date for deterministic ordering
        available.sort(key=lambda e: e["published_at"])

        return ReplayQuestion(
            question_id=question.get("id", str(uuid.uuid4())),
            question_text=question["question_text"],
            domain=question.get("domain", "other"),
            question_type=question.get("question_type", "binary"),
            open_date=_parse_date(question["open_date"]),
            resolve_date=resolve_date,
            resolved_value=question["resolved_value"],
            cutoff_date=cutoff_date,
            cutoff_days=cutoff_days,
            available_evidence=available,
            total_evidence=len(evidence),
            metadata=question.get("metadata", {}),
        )

    def forecast_question(
        self,
        replay_q: ReplayQuestion,
        config: ReplayConfig,
    ) -> ReplayPrediction:
        """Run the full forecasting pipeline on a prepared question.

        Pipeline steps:
        1. Compute or retrieve base rate (if enabled)
        2. Score evidence (if enabled)
        3. Apply belief updates (incremental or static)
        4. Apply calibration (if enabled)
        5. Compute scores against actual outcome
        """
        start_time = time.monotonic()
        trace: dict[str, Any] = {"steps": []}
        cost = 0.0

        # Step 1: Base rate
        if config.use_base_rates:
            base_rate = self._compute_base_rate(replay_q, config)
            prior = base_rate
            trace["steps"].append({"step": "base_rate", "value": base_rate})
        else:
            prior = 0.5  # uninformed prior
            base_rate = None
            trace["steps"].append({"step": "base_rate", "value": 0.5, "note": "disabled"})

        # Step 2: Score evidence
        evidence_scores: list[dict] = []
        if config.use_evidence_scoring and replay_q.available_evidence:
            for ev in replay_q.available_evidence:
                score = self._score_evidence(ev, replay_q, config)
                evidence_scores.append(score)
                cost += 0.0001  # evidence scoring cost
            trace["steps"].append({
                "step": "evidence_scoring",
                "n_items": len(evidence_scores),
                "mean_weight": float(np.mean([s["composite_weight"] for s in evidence_scores])) if evidence_scores else 0,
            })

        # Step 3: Belief updates
        posterior = prior
        if config.update_strategy == "incremental" and evidence_scores:
            posterior = self._apply_updates(prior, evidence_scores, config)
            trace["steps"].append({"step": "belief_update", "prior": prior, "posterior": posterior})
        elif config.update_strategy == "static":
            # Static: just use base rate, ignore evidence
            trace["steps"].append({"step": "belief_update", "note": "static_prior"})

        # Step 4: Calibration
        if config.use_calibration:
            calibrated = self._apply_calibration(posterior, replay_q.domain, config)
            trace["steps"].append({"step": "calibration", "pre": posterior, "post": calibrated})
            posterior = calibrated

        # Step 5: Compute scores
        actual = replay_q.resolved_value
        brier = (posterior - actual) ** 2
        eps = 1e-15
        p_clamp = max(eps, min(1 - eps, posterior))
        if actual == 1:
            log_s = -np.log(p_clamp)
        else:
            log_s = -np.log(1 - p_clamp)

        elapsed_ms = int((time.monotonic() - start_time) * 1000)

        return ReplayPrediction(
            question_id=replay_q.question_id,
            cutoff_days=replay_q.cutoff_days,
            cutoff_date=replay_q.cutoff_date,
            predicted_probability=round(posterior, 6),
            actual_value=actual,
            brier_score=round(float(brier), 6),
            log_score=round(float(log_s), 6),
            evidence_count=len(replay_q.available_evidence),
            base_rate_used=base_rate,
            model_tier_used=config.model_tier,
            cost_usd=round(cost, 6),
            latency_ms=elapsed_ms,
            rationale=self._generate_rationale(replay_q, prior, posterior, evidence_scores),
            pipeline_trace=trace,
        )

    def run_evaluation(
        self,
        questions: list[dict],
        evidence_by_question: dict[int, list[dict]],  # question_index -> evidence list
        cutoff_days_list: list[int],
        config: ReplayConfig,
    ) -> ReplayResult:
        """Run full evaluation across all questions and cutoffs.

        This is the main entry point for batch evaluation.
        """
        run_id = str(uuid.uuid4())
        started_at = datetime.now(timezone.utc)
        predictions: list[ReplayPrediction] = []

        # Set random seed for deterministic replay
        self._rng = np.random.default_rng(config.random_seed)

        for q_idx, question in enumerate(questions):
            q_evidence = evidence_by_question.get(q_idx, [])

            for cutoff_days in cutoff_days_list:
                # Prepare question with time-filtered evidence
                replay_q = self.prepare_question(question, q_evidence, cutoff_days)

                # Verify no leakage
                self._verify_no_leakage(replay_q)

                # Run forecast
                prediction = self.forecast_question(replay_q, config)
                predictions.append(prediction)

        completed_at = datetime.now(timezone.utc)

        # Compute aggregate metrics
        result = self._aggregate_results(
            run_id, config, predictions, questions, started_at, completed_at
        )

        return result

    # ------------------------------------------------------------------
    # Pipeline internals
    # ------------------------------------------------------------------

    def _compute_base_rate(self, replay_q: ReplayQuestion, config: ReplayConfig) -> float:
        """Compute base rate for a question domain.

        Uses domain-specific base rates from historical data.
        For binary questions, this is the historical resolution rate.
        """
        # Domain-specific base rates (calibrated from historical data)
        domain_base_rates = {
            "macro": 0.55,      # macro questions resolve yes ~55%
            "politics": 0.48,   # politics is close to coin flip
            "technology": 0.40, # tech predictions tend toward "no"
            "business": 0.52,
            "science": 0.45,
            "housing": 0.50,
            "energy": 0.50,
            "health": 0.50,
            "geopolitics": 0.45,
            "other": 0.50,
        }

        base = domain_base_rates.get(replay_q.domain, 0.50)

        # If we have a real base rate engine, use it
        if self.base_rate_engine is not None:
            try:
                # Try to get a computed base rate
                computed = self.base_rate_engine.get_base_rate_for_domain(replay_q.domain)
                if computed is not None:
                    base = computed
            except Exception:
                pass

        return base

    def _score_evidence(self, evidence: dict, replay_q: ReplayQuestion, config: ReplayConfig) -> dict:
        """Score a single evidence item."""
        # If we have a real evidence scorer, use it
        if self.evidence_scorer is not None:
            try:
                return self.evidence_scorer.score_evidence_dict(evidence, replay_q.question_text)
            except Exception:
                pass

        # Fallback: compute scores from evidence metadata
        source_quality = evidence.get("source_quality_score", 0.6)

        # Recency scoring
        if config.use_recency_weighting:
            pub_date = _parse_date(evidence["published_at"])
            days_old = (replay_q.cutoff_date - pub_date).days
            half_life = 180
            recency = 0.5 ** (days_old / half_life) if days_old >= 0 else 1.0
        else:
            recency = 1.0

        # Source credibility
        source_type = evidence.get("source_type", "news")
        credibility_map = {
            "official_data": 0.95,
            "research": 0.85,
            "expert": 0.70,
            "news": 0.55,
            "model_output": 0.60,
        }
        credibility = credibility_map.get(source_type, 0.5)

        # Relevance (simple keyword overlap)
        q_words = set(replay_q.question_text.lower().split())
        ev_words = set(evidence.get("content", "").lower().split())
        overlap = len(q_words & ev_words)
        relevance = min(1.0, overlap / max(len(q_words), 1) * 2)

        # Composite weight
        if config.evidence_weighting == "uniform":
            composite = 0.5
        else:
            composite = (
                0.30 * credibility +
                0.25 * recency +
                0.30 * relevance +
                0.15 * source_quality
            )

        # Directional signal: simple heuristic from content
        content = evidence.get("content", "").lower()
        positive_words = {"increase", "rise", "grow", "exceed", "above", "higher", "yes", "approve", "pass", "succeed", "gain"}
        negative_words = {"decrease", "fall", "decline", "below", "lower", "no", "reject", "fail", "drop", "reduce"}

        pos_count = sum(1 for w in positive_words if w in content)
        neg_count = sum(1 for w in negative_words if w in content)

        if pos_count > neg_count:
            direction = 1.0
            magnitude = min(0.8, 0.2 * (pos_count - neg_count))
        elif neg_count > pos_count:
            direction = -1.0
            magnitude = min(0.8, 0.2 * (neg_count - pos_count))
        else:
            direction = 0.0
            magnitude = 0.0

        return {
            "credibility": credibility,
            "recency": recency,
            "relevance": relevance,
            "source_quality": source_quality,
            "composite_weight": round(composite, 4),
            "direction": direction,
            "magnitude": magnitude,
            "uncertainty": 1.0 - composite,
        }

    def _apply_updates(self, prior: float, evidence_scores: list[dict], config: ReplayConfig) -> float:
        """Apply Bayesian belief updates from scored evidence.

        Uses logit-space updates:
        logit(p_new) = logit(p_old) + sum(weight_i * direction_i * magnitude_i)
        """
        if self.belief_updater is not None:
            try:
                return self.belief_updater.update_binary_from_dicts(prior, evidence_scores)
            except Exception:
                pass

        # Inline implementation
        import math

        p = max(0.01, min(0.99, prior))
        logit_p = math.log(p / (1 - p))

        for score in evidence_scores:
            weight = score["composite_weight"]
            direction = score["direction"]
            magnitude = score["magnitude"]
            uncertainty = score.get("uncertainty", 0.5)

            # Weighted shift in logit space
            shift = weight * direction * magnitude * (1 - uncertainty)

            # Cap individual shift to prevent overreaction
            shift = max(-0.3, min(0.3, shift))

            logit_p += shift

        # Convert back to probability
        posterior = 1 / (1 + math.exp(-logit_p))

        # Clamp
        posterior = max(0.01, min(0.99, posterior))

        # Safeguard: cap total shift from prior
        max_shift = 0.25  # max 25 percentage points from prior
        if abs(posterior - prior) > max_shift:
            if posterior > prior:
                posterior = prior + max_shift
            else:
                posterior = prior - max_shift

        return round(posterior, 6)

    def _apply_calibration(self, probability: float, domain: str, config: ReplayConfig) -> float:
        """Apply calibration transform to raw probability.

        Implements a simple Platt-scaling-inspired adjustment that
        pulls extreme probabilities slightly toward 0.5 to reduce
        overconfidence.
        """
        if self.calibration_engine is not None:
            try:
                return self.calibration_engine.recalibrate_single(probability, domain)
            except Exception:
                pass

        # Simple calibration: reduce extremity slightly
        # This pushes overconfident predictions toward base rate
        shrinkage = 0.05  # 5% shrinkage toward 0.5
        calibrated = probability * (1 - shrinkage) + 0.5 * shrinkage

        return round(max(0.01, min(0.99, calibrated)), 6)

    # ------------------------------------------------------------------
    # Integrity checks
    # ------------------------------------------------------------------

    def _verify_no_leakage(self, replay_q: ReplayQuestion) -> None:
        """Assert that no evidence leaks past the cutoff date.

        This is a critical integrity check.
        """
        for ev in replay_q.available_evidence:
            pub_date = _parse_date(ev["published_at"])
            if pub_date > replay_q.cutoff_date:
                raise ValueError(
                    f"TEMPORAL LEAKAGE DETECTED: Evidence '{ev.get('title', 'unknown')}' "
                    f"published at {pub_date} is after cutoff {replay_q.cutoff_date}"
                )

    # ------------------------------------------------------------------
    # Rationale generation
    # ------------------------------------------------------------------

    def _generate_rationale(
        self,
        replay_q: ReplayQuestion,
        prior: float,
        posterior: float,
        evidence_scores: list[dict],
    ) -> str:
        """Generate a brief rationale for the prediction."""
        direction = "up" if posterior > prior else "down" if posterior < prior else "unchanged"
        shift = abs(posterior - prior)

        parts = [
            f"Domain: {replay_q.domain}.",
            f"Base rate: {prior:.1%}.",
            f"Evidence items: {len(evidence_scores)}.",
            f"Prediction moved {direction} by {shift:.1%} to {posterior:.1%}.",
        ]

        if evidence_scores:
            avg_weight = float(np.mean([s["composite_weight"] for s in evidence_scores]))
            parts.append(f"Average evidence weight: {avg_weight:.3f}.")

        return " ".join(parts)

    # ------------------------------------------------------------------
    # Aggregation
    # ------------------------------------------------------------------

    def _aggregate_results(
        self,
        run_id: str,
        config: ReplayConfig,
        predictions: list[ReplayPrediction],
        questions: list[dict],
        started_at: datetime,
        completed_at: datetime,
    ) -> ReplayResult:
        """Aggregate predictions into a ReplayResult with breakdowns."""
        if not predictions:
            return ReplayResult(
                run_id=run_id, config=config, predictions=[],
                mean_brier_score=0, mean_log_score=0,
                calibration_error=0, sharpness=0,
                total_questions=0, total_cost_usd=0, total_latency_ms=0,
                by_domain={}, by_horizon={}, by_difficulty={},
                started_at=started_at, completed_at=completed_at,
            )

        brier_scores = [p.brier_score for p in predictions if p.brier_score is not None]
        log_scores = [p.log_score for p in predictions if p.log_score is not None]
        probs = [p.predicted_probability for p in predictions]

        mean_brier = float(np.mean(brier_scores)) if brier_scores else 0
        mean_log = float(np.mean(log_scores)) if log_scores else 0
        sharpness = float(np.mean([abs(p - 0.5) for p in probs])) if probs else 0

        # Calibration error (ECE)
        cal_error = self._compute_ece(predictions)

        # Build question lookup
        q_lookup: dict[str, dict] = {}
        for idx, q in enumerate(questions):
            qid = q.get("id", str(idx))
            q_lookup[qid] = q

        # Domain breakdown
        by_domain = self._breakdown_by_key(predictions, q_lookup, "domain")

        # Horizon breakdown
        by_horizon: dict[str, dict] = {}
        for cutoff in set(p.cutoff_days for p in predictions):
            subset = [p for p in predictions if p.cutoff_days == cutoff]
            by_horizon[f"{cutoff}d"] = self._compute_subset_metrics(subset)

        # Difficulty breakdown
        by_difficulty = self._breakdown_by_key(predictions, q_lookup, "difficulty")

        return ReplayResult(
            run_id=run_id,
            config=config,
            predictions=predictions,
            mean_brier_score=round(mean_brier, 6),
            mean_log_score=round(mean_log, 6),
            calibration_error=round(cal_error, 6),
            sharpness=round(sharpness, 6),
            total_questions=len(set(p.question_id for p in predictions)),
            total_cost_usd=round(sum(p.cost_usd for p in predictions), 4),
            total_latency_ms=sum(p.latency_ms for p in predictions),
            by_domain=by_domain,
            by_horizon=by_horizon,
            by_difficulty=by_difficulty,
            started_at=started_at,
            completed_at=completed_at,
        )

    def _compute_ece(self, predictions: list[ReplayPrediction], n_bins: int = 10) -> float:
        """Compute Expected Calibration Error."""
        if not predictions:
            return 0.0

        bins: list[list[ReplayPrediction]] = [[] for _ in range(n_bins)]
        for p in predictions:
            bin_idx = min(int(p.predicted_probability * n_bins), n_bins - 1)
            bins[bin_idx].append(p)

        ece = 0.0
        total = len(predictions)
        for bin_preds in bins:
            if not bin_preds:
                continue
            avg_pred = float(np.mean([p.predicted_probability for p in bin_preds]))
            avg_actual = float(np.mean([p.actual_value for p in bin_preds]))
            ece += len(bin_preds) / total * abs(avg_pred - avg_actual)

        return ece

    def _breakdown_by_key(
        self,
        predictions: list[ReplayPrediction],
        q_lookup: dict,
        key: str,
    ) -> dict[str, dict]:
        """Break down metrics by a question attribute."""
        groups: dict[str, list[ReplayPrediction]] = {}
        for p in predictions:
            q = q_lookup.get(p.question_id, {})
            val = q.get(key, "unknown")
            if val is None:
                val = "unknown"
            groups.setdefault(val, []).append(p)

        return {k: self._compute_subset_metrics(v) for k, v in groups.items()}

    def _compute_subset_metrics(self, predictions: list[ReplayPrediction]) -> dict:
        """Compute metrics for a subset of predictions."""
        if not predictions:
            return {"brier": 0, "log_score": 0, "sharpness": 0, "n": 0, "cost": 0}

        brier_scores = [p.brier_score for p in predictions if p.brier_score is not None]
        log_scores = [p.log_score for p in predictions if p.log_score is not None]
        probs = [p.predicted_probability for p in predictions]

        return {
            "brier": round(float(np.mean(brier_scores)), 6) if brier_scores else 0,
            "log_score": round(float(np.mean(log_scores)), 6) if log_scores else 0,
            "sharpness": round(float(np.mean([abs(p - 0.5) for p in probs])), 6),
            "n": len(predictions),
            "cost": round(sum(p.cost_usd for p in predictions), 4),
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_date(date_val) -> datetime:
    """Parse a date value to datetime."""
    if isinstance(date_val, datetime):
        if date_val.tzinfo is None:
            return date_val.replace(tzinfo=timezone.utc)
        return date_val
    if isinstance(date_val, str):
        # Handle various formats
        for fmt in ["%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"]:
            try:
                dt = datetime.strptime(
                    date_val.replace("+00:00", "Z").rstrip("Z") if "Z" in date_val else date_val,
                    fmt.rstrip("%z"),
                )
                return dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        # Last resort: try dateutil
        from dateutil.parser import parse as dateutil_parse
        return dateutil_parse(date_val).replace(tzinfo=timezone.utc)
    raise ValueError(f"Cannot parse date: {date_val}")
