#!/usr/bin/env python3
"""
Standalone evaluation runner — no database, no Docker required.

Just: pip install numpy && python run_eval.py

Usage:
    python run_eval.py                           # run full eval with defaults
    python run_eval.py --cutoffs 90,30,7         # specify cutoff horizons
    python run_eval.py --ablation                # run all ablation experiments
    python run_eval.py --no-base-rates           # disable base rates
    python run_eval.py --no-calibration          # disable calibration
    python run_eval.py --no-evidence             # disable evidence scoring
    python run_eval.py --domain macro            # filter to one domain
    python run_eval.py --difficulty hard          # filter by difficulty
    python run_eval.py --verbose                 # show per-question predictions
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from dataclasses import dataclass
from datetime import timedelta

from forecast.config import (
    CALIBRATION_SHRINKAGE,
    DOMAIN_BASE_RATES,
    MAX_EVIDENCE_SHIFT,
    NEGATIVE_WORDS,
    POSITIVE_WORDS,
    SOURCE_CREDIBILITY,
)
from forecast.data import filter_questions, load_seed_questions
from forecast.dates import parse_date
from forecast.display import (
    print_comparison_table,
    print_domain_breakdown,
    print_header,
    print_horizon_breakdown,
    print_prediction_row,
)
from forecast.metrics import baseline_always_half, baseline_base_rate, compute_metrics, skill_score


@dataclass
class ForecastConfig:
    name: str = "default"
    use_base_rates: bool = True
    use_evidence: bool = True
    use_recency: bool = True
    use_calibration: bool = True
    evidence_weighting: str = "credibility"
    max_shift: float = 0.25


@dataclass
class Prediction:
    question_idx: int
    question_text: str
    domain: str
    difficulty: str
    cutoff_days: int
    predicted: float
    actual: float
    brier: float
    log_score: float
    evidence_count: int
    base_rate: float


def score_evidence(ev: dict, question_text: str, cutoff_date, config: ForecastConfig) -> dict:
    credibility = SOURCE_CREDIBILITY.get(ev.get("source_type", "news"), 0.5)
    quality = ev.get("source_quality_score", 0.6)

    if config.use_recency:
        pub = parse_date(ev["published_at"])
        days_old = max(0, (cutoff_date - pub).days)
        recency = 0.5 ** (days_old / 180)
    else:
        recency = 1.0

    q_words = set(question_text.lower().split())
    ev_words = set(ev.get("content", "").lower().split())
    overlap = len(q_words & ev_words)
    relevance = min(1.0, overlap / max(len(q_words), 1) * 2)

    if config.evidence_weighting == "uniform":
        weight = 0.5
    else:
        weight = 0.30 * credibility + 0.25 * recency + 0.30 * relevance + 0.15 * quality

    content = ev.get("content", "").lower()
    pos = sum(1 for w in POSITIVE_WORDS if w in content)
    neg = sum(1 for w in NEGATIVE_WORDS if w in content)
    if pos > neg:
        direction, magnitude = 1.0, min(0.8, 0.2 * (pos - neg))
    elif neg > pos:
        direction, magnitude = -1.0, min(0.8, 0.2 * (neg - pos))
    else:
        direction, magnitude = 0.0, 0.0

    return {"weight": weight, "direction": direction, "magnitude": magnitude, "uncertainty": 1 - weight}


def forecast_question(question: dict, evidence: list[dict], cutoff_days: int, config: ForecastConfig) -> Prediction:
    resolve_date = parse_date(question["resolve_date"])
    cutoff_date = resolve_date - timedelta(days=cutoff_days)
    actual = question["resolved_value"]
    domain = question.get("domain", "other")

    prior = DOMAIN_BASE_RATES.get(domain, 0.5) if config.use_base_rates else 0.5
    base_rate = prior

    available = [e for e in evidence if parse_date(e["published_at"]) <= cutoff_date]
    available.sort(key=lambda e: e["published_at"])

    posterior = prior
    if config.use_evidence and available:
        scores = [score_evidence(e, question["question_text"], cutoff_date, config) for e in available]
        p = max(0.01, min(0.99, posterior))
        logit_p = math.log(p / (1 - p))
        for s in scores:
            shift = s["weight"] * s["direction"] * s["magnitude"] * (1 - s["uncertainty"])
            shift = max(-MAX_EVIDENCE_SHIFT, min(MAX_EVIDENCE_SHIFT, shift))
            logit_p += shift
        posterior = 1 / (1 + math.exp(-logit_p))
        posterior = max(0.01, min(0.99, posterior))
        if abs(posterior - prior) > config.max_shift:
            posterior = prior + config.max_shift if posterior > prior else prior - config.max_shift

    if config.use_calibration:
        posterior = posterior * (1 - CALIBRATION_SHRINKAGE) + 0.5 * CALIBRATION_SHRINKAGE

    posterior = round(max(0.01, min(0.99, posterior)), 6)
    brier = (posterior - actual) ** 2
    eps = 1e-15
    p_c = max(eps, min(1 - eps, posterior))
    log_s = -(actual * math.log(p_c) + (1 - actual) * math.log(1 - p_c))

    return Prediction(
        question_idx=question.get("_idx", 0),
        question_text=question["question_text"],
        domain=domain,
        difficulty=question.get("difficulty", "medium"),
        cutoff_days=cutoff_days,
        predicted=posterior,
        actual=actual,
        brier=round(brier, 6),
        log_score=round(log_s, 6),
        evidence_count=len(available),
        base_rate=base_rate,
    )


def run_single(questions, evidence_by_q, cutoffs, config):
    preds = []
    for i, q in enumerate(questions):
        q["_idx"] = i
        ev = evidence_by_q.get(i, [])
        for cutoff in cutoffs:
            preds.append(forecast_question(q, ev, cutoff, config))
    return preds


def print_results(preds: list[Prediction], config_name: str, verbose: bool = False) -> None:
    metrics = compute_metrics(preds)
    actuals = [p.actual for p in preds]
    half_brier = baseline_always_half(actuals)
    br_brier = baseline_base_rate(actuals)

    print_header(f"EVALUATION: {config_name}")
    print(f"  Mean Brier Score:     {metrics['brier']:.4f}")
    print(f"  Mean Log Score:       {metrics['log_score']:.4f}")
    print(f"  Calibration Error:    {metrics['ece']:.4f}")
    print(f"  Sharpness:            {metrics['sharpness']:.4f}")
    print(f"  Predictions:          {metrics['n']}")
    print(f"{'=' * 65}")
    print(
        f"  vs Always-0.5:        {metrics['brier'] - half_brier:+.4f} {'(better)' if metrics['brier'] < half_brier else '(worse)'}"
    )
    print(
        f"  vs Base-Rate-Only:    {metrics['brier'] - br_brier:+.4f} {'(better)' if metrics['brier'] < br_brier else '(worse)'}"
    )
    print(f"  Skill Score:          {skill_score(metrics['brier'], half_brier):.4f}")

    print_domain_breakdown(preds, compute_metrics)
    cutoffs = sorted({p.cutoff_days for p in preds})
    print_horizon_breakdown(preds, cutoffs, compute_metrics)
    print(f"{'=' * 65}\n")

    if verbose:
        print(f"  {'Question':<55} {'Cut':>4} {'Pred':>6} {'Act':>4} {'Brier':>7}")
        print(f"  {'-' * 80}")
        for p in sorted(preds, key=lambda x: -x.brier)[:20]:
            print_prediction_row(p)
        if len(preds) > 20:
            print(f"  ... and {len(preds) - 20} more predictions")
        print()


def run_ablation(questions, evidence_by_q, cutoffs):
    configs = {
        "default (full pipeline)": ForecastConfig(name="default"),
        "no base rates": ForecastConfig(name="no_base_rates", use_base_rates=False),
        "no calibration": ForecastConfig(name="no_calibration", use_calibration=False),
        "no evidence": ForecastConfig(name="no_evidence", use_evidence=False),
        "no recency": ForecastConfig(name="no_recency", use_recency=False),
        "uniform weights": ForecastConfig(name="uniform_weights", evidence_weighting="uniform"),
        "base rate only (static)": ForecastConfig(name="static", use_evidence=False, use_calibration=False),
    }

    total = len(questions) * len(cutoffs)
    print(f"\n{'=' * 90}")
    print(
        f"  ABLATION EXPERIMENT — {len(questions)} questions x {len(cutoffs)} cutoffs = {total} predictions per config"
    )
    print(f"{'=' * 90}\n")

    results = {}
    for name, config in configs.items():
        start = time.time()
        preds = run_single(questions, evidence_by_q, cutoffs, config)
        elapsed = time.time() - start
        m = compute_metrics(preds)
        results[name] = {"metrics": m, "preds": preds, "time": elapsed}
        print(f"  {name:<30} Brier={m['brier']:.4f}  Log={m['log_score']:.4f}  ECE={m['ece']:.4f}  ({elapsed:.2f}s)")

    print_comparison_table(results)

    best_name = min(results, key=lambda k: results[k]["metrics"]["brier"])
    best_actuals = [p.actual for p in results[best_name]["preds"]]
    half_b = baseline_always_half(best_actuals)
    br_b = baseline_base_rate(best_actuals)
    best_brier = results[best_name]["metrics"]["brier"]
    print(f"\n  Baselines:  Always-0.5 Brier = {half_b:.4f}  |  Base-Rate Brier = {br_b:.4f}")
    print(f"  Best model beats always-0.5 by {half_b - best_brier:+.4f}")
    print(f"{'=' * 90}\n")


def main():
    parser = argparse.ArgumentParser(description="Run forecasting evaluations")
    parser.add_argument("--data-dir", default="data/seeds")
    parser.add_argument("--cutoffs", default="90,30,7", help="Cutoff days, comma-separated")
    parser.add_argument("--ablation", action="store_true", help="Run all ablation experiments")
    parser.add_argument("--domain", help="Filter to one domain")
    parser.add_argument("--difficulty", help="Filter by difficulty (easy/medium/hard)")
    parser.add_argument("--no-base-rates", action="store_true")
    parser.add_argument("--no-calibration", action="store_true")
    parser.add_argument("--no-evidence", action="store_true")
    parser.add_argument("--no-recency", action="store_true")
    parser.add_argument("--uniform-weights", action="store_true")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show per-question predictions")
    parser.add_argument("--output", "-o", help="Save results to JSON file")
    args = parser.parse_args()

    cutoffs = [int(x) for x in args.cutoffs.split(",")]
    questions, evidence_by_q = load_seed_questions(args.data_dir)
    print(f"Loaded {len(questions)} questions, {sum(len(v) for v in evidence_by_q.values())} evidence items")

    questions, evidence_by_q = filter_questions(
        questions, evidence_by_q, domain=args.domain, difficulty=args.difficulty
    )
    if args.domain:
        print(f"Filtered to {len(questions)} {args.domain} questions")
    if args.difficulty:
        print(f"Filtered to {len(questions)} {args.difficulty} questions")

    if not questions:
        print("No questions match filters. Exiting.")
        sys.exit(1)

    if args.ablation:
        run_ablation(questions, evidence_by_q, cutoffs)
        return

    config = ForecastConfig(
        use_base_rates=not args.no_base_rates,
        use_evidence=not args.no_evidence,
        use_recency=not args.no_recency,
        use_calibration=not args.no_calibration,
        evidence_weighting="uniform" if args.uniform_weights else "credibility",
    )

    start = time.time()
    preds = run_single(questions, evidence_by_q, cutoffs, config)
    elapsed = time.time() - start

    print(f"Evaluation completed in {elapsed:.2f}s")
    print_results(preds, config.name, verbose=args.verbose)

    if args.output:
        metrics = compute_metrics(preds)
        output = {
            "config": dict(config.__dict__.items()),
            "metrics": metrics,
            "elapsed_seconds": round(elapsed, 2),
            "predictions": [
                {
                    "question": p.question_text,
                    "domain": p.domain,
                    "cutoff": p.cutoff_days,
                    "predicted": p.predicted,
                    "actual": p.actual,
                    "brier": p.brier,
                }
                for p in preds
            ],
        }
        with open(args.output, "w") as f:
            json.dump(output, f, indent=2)
        print(f"Results saved to {args.output}")


if __name__ == "__main__":
    main()
