#!/usr/bin/env python3
"""
LLM-powered evaluation runner.

Uses an actual LLM (Claude or GPT) to forecast questions instead of keyword heuristics.

Setup:
    pip install numpy anthropic     # for Claude
    pip install numpy openai        # for GPT
    pip install numpy exa-py        # for search (optional)

    export ANTHROPIC_API_KEY=sk-ant-...
    export EXA_API_KEY=...

Usage:
    python run_llm_eval.py
    python run_llm_eval.py --mode direct
    python run_llm_eval.py --compare
    python run_llm_eval.py --model claude-haiku-4-5-20251001
    python run_llm_eval.py --provider openai --model gpt-4o-mini
    python run_llm_eval.py --limit 5
    python run_llm_eval.py --domain macro --limit 10
    python run_llm_eval.py --search
    python run_llm_eval.py --output results.json
    python run_llm_eval.py -v --limit 5
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import timedelta

from forecast.config import DOMAIN_BASE_RATES, PROB_CEILING, PROB_FLOOR
from forecast.data import filter_questions, load_questions_from_file, load_seed_questions
from forecast.dates import parse_date
from forecast.display import (
    format_evidence,
    print_baselines,
    print_confidence_breakdown,
    print_domain_breakdown,
    print_header,
    print_horizon_breakdown,
)
from forecast.llm import call_llm, estimate_cost, parse_llm_json
from forecast.metrics import (
    brier_score,
    compute_metrics,
    log_score,
)
from forecast.prompts import DIRECT_FORECAST_PROMPT, EVIDENCE_SCORING_PROMPT, STRUCTURED_FORECAST_PROMPT, SYSTEM_PROMPT
from forecast.search import search_for_question, set_asknews_credentials, set_search_provider


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
    cost: float = 0.0
    latency_ms: int = 0
    mode: str = "structured"
    rationale: str = ""
    confidence: str = "medium"
    model: str = ""


def _build_scored_evidence(
    question: dict,
    available: list[dict],
    cutoff_str: str,
    domain: str,
    provider: str,
    cheap_model: str,
) -> tuple[str, str, float, int, int]:
    scores_text = "No evidence available."
    direction = "neutral"
    total_cost, total_in, total_out = 0.0, 0, 0
    if not available:
        return scores_text, direction, total_cost, total_in, total_out

    ev_text = format_evidence(available)
    prompt = EVIDENCE_SCORING_PROMPT.format(
        question=question["question_text"],
        domain=domain,
        cutoff=cutoff_str,
        evidence=ev_text,
    )
    try:
        resp, ti, to = call_llm(prompt, SYSTEM_PROMPT, provider, cheap_model)
        total_in, total_out = ti, to
        total_cost = estimate_cost(cheap_model, ti, to)
        data = parse_llm_json(resp)
        scores = data.get("scores", [])
        direction = data.get("overall_direction", "neutral")
        scores_text = "\n".join(
            f"  [{s.get('idx', i)}] cred={s.get('credibility', 0.5):.1f} rel={s.get('relevance', 0.5):.1f} "
            f"dir={s.get('direction', '?')} str={s.get('strength', 0.3):.1f} — {s.get('insight', '')}"
            for i, s in enumerate(scores)
        )
    except Exception as e:
        scores_text = f"Evidence scoring failed: {e}"
    return scores_text, direction, total_cost, total_in, total_out


def _gather_evidence(
    question: dict,
    evidence: list[dict],
    cutoff_date,
    cutoff_str: str,
    domain: str,
    use_search: bool,
    search_per_q: int,
    provider: str,
    cheap_model: str,
) -> list[dict]:
    available = [e for e in evidence if parse_date(e["published_at"]) <= cutoff_date]
    if use_search:
        # AskNews historical mode already time-gates articles to before
        # the cutoff date. The judge model provides a second layer of
        # filtering for non-news sources. We still date-check as a
        # safety net in case any article slips through.
        for ev in search_for_question(
            question["question_text"],
            domain,
            cutoff_str,
            max_results=search_per_q,
            provider=provider,
            cheap_model=cheap_model,
        ):
            ev_dict = {
                "source": ev.source,
                "source_type": ev.source_type,
                "source_quality_score": ev.source_quality_score,
                "title": ev.title,
                "content": ev.content,
                "url": ev.url,
                "published_at": ev.published_at,
            }
            if ev.published_at:
                try:
                    if parse_date(ev.published_at) <= cutoff_date:
                        available.append(ev_dict)
                except Exception:
                    available.append(ev_dict)
            else:
                available.append(ev_dict)
    available.sort(key=lambda e: e.get("published_at", ""))
    return available


def _make_prediction(
    question: dict,
    prob: float,
    actual: float,
    domain: str,
    cutoff_days: int,
    evidence_count: int,
    base_rate: float,
    cost: float,
    elapsed_ms: int,
    mode: str,
    rationale: str,
    confidence: str,
    model: str,
) -> Prediction:
    return Prediction(
        question_idx=question.get("_idx", 0),
        question_text=question["question_text"],
        domain=domain,
        difficulty=question.get("difficulty", "medium"),
        cutoff_days=cutoff_days,
        predicted=round(prob, 4),
        actual=actual,
        brier=round(brier_score(prob, actual), 6),
        log_score=round(log_score(prob, actual), 6),
        evidence_count=evidence_count,
        base_rate=base_rate,
        cost=round(cost, 6),
        latency_ms=elapsed_ms,
        mode=mode,
        rationale=rationale,
        confidence=confidence,
        model=model,
    )


def forecast_structured(
    question: dict,
    evidence: list[dict],
    cutoff_days: int,
    provider: str,
    model: str,
    cheap_model: str,
    use_search: bool = False,
    search_per_q: int = 5,
) -> Prediction:
    resolve_date = parse_date(question["resolve_date"])
    cutoff_date = resolve_date - timedelta(days=cutoff_days)
    cutoff_str = cutoff_date.strftime("%Y-%m-%d")
    domain = question.get("domain", "other")
    base_rate = DOMAIN_BASE_RATES.get(domain, 0.5)
    actual = question["resolved_value"]

    available = _gather_evidence(
        question, evidence, cutoff_date, cutoff_str, domain, use_search, search_per_q, provider, cheap_model
    )
    start = time.monotonic()
    scores_text, direction, cost, _ti_total, _to_total = _build_scored_evidence(
        question,
        available,
        cutoff_str,
        domain,
        provider,
        cheap_model,
    )

    prompt = STRUCTURED_FORECAST_PROMPT.format(
        question=question["question_text"],
        domain=domain,
        cutoff=cutoff_str,
        base_rate=base_rate,
        scores=scores_text,
        direction=direction,
    )
    try:
        resp, ti, to = call_llm(prompt, SYSTEM_PROMPT, provider, model)
        cost += estimate_cost(model, ti, to)
        result = parse_llm_json(resp)
        prob = max(PROB_FLOOR, min(PROB_CEILING, float(result.get("probability", 0.5))))
        rationale = result.get("rationale", "")
        confidence = result.get("confidence", "medium")
    except Exception as e:
        prob, rationale, confidence = base_rate, f"Failed: {e}", "low"

    elapsed_ms = int((time.monotonic() - start) * 1000)
    return _make_prediction(
        question,
        prob,
        actual,
        domain,
        cutoff_days,
        len(available),
        base_rate,
        cost,
        elapsed_ms,
        "structured",
        rationale,
        confidence,
        model,
    )


def forecast_direct(
    question: dict,
    evidence: list[dict],
    cutoff_days: int,
    provider: str,
    model: str,
    use_search: bool = False,
    search_per_q: int = 5,
) -> Prediction:
    resolve_date = parse_date(question["resolve_date"])
    cutoff_date = resolve_date - timedelta(days=cutoff_days)
    cutoff_str = cutoff_date.strftime("%Y-%m-%d")
    domain = question.get("domain", "other")
    base_rate = DOMAIN_BASE_RATES.get(domain, 0.5)
    actual = question["resolved_value"]

    available = _gather_evidence(
        question, evidence, cutoff_date, cutoff_str, domain, use_search, search_per_q, provider, model
    )
    start = time.monotonic()
    ev_text = format_evidence(available)
    prompt = DIRECT_FORECAST_PROMPT.format(
        question=question["question_text"],
        domain=domain,
        cutoff=cutoff_str,
        evidence=ev_text,
    )
    try:
        resp, ti, to = call_llm(prompt, SYSTEM_PROMPT, provider, model)
        cost = estimate_cost(model, ti, to)
        result = parse_llm_json(resp)
        prob = max(PROB_FLOOR, min(PROB_CEILING, float(result.get("probability", 0.5))))
        rationale = result.get("rationale", "")
        confidence = result.get("confidence", "medium")
    except Exception as e:
        prob, cost, rationale, confidence = base_rate, 0.0, f"Failed: {e}", "low"

    elapsed_ms = int((time.monotonic() - start) * 1000)
    return _make_prediction(
        question,
        prob,
        actual,
        domain,
        cutoff_days,
        len(available),
        base_rate,
        cost,
        elapsed_ms,
        "direct",
        rationale,
        confidence,
        model,
    )


def run(args):
    if getattr(args, "from_file", None):
        questions = load_questions_from_file(args.from_file)
        evidence_by_q: dict[int, list[dict]] = {}
    else:
        questions, evidence_by_q = load_seed_questions(args.data_dir)

    questions, evidence_by_q = filter_questions(
        questions,
        evidence_by_q,
        domain=args.domain,
        difficulty=args.difficulty,
        limit=args.limit,
    )
    cutoffs = [int(x) for x in args.cutoffs.split(",")]
    total_forecasts = len(questions) * len(cutoffs)
    use_search = getattr(args, "search", False)

    print(f"\nLoaded {len(questions)} questions, {sum(len(v) for v in evidence_by_q.values())} evidence items")
    print(f"Mode: {args.mode} | Model: {args.model} | Provider: {args.provider}")
    print(f"Search: {'ON (exa.ai)' if use_search else 'OFF'}")
    print(f"Cutoffs: {cutoffs} | Total forecasts: {total_forecasts}")
    print(f"{'=' * 70}\n")

    preds: list[Prediction] = []
    for i, q in enumerate(questions):
        q["_idx"] = i
        ev = evidence_by_q.get(i, [])
        for cutoff in cutoffs:
            label = f"[{len(preds) + 1}/{total_forecasts}] Q{i} @{cutoff}d"
            if args.mode == "structured":
                pred = forecast_structured(
                    q, ev, cutoff, args.provider, args.model, args.cheap_model, use_search=use_search
                )
            else:
                pred = forecast_direct(q, ev, cutoff, args.provider, args.model, use_search=use_search)
            preds.append(pred)
            ok = "OK" if (pred.predicted > 0.5) == (pred.actual == 1) else "MISS"
            if args.verbose:
                print(
                    f"  {label}: {pred.predicted:.2f} (actual={pred.actual:.0f}) brier={pred.brier:.3f} ${pred.cost:.4f} {pred.latency_ms}ms [{ok}]"
                )
                if pred.rationale:
                    print(f"         -> {pred.rationale[:120].encode('ascii', 'replace').decode()}")
            else:
                print(
                    f"  {label}: pred={pred.predicted:.2f} actual={pred.actual:.0f} brier={pred.brier:.3f} ${pred.cost:.4f}",
                    flush=True,
                )

    m = compute_metrics(preds)
    actuals = [p.actual for p in preds]
    print_header(f"RESULTS — {args.mode.upper()} mode, {args.model}")
    print(f"  Mean Brier Score:     {m['brier']:.4f}")
    print(f"  Mean Log Score:       {m['log_score']:.4f}")
    print(f"  Calibration Error:    {m['ece']:.4f}")
    print(f"  Sharpness:            {m['sharpness']:.4f}")
    print(f"  Predictions:          {m['n']}")
    print(f"  Total Cost:           ${m['cost']:.4f}")
    print(f"  Avg Latency:          {m['avg_latency_ms']:.0f}ms")
    print(f"{'=' * 70}")
    print_baselines(m, actuals)
    print_domain_breakdown(preds, compute_metrics, show_cost=True)
    print_horizon_breakdown(preds, cutoffs, compute_metrics)
    print_confidence_breakdown(preds, compute_metrics)
    print(f"{'=' * 70}\n")

    if args.output:
        output = {
            "config": {"mode": args.mode, "model": args.model, "provider": args.provider, "search": use_search},
            "metrics": m,
            "predictions": [
                {
                    "question": p.question_text,
                    "domain": p.domain,
                    "cutoff": p.cutoff_days,
                    "predicted": p.predicted,
                    "actual": p.actual,
                    "brier": p.brier,
                    "cost": p.cost,
                    "rationale": p.rationale,
                    "confidence": p.confidence,
                }
                for p in preds
            ],
        }
        with open(args.output, "w") as f:
            json.dump(output, f, indent=2, default=str)
        print(f"Results saved to {args.output}")

    return preds, m


def main():
    parser = argparse.ArgumentParser(description="LLM-powered forecast evaluation")
    parser.add_argument("--data-dir", default="data/seeds")
    parser.add_argument("--provider", default="anthropic", choices=["anthropic", "openai"])
    parser.add_argument("--model", default="claude-sonnet-4-6", help="Main model for synthesis")
    parser.add_argument("--cheap-model", default="claude-haiku-4-5-20251001", help="Cheap model for evidence scoring")
    parser.add_argument("--mode", default="structured", choices=["structured", "direct"])
    parser.add_argument("--compare", action="store_true", help="Run both modes and compare")
    parser.add_argument("--cutoffs", default="90,30,7")
    parser.add_argument("--limit", type=int, help="Limit number of questions (for testing/budget)")
    parser.add_argument("--domain", help="Filter to domain")
    parser.add_argument("--difficulty", help="Filter by difficulty")
    parser.add_argument("--search", action="store_true", help="Use Exa.ai search for additional evidence")
    parser.add_argument("--exa-key", help="Exa.ai API key (or set EXA_API_KEY env var)")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--output", "-o", help="Save results to JSON")
    parser.add_argument("--from-file", help="Load questions from JSON file instead of seed data")
    args = parser.parse_args()

    if args.provider == "anthropic" and not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: Set ANTHROPIC_API_KEY environment variable")
        print('  $env:ANTHROPIC_API_KEY="sk-ant-..."')
        sys.exit(1)
    if args.provider == "openai" and not os.environ.get("OPENAI_API_KEY"):
        print("ERROR: Set OPENAI_API_KEY environment variable")
        sys.exit(1)

    if os.environ.get("ASKNEWS_API_KEY"):
        set_asknews_credentials(api_key=os.environ["ASKNEWS_API_KEY"])
    elif os.environ.get("ASKNEWS_CLIENT_ID") and os.environ.get("ASKNEWS_CLIENT_SECRET"):
        set_asknews_credentials(os.environ["ASKNEWS_CLIENT_ID"], os.environ["ASKNEWS_CLIENT_SECRET"])

    if os.environ.get("SEARCH_PROVIDER"):
        set_search_provider(os.environ["SEARCH_PROVIDER"])

    has_search_provider = os.environ.get("ASKNEWS_API_KEY") or (os.environ.get("ASKNEWS_CLIENT_ID") and os.environ.get("ASKNEWS_CLIENT_SECRET"))
    if args.search and not has_search_provider:
        print("WARNING: --search requires ASKNEWS_API_KEY or ASKNEWS_CLIENT_ID/SECRET")

    if args.compare:
        print_header("STRUCTURED vs DIRECT comparison")
        print(f"  Model: {args.model} | Provider: {args.provider}")
        print(f"{'=' * 70}\n")
        args.mode = "structured"
        print("--- Running STRUCTURED mode ---")
        _, m_s = run(args)
        args.mode = "direct"
        print("\n--- Running DIRECT mode ---")
        _, m_d = run(args)
        print_header("HEAD-TO-HEAD COMPARISON")
        print(f"  {'Metric':<20} {'Structured':>12} {'Direct':>12} {'Delta':>12}")
        print(f"  {'-' * 58}")
        for key in ["brier", "log_score", "ece", "sharpness", "cost"]:
            delta = m_s[key] - m_d[key]
            better = (
                "structured" if (delta < 0 and key != "sharpness") or (delta > 0 and key == "sharpness") else "direct"
            )
            print(f"  {key:<20} {m_s[key]:>12.4f} {m_d[key]:>12.4f} {delta:>+12.4f}  ({better})")
        print(f"{'=' * 70}\n")
    else:
        run(args)


if __name__ == "__main__":
    main()
