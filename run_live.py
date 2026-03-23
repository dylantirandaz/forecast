#!/usr/bin/env python3
"""
Live forecasting runner — pulls OPEN questions from Metaculus, forecasts them.

Setup:
    pip install numpy anthropic httpx

Usage:
    python run_live.py
    python run_live.py --limit 10
    python run_live.py --search "AI" --limit 10
    python run_live.py --mode direct --limit 5
    python run_live.py --output forecasts.json
    python run_live.py -v --limit 5
    python run_live.py --limit 20 --compare-community
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime

import numpy as np

from forecast.data import classify_domain, fetch_metaculus_questions, load_questions_from_file
from forecast.display import print_header
from forecast.llm import call_llm, estimate_cost, parse_llm_json
from forecast.prompts import (
    LIVE_FORECAST_PROMPT,
    LIVE_STRUCTURED_SCORE_PROMPT,
    LIVE_STRUCTURED_SYNTH_PROMPT,
    SYSTEM_PROMPT,
)


@dataclass
class LiveForecast:
    metaculus_id: int
    question: str
    domain: str
    probability: float
    confidence: str
    rationale: str
    community_prediction: float | None
    delta_vs_community: float | None
    base_rate: float
    cost: float
    latency_ms: int
    mode: str
    model: str
    url: str
    close_date: str
    days_left: int


def _compute_days_left(close: str) -> int:
    try:
        close_dt = datetime.fromisoformat(close.replace("Z", "+00:00"))
        return max(0, (close_dt - datetime.now(UTC)).days)
    except Exception:
        return 0


def forecast_direct(q: dict, provider: str, model: str) -> LiveForecast:
    today = datetime.now(UTC)
    close = q.get("close_date", "")
    days_left = _compute_days_left(close)
    community = q.get("community_prediction")

    community_info = ""
    if community is not None:
        community_info = f"NOTE: The Metaculus community prediction is currently {community:.0%}. You may use this as a signal but form your own independent judgment."

    prompt = LIVE_FORECAST_PROMPT.format(
        question=q["question_text"],
        domain=q["domain"],
        close_date=close[:10] if close else "unknown",
        description=(q.get("description", "") or "No description provided.")[:1500],
        today=today.strftime("%Y-%m-%d"),
        days_left=days_left,
        community_info=community_info,
    )

    start = time.monotonic()
    try:
        resp, ti, to = call_llm(prompt, SYSTEM_PROMPT, provider, model)
        cost = estimate_cost(model, ti, to)
        result = parse_llm_json(resp)
        prob = max(0.05, min(0.95, float(result.get("probability", 0.5))))
        rationale = result.get("rationale", "")
        confidence = result.get("confidence", "medium")
        base_rate = result.get("base_rate_estimate", 0.5)
    except Exception as e:
        prob, rationale, confidence, base_rate, cost = 0.5, f"Error: {e}", "low", 0.5, 0.0

    elapsed = int((time.monotonic() - start) * 1000)
    delta = round(prob - community, 4) if community else None
    return LiveForecast(
        metaculus_id=q["metaculus_id"],
        question=q["question_text"],
        domain=q["domain"],
        probability=round(prob, 4),
        confidence=confidence,
        rationale=rationale,
        community_prediction=community,
        delta_vs_community=delta,
        base_rate=base_rate,
        cost=round(cost, 6),
        latency_ms=elapsed,
        mode="direct",
        model=model,
        url=q["url"],
        close_date=close[:10] if close else "",
        days_left=days_left,
    )


def forecast_structured(q: dict, provider: str, model: str, cheap_model: str) -> LiveForecast:
    datetime.now(UTC)
    close = q.get("close_date", "")
    days_left = _compute_days_left(close)
    community = q.get("community_prediction")
    total_cost = 0.0
    start = time.monotonic()

    score_prompt = LIVE_STRUCTURED_SCORE_PROMPT.format(
        question=q["question_text"],
        domain=q["domain"],
        close_date=close[:10] if close else "unknown",
        description=(q.get("description", "") or "")[:1500],
    )
    try:
        resp, ti, to = call_llm(score_prompt, SYSTEM_PROMPT, provider, cheap_model)
        total_cost += estimate_cost(cheap_model, ti, to)
        analysis = parse_llm_json(resp)
        base_rate = float(analysis.get("base_rate", 0.5))
        factors_list = analysis.get("key_factors", [])
        factors = (
            "; ".join(
                f"{f.get('factor', '?')} ({f.get('direction', '?')}, str={f.get('strength', 0.5):.1f})"
                for f in factors_list[:5]
            )
            if factors_list
            else "No factors identified"
        )
        direction = analysis.get("overall_direction", "neutral")
        uncertainty = analysis.get("uncertainty", "medium")
    except Exception as e:
        base_rate, factors, direction, uncertainty = 0.5, f"Analysis failed: {e}", "neutral", "high"

    community_info = ""
    if community is not None:
        community_info = f"Community prediction: {community:.0%}. Use as a signal but form independent judgment."

    synth_prompt = LIVE_STRUCTURED_SYNTH_PROMPT.format(
        question=q["question_text"],
        domain=q["domain"],
        close_date=close[:10] if close else "unknown",
        days_left=days_left,
        base_rate=base_rate,
        factors=factors,
        direction=direction,
        uncertainty=uncertainty,
        community_info=community_info,
    )
    try:
        resp, ti, to = call_llm(synth_prompt, SYSTEM_PROMPT, provider, model)
        total_cost += estimate_cost(model, ti, to)
        result = parse_llm_json(resp)
        prob = max(0.05, min(0.95, float(result.get("probability", 0.5))))
        rationale = result.get("rationale", "")
        confidence = result.get("confidence", "medium")
    except Exception as e:
        prob, rationale, confidence = base_rate, f"Synthesis failed: {e}", "low"

    elapsed = int((time.monotonic() - start) * 1000)
    delta = round(prob - community, 4) if community else None
    return LiveForecast(
        metaculus_id=q["metaculus_id"],
        question=q["question_text"],
        domain=q["domain"],
        probability=round(prob, 4),
        confidence=confidence,
        rationale=rationale,
        community_prediction=community,
        delta_vs_community=delta,
        base_rate=base_rate,
        cost=round(total_cost, 6),
        latency_ms=elapsed,
        mode="structured",
        model=model,
        url=q["url"],
        close_date=close[:10] if close else "",
        days_left=days_left,
    )


def main():
    parser = argparse.ArgumentParser(description="Live forecasting on open Metaculus questions")
    parser.add_argument("--provider", default="anthropic", choices=["anthropic", "openai"])
    parser.add_argument("--model", default="claude-sonnet-4-6")
    parser.add_argument("--cheap-model", default="claude-haiku-4-5-20251001")
    parser.add_argument("--mode", default="structured", choices=["structured", "direct"])
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--search", default="", help="Search filter for questions")
    parser.add_argument("--compare-community", action="store_true", help="Show comparison with community")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--output", "-o", help="Save forecasts to JSON")
    parser.add_argument("--from-file", help="Load questions from JSON file instead of Metaculus API")
    args = parser.parse_args()

    if args.provider == "anthropic" and not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: Set ANTHROPIC_API_KEY")
        print('  $env:ANTHROPIC_API_KEY="sk-ant-..."')
        sys.exit(1)

    if not os.environ.get("METACULUS_API_KEY"):
        print("WARNING: METACULUS_API_KEY not set. Metaculus API requires authentication.")
        print("  Get your token at https://www.metaculus.com/accounts/profile/ -> API Token")
        print('  Then: $env:METACULUS_API_KEY="your-token"')
        print()

    if args.from_file:
        print(f"Loading questions from {args.from_file}...", flush=True)
        questions = load_questions_from_file(args.from_file)
        for q in questions:
            if "metaculus_id" not in q:
                q["metaculus_id"] = q.get("id", 0)
            if "question_text" not in q:
                q["question_text"] = q.get("title", q.get("question", ""))
            if "domain" not in q:
                q["domain"] = classify_domain(q.get("question_text", "").lower())
            if "url" not in q:
                q["url"] = ""
        questions = questions[: args.limit]
    else:
        print("Fetching open questions from Metaculus...", flush=True)
        questions = fetch_metaculus_questions(limit=args.limit, search=args.search)
    print(f"Got {len(questions)} questions\n")

    if not questions:
        print("No open questions found. Try different search terms or increase limit.")
        sys.exit(0)

    print(f"Mode: {args.mode} | Model: {args.model} | Questions: {len(questions)}")
    print(f"{'=' * 80}\n")

    forecasts: list[LiveForecast] = []
    for i, q in enumerate(questions):
        print(f"[{i + 1}/{len(questions)}] {q['question_text'][:70]}...", flush=True)
        if args.mode == "structured":
            fc = forecast_structured(q, args.provider, args.model, args.cheap_model)
        else:
            fc = forecast_direct(q, args.provider, args.model)
        forecasts.append(fc)

        comm_str = f" (community: {fc.community_prediction:.0%})" if fc.community_prediction else ""
        delta_str = f" [delta: {fc.delta_vs_community:+.0%}]" if fc.delta_vs_community is not None else ""
        print(f"  -> {fc.probability:.0%} ({fc.confidence}){comm_str}{delta_str}  ${fc.cost:.4f}  {fc.latency_ms}ms")
        if args.verbose and fc.rationale:
            print(f"     {fc.rationale[:150]}")
        print()

    print_header("LIVE FORECAST SUMMARY", width=80)
    print(f"  Questions forecasted:   {len(forecasts)}")
    print(f"  Total cost:             ${sum(f.cost for f in forecasts):.4f}")
    print(f"  Avg latency:            {np.mean([f.latency_ms for f in forecasts]):.0f}ms")
    print(f"  Avg probability:        {np.mean([f.probability for f in forecasts]):.2f}")
    print(f"  Sharpness:              {np.mean([abs(f.probability - 0.5) for f in forecasts]):.3f}")

    confs: dict[str, list[LiveForecast]] = {}
    for f in forecasts:
        confs.setdefault(f.confidence, []).append(f)
    if confs:
        print(f"\n  {'Confidence':<12} {'Avg Prob':>10} {'Sharpness':>10} {'N':>5}")
        print(f"  {'-' * 40}")
        for c in ["low", "medium", "high"]:
            if c in confs:
                probs = [f.probability for f in confs[c]]
                print(
                    f"  {c:<12} {np.mean(probs):>10.2f} {np.mean([abs(p - 0.5) for p in probs]):>10.3f} {len(probs):>5}"
                )

    with_community = [f for f in forecasts if f.community_prediction is not None]
    if with_community and args.compare_community:
        print(f"\n  {'=' * 60}")
        print("  MODEL vs COMMUNITY")
        print(f"  {'=' * 60}")
        print(f"  {'Question':<45} {'Model':>7} {'Comm':>7} {'Delta':>7}")
        print(f"  {'-' * 68}")
        for f in sorted(with_community, key=lambda x: abs(x.delta_vs_community or 0), reverse=True):
            text = f.question[:42] + "..." if len(f.question) > 45 else f.question
            print(f"  {text:<45} {f.probability:>6.0%} {f.community_prediction:>6.0%} {f.delta_vs_community:>+6.0%}")
        deltas = [abs(f.delta_vs_community) for f in with_community if f.delta_vs_community is not None]
        print(f"\n  Mean absolute disagreement: {np.mean(deltas):.1%}")
        print(f"  Max disagreement:           {max(deltas):.1%}")

    domains: dict[str, list[LiveForecast]] = {}
    for f in forecasts:
        domains.setdefault(f.domain, []).append(f)
    if len(domains) > 1:
        print(f"\n  {'Domain':<15} {'Avg Prob':>10} {'N':>5} {'Cost':>8}")
        print(f"  {'-' * 40}")
        for d in sorted(domains):
            probs = [f.probability for f in domains[d]]
            cost = sum(f.cost for f in domains[d])
            print(f"  {d:<15} {np.mean(probs):>10.2f} {len(probs):>5} ${cost:>7.4f}")

    print(f"{'=' * 80}")

    if args.output:
        output = {
            "timestamp": datetime.now(UTC).isoformat(),
            "config": {"mode": args.mode, "model": args.model, "provider": args.provider},
            "forecasts": [
                {
                    "metaculus_id": f.metaculus_id,
                    "question": f.question,
                    "domain": f.domain,
                    "probability": f.probability,
                    "confidence": f.confidence,
                    "rationale": f.rationale,
                    "community_prediction": f.community_prediction,
                    "delta_vs_community": f.delta_vs_community,
                    "base_rate": f.base_rate,
                    "cost": f.cost,
                    "mode": f.mode,
                    "model": f.model,
                    "url": f.url,
                    "close_date": f.close_date,
                    "days_left": f.days_left,
                }
                for f in forecasts
            ],
        }
        with open(args.output, "w") as f:
            json.dump(output, f, indent=2, default=str)
        print(f"\nForecasts saved to {args.output}")
        print("Re-run after questions resolve to score accuracy!")


if __name__ == "__main__":
    main()
