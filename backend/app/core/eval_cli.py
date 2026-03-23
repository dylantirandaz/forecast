"""CLI runner for evaluation and ablation experiments.

Usage:
    python -m app.core.eval_cli run --set resolved_80 --cutoffs 90,30,7
    python -m app.core.eval_cli ablation --set resolved_80 --configs default,no_base_rates,no_calibration
    python -m app.core.eval_cli compare --runs <run_id_1> <run_id_2>
    python -m app.core.eval_cli report --run <run_id>
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np


def load_seed_data(data_dir: Path) -> tuple[list[dict], dict[int, list[dict]], list[dict]]:
    """Load seed questions and evidence from JSON files."""
    questions_file = data_dir / "seed_historical_questions.json"
    evidence_file = data_dir / "seed_historical_evidence.json"

    with open(questions_file) as f:
        questions = json.load(f)

    evidence_by_question: dict[int, list[dict]] = {}
    if evidence_file.exists():
        with open(evidence_file) as f:
            evidence_items = json.load(f)
        for ev in evidence_items:
            q_idx = ev.get("question_index", 0)
            evidence_by_question.setdefault(q_idx, []).append(ev)

    return questions, evidence_by_question, []


def run_evaluation(args: argparse.Namespace) -> dict:
    """Run a single evaluation."""
    from app.services.replay_engine import ReplayRunner, ReplayConfig
    from app.services.eval_metrics import EvalMetricsEngine

    data_dir = Path(args.data_dir)
    questions, evidence_by_q, _ = load_seed_data(data_dir)

    # Filter by set if specified
    if args.set and args.set != "all":
        sets_file = data_dir / "seed_evaluation_sets.json"
        if sets_file.exists():
            with open(sets_file) as f:
                eval_sets = json.load(f)
            for es in eval_sets:
                if es["name"] == args.set:
                    if "question_indices" in es:
                        indices = es["question_indices"]
                        questions = [questions[i] for i in indices if i < len(questions)]
                    break

    cutoffs = [int(x) for x in args.cutoffs.split(",")]

    config = ReplayConfig(
        name=args.name or f"eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        use_base_rates=not args.no_base_rates,
        use_evidence_scoring=not args.no_evidence_scoring,
        use_recency_weighting=not args.no_recency,
        use_novelty_filter=not args.no_novelty,
        use_calibration=not args.no_calibration,
        evidence_weighting=args.evidence_weighting,
        model_tier=args.model_tier,
        use_disagreement_second_pass=args.second_pass,
        random_seed=args.seed,
    )

    print(f"\n{'='*60}")
    print(f"EVALUATION RUN: {config.name}")
    print(f"{'='*60}")
    print(f"Questions: {len(questions)}")
    print(f"Cutoffs: {cutoffs}")
    print(f"Config: base_rates={config.use_base_rates}, evidence={config.use_evidence_scoring}, "
          f"calibration={config.use_calibration}, tier={config.model_tier}")
    print(f"{'='*60}\n")

    runner = ReplayRunner()
    start = time.time()
    result = runner.run_evaluation(questions, evidence_by_q, cutoffs, config)
    elapsed = time.time() - start

    # Print results
    print(f"\n{'='*60}")
    print(f"RESULTS")
    print(f"{'='*60}")
    print(f"Mean Brier Score:    {result.mean_brier_score:.4f}")
    print(f"Mean Log Score:      {result.mean_log_score:.4f}")
    print(f"Calibration Error:   {result.calibration_error:.4f}")
    print(f"Sharpness:           {result.sharpness:.4f}")
    print(f"Total Questions:     {result.total_questions}")
    print(f"Total Predictions:   {len(result.predictions)}")
    print(f"Total Cost:          ${result.total_cost_usd:.4f}")
    print(f"Elapsed Time:        {elapsed:.1f}s")

    # Domain breakdown
    if result.by_domain:
        print(f"\n{'='*60}")
        print(f"DOMAIN BREAKDOWN")
        print(f"{'='*60}")
        print(f"{'Domain':<20} {'Brier':>8} {'LogScore':>10} {'N':>5} {'Cost':>8}")
        print(f"{'-'*55}")
        for domain, metrics in sorted(result.by_domain.items()):
            print(f"{domain:<20} {metrics['brier']:>8.4f} {metrics['log_score']:>10.4f} "
                  f"{metrics['n']:>5} ${metrics['cost']:>7.4f}")

    # Horizon breakdown
    if result.by_horizon:
        print(f"\n{'='*60}")
        print(f"HORIZON BREAKDOWN")
        print(f"{'='*60}")
        print(f"{'Horizon':<10} {'Brier':>8} {'LogScore':>10} {'Sharpness':>10} {'N':>5}")
        print(f"{'-'*45}")
        for horizon, metrics in sorted(result.by_horizon.items(), key=lambda x: -int(x[0].rstrip('d'))):
            print(f"{horizon:<10} {metrics['brier']:>8.4f} {metrics['log_score']:>10.4f} "
                  f"{metrics['sharpness']:>10.4f} {metrics['n']:>5}")

    # Baseline comparison
    metrics_engine = EvalMetricsEngine()
    probs = np.array([p.predicted_probability for p in result.predictions])
    actuals = np.array([p.actual_value for p in result.predictions])
    baseline = metrics_engine.compute_baseline_comparison(probs, actuals)

    print(f"\n{'='*60}")
    print(f"BASELINE COMPARISON")
    print(f"{'='*60}")
    print(f"Model Brier:         {baseline.model_brier:.4f}")
    print(f"Always 0.5 Brier:    {baseline.always_half_brier:.4f}")
    print(f"Base Rate Brier:     {baseline.base_rate_brier:.4f}")
    print(f"vs Always 0.5:       {baseline.model_vs_half_delta:+.4f} ({'better' if baseline.model_vs_half_delta < 0 else 'worse'})")
    print(f"vs Base Rate:        {baseline.model_vs_base_rate_delta:+.4f} ({'better' if baseline.model_vs_base_rate_delta < 0 else 'worse'})")
    print(f"Skill Score:         {baseline.skill_score:.4f}")
    print(f"{'='*60}\n")

    # Save results to file
    if args.output:
        output = {
            "run_id": result.run_id,
            "config": {
                "name": config.name,
                "use_base_rates": config.use_base_rates,
                "use_evidence_scoring": config.use_evidence_scoring,
                "use_calibration": config.use_calibration,
                "model_tier": config.model_tier,
            },
            "metrics": {
                "brier_score": result.mean_brier_score,
                "log_score": result.mean_log_score,
                "calibration_error": result.calibration_error,
                "sharpness": result.sharpness,
            },
            "by_domain": result.by_domain,
            "by_horizon": result.by_horizon,
            "baseline": {
                "model_brier": baseline.model_brier,
                "always_half_brier": baseline.always_half_brier,
                "base_rate_brier": baseline.base_rate_brier,
                "skill_score": baseline.skill_score,
            },
            "total_questions": result.total_questions,
            "total_cost": result.total_cost_usd,
            "elapsed_seconds": round(elapsed, 2),
        }
        with open(args.output, "w") as f:
            json.dump(output, f, indent=2)
        print(f"Results saved to {args.output}")

    return {"result": result, "baseline": baseline}


def run_ablation(args: argparse.Namespace) -> None:
    """Run multiple ablation configurations."""
    from app.services.replay_engine import ReplayRunner, ReplayConfig
    from app.services.eval_metrics import EvalMetricsEngine

    data_dir = Path(args.data_dir)
    questions, evidence_by_q, _ = load_seed_data(data_dir)
    cutoffs = [int(x) for x in args.cutoffs.split(",")]

    # Define ablation configs
    configs = {
        "default": ReplayConfig(name="default"),
        "no_base_rates": ReplayConfig(name="no_base_rates", use_base_rates=False),
        "no_calibration": ReplayConfig(name="no_calibration", use_calibration=False),
        "no_evidence": ReplayConfig(name="no_evidence", use_evidence_scoring=False),
        "no_recency": ReplayConfig(name="no_recency", use_recency_weighting=False),
        "uniform_weights": ReplayConfig(name="uniform_weights", evidence_weighting="uniform"),
        "static_prior": ReplayConfig(name="static_prior", update_strategy="static"),
        "no_novelty": ReplayConfig(name="no_novelty", use_novelty_filter=False),
        "tier_b": ReplayConfig(name="tier_b", model_tier="B"),
        "second_pass": ReplayConfig(name="second_pass", use_disagreement_second_pass=True, model_tier="A"),
    }

    # Filter to requested configs
    if args.configs and args.configs != "all":
        requested = args.configs.split(",")
        configs = {k: v for k, v in configs.items() if k in requested}

    print(f"\n{'='*70}")
    print(f"ABLATION EXPERIMENT")
    print(f"{'='*70}")
    print(f"Questions: {len(questions)}, Cutoffs: {cutoffs}, Configs: {len(configs)}")
    print(f"{'='*70}\n")

    results = {}
    runner = ReplayRunner()

    for config_name, config in configs.items():
        print(f"Running {config_name}...", end=" ", flush=True)
        start = time.time()
        result = runner.run_evaluation(questions, evidence_by_q, cutoffs, config)
        elapsed = time.time() - start
        results[config_name] = {
            "result": result,
            "elapsed": elapsed,
        }
        print(f"Brier={result.mean_brier_score:.4f}, "
              f"LogScore={result.mean_log_score:.4f}, "
              f"Cost=${result.total_cost_usd:.4f}, "
              f"Time={elapsed:.1f}s")

    # Comparison table
    print(f"\n{'='*90}")
    print(f"ABLATION COMPARISON")
    print(f"{'='*90}")
    print(f"{'Config':<25} {'Brier':>8} {'Delta':>8} {'LogScore':>10} {'CalErr':>8} "
          f"{'Sharp':>8} {'Cost':>8} {'Time':>6}")
    print(f"{'-'*90}")

    # Find best
    best_brier = min(r["result"].mean_brier_score for r in results.values())

    for name, data in sorted(results.items(), key=lambda x: x[1]["result"].mean_brier_score):
        r = data["result"]
        delta = r.mean_brier_score - best_brier
        marker = " *" if delta == 0 else ""
        print(f"{name:<25} {r.mean_brier_score:>8.4f} {delta:>+8.4f} {r.mean_log_score:>10.4f} "
              f"{r.calibration_error:>8.4f} {r.sharpness:>8.4f} ${r.total_cost_usd:>7.4f} "
              f"{data['elapsed']:>5.1f}s{marker}")

    print(f"\n* = best configuration")
    print(f"{'='*90}\n")


def main():
    parser = argparse.ArgumentParser(description="Forecast Evaluation CLI")
    parser.add_argument("--data-dir", default="data/seeds", help="Data directory")

    subparsers = parser.add_subparsers(dest="command", help="Command")

    # Run command
    run_parser = subparsers.add_parser("run", help="Run single evaluation")
    run_parser.add_argument("--set", default="all", help="Evaluation set name")
    run_parser.add_argument("--name", help="Run name")
    run_parser.add_argument("--cutoffs", default="90,30,7", help="Cutoff days (comma-separated)")
    run_parser.add_argument("--no-base-rates", action="store_true")
    run_parser.add_argument("--no-evidence-scoring", action="store_true")
    run_parser.add_argument("--no-recency", action="store_true")
    run_parser.add_argument("--no-novelty", action="store_true")
    run_parser.add_argument("--no-calibration", action="store_true")
    run_parser.add_argument("--evidence-weighting", default="credibility", choices=["credibility", "uniform"])
    run_parser.add_argument("--model-tier", default="A", choices=["A", "B", "A+B"])
    run_parser.add_argument("--second-pass", action="store_true")
    run_parser.add_argument("--seed", type=int, default=42)
    run_parser.add_argument("--output", help="Output JSON file path")

    # Ablation command
    abl_parser = subparsers.add_parser("ablation", help="Run ablation experiments")
    abl_parser.add_argument("--set", default="all", help="Evaluation set name")
    abl_parser.add_argument("--configs", default="all", help="Configs to run (comma-separated or 'all')")
    abl_parser.add_argument("--cutoffs", default="90,30,7")
    abl_parser.add_argument("--output", help="Output JSON file path")

    args = parser.parse_args()

    if args.command == "run":
        run_evaluation(args)
    elif args.command == "ablation":
        run_ablation(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
