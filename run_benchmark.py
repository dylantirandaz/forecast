#!/usr/bin/env python3
"""
ForecastBench benchmark runner with FRED data integration.

Setup:
    pip install numpy anthropic httpx exa-py

Usage:
    python run_benchmark.py --resolved --limit 50
    python run_benchmark.py --resolved --source fred --fred-key YOUR_KEY
    python run_benchmark.py --resolved --limit 30 --search --exa-key YOUR_KEY
    python run_benchmark.py --open --limit 50 -o submission.json
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime

import numpy as np

from forecast.data import (
    download_forecastbench_questions,
    download_forecastbench_resolutions,
    fetch_fred_series,
    match_resolutions,
)
from forecast.display import print_header
from forecast.llm import call_llm, estimate_cost, parse_llm_json
from forecast.prompts import FORECASTBENCH_PROMPT, FRED_FORECAST_PROMPT, SYSTEM_PROMPT
from forecast.search import search as exa_search
from forecast.search import set_exa_key

_fred_api_key = ""


@dataclass
class BenchmarkPrediction:
    question_id: str
    question: str
    source: str
    predicted: float
    actual: float | None
    brier: float | None
    confidence: str
    rationale: str
    cost: float
    latency_ms: int
    method: str = "llm"


def _fred_data_to_probability(fred_info: dict, question_text: str) -> float:
    change = fred_info["current_change"]
    freeze = fred_info["freeze_value"]
    trend = fred_info["trend_direction"]
    cv = fred_info["cv"]

    q_lower = question_text.lower()
    if "decreased" in q_lower or "decline" in q_lower or "fallen" in q_lower:
        change = -change
        trend = "up" if trend == "down" else "down"

    if change > 0:
        if abs(change) > abs(freeze) * 0.1:
            base = 0.80
        elif abs(change) > abs(freeze) * 0.03:
            base = 0.70
        else:
            base = 0.58
        base = min(0.95, base + 0.05) if trend == "up" else max(0.40, base - 0.10)
    else:
        if abs(change) > abs(freeze) * 0.1:
            base = 0.20
        elif abs(change) > abs(freeze) * 0.03:
            base = 0.35
        else:
            base = 0.45
        base = min(0.60, base + 0.10) if trend == "up" else max(0.10, base - 0.05)

    if cv > 0.1:
        base = base * 0.8 + 0.5 * 0.2

    return round(max(0.05, min(0.95, base)), 4)


def _analyze_fred_question(q: dict) -> dict | None:
    freeze_val = q.get("freeze_datetime_value")
    if freeze_val is None:
        return None
    try:
        freeze_val = float(freeze_val)
    except (ValueError, TypeError):
        return None

    obs = fetch_fred_series(q["id"], api_key=_fred_api_key, limit=10)
    if not obs:
        return None

    try:
        latest_val = float(obs[0]["value"])
        latest_date = obs[0]["date"]
    except (ValueError, IndexError):
        return None

    values = []
    for o in obs[:10]:
        try:
            values.append(float(o["value"]))
        except ValueError:
            continue

    if len(values) < 2:
        return None

    current_change = latest_val - freeze_val
    pct_change = current_change / abs(freeze_val) if freeze_val != 0 else 0
    recent_trend = values[0] - values[-1]
    trend_direction = "up" if recent_trend > 0 else "down"

    if len(values) >= 3:
        volatility = float(np.std(values))
        mean_val = float(np.mean(values))
        cv = volatility / abs(mean_val) if mean_val != 0 else 0
    else:
        cv = 0.0

    return {
        "series_id": q["id"],
        "freeze_value": freeze_val,
        "latest_value": latest_val,
        "latest_date": latest_date,
        "current_change": round(current_change, 6),
        "pct_change": round(pct_change, 6),
        "trend_direction": trend_direction,
        "recent_values": values[:5],
        "volatility": round(float(np.std(values)) if len(values) >= 3 else 0, 6),
        "cv": round(cv, 6),
    }


def forecast_question(
    q: dict, provider: str, model: str, cheap_model: str, use_search: bool, use_fred: bool
) -> BenchmarkPrediction:
    question_text = q.get("question", "")
    source = q.get("source", "unknown")
    actual = q.get("resolved_value")
    start = time.monotonic()

    if source == "fred" and use_fred:
        fred_info = _analyze_fred_question(q)
        if fred_info:
            data_prob = _fred_data_to_probability(fred_info, question_text)
            direction = "up" if fred_info["current_change"] > 0 else "down"
            prompt = FRED_FORECAST_PROMPT.format(
                question=question_text,
                freeze_val=fred_info["freeze_value"],
                latest_val=fred_info["latest_value"],
                latest_date=fred_info["latest_date"],
                change=f"{fred_info['current_change']:+.4f}",
                pct_change=f"{fred_info['pct_change']:+.2%}",
                trend=fred_info["trend_direction"],
                recent_vals=fred_info["recent_values"],
                cv=f"{fred_info['cv']:.4f}",
                criteria=q.get("resolution_criteria", "")[:300],
                res_dates=", ".join(q.get("resolution_dates", [])[:3]),
                direction=direction,
            )
            try:
                resp, ti, to = call_llm(prompt, SYSTEM_PROMPT, provider, cheap_model)
                cost = estimate_cost(cheap_model, ti, to)
                result = parse_llm_json(resp)
                llm_prob = max(0.05, min(0.95, float(result.get("probability", 0.5))))
                rationale = result.get("rationale", "")
                confidence = result.get("confidence", "medium")
            except Exception as e:
                llm_prob, rationale, confidence, cost = data_prob, f"LLM failed, using data: {e}", "medium", 0.0

            prob = 0.6 * data_prob + 0.4 * llm_prob
            elapsed = int((time.monotonic() - start) * 1000)
            b = (prob - actual) ** 2 if actual is not None else None
            return BenchmarkPrediction(
                question_id=q["id"],
                question=question_text[:100],
                source=source,
                predicted=round(prob, 4),
                actual=actual,
                brier=round(b, 6) if b is not None else None,
                confidence=confidence,
                rationale=f"[FRED data: {fred_info['freeze_value']}->{fred_info['latest_value']} ({direction})] {rationale}",
                cost=round(cost, 6),
                latency_ms=elapsed,
                method="fred_data+llm",
            )

    background = q.get("background", "")[:1500]
    criteria = q.get("resolution_criteria", q.get("market_info_resolution_criteria", ""))[:500]
    freeze_val = q.get("freeze_datetime_value", "N/A")
    freeze_expl = q.get("freeze_datetime_value_explanation", "")
    res_dates = ", ".join(q.get("resolution_dates", [])[:3]) if q.get("resolution_dates") else "unknown"

    evidence_section = ""
    if use_search:
        freeze_dt = q.get("freeze_datetime", "")
        end_date = freeze_dt[:10] if freeze_dt else None
        results = exa_search(question_text[:200], max_results=3, before_date=end_date)
        if results:
            evidence_section = "SEARCH EVIDENCE:\n" + "\n".join(
                f"  [{r.source}] {r.title[:80]}: {r.content[:200]}" for r in results[:5]
            )

    freeze_info = (
        f"{freeze_val} ({freeze_expl[:200]})"
        if freeze_val and freeze_val != "N/A" and freeze_expl
        else str(freeze_val)
        if freeze_val
        else "N/A"
    )
    prompt = FORECASTBENCH_PROMPT.format(
        question=question_text,
        background=background,
        criteria=criteria,
        res_dates=res_dates,
        source=source,
        freeze_val=freeze_info,
        data_section="",
        evidence_section=evidence_section or "No additional evidence.",
    )
    try:
        resp, ti, to = call_llm(prompt, SYSTEM_PROMPT, provider, model)
        cost = estimate_cost(model, ti, to)
        result = parse_llm_json(resp)
        prob = max(0.05, min(0.95, float(result.get("probability", 0.5))))
        confidence = result.get("confidence", "medium")
        rationale = result.get("rationale", "")
    except Exception as e:
        prob, confidence, rationale, cost = 0.5, "low", f"Error: {e}", 0.0

    elapsed = int((time.monotonic() - start) * 1000)
    b = (prob - actual) ** 2 if actual is not None else None
    return BenchmarkPrediction(
        question_id=q["id"],
        question=question_text[:100],
        source=source,
        predicted=round(prob, 4),
        actual=actual,
        brier=round(b, 6) if b is not None else None,
        confidence=confidence,
        rationale=rationale,
        cost=round(cost, 6),
        latency_ms=elapsed,
        method="llm",
    )


def main():
    parser = argparse.ArgumentParser(description="ForecastBench benchmark runner")
    parser.add_argument("--provider", default="anthropic", choices=["anthropic", "openai"])
    parser.add_argument("--model", default="claude-sonnet-4-6")
    parser.add_argument("--cheap-model", default="claude-haiku-4-5-20251001")
    parser.add_argument("--resolved", action="store_true", help="Score against resolutions")
    parser.add_argument("--open", action="store_true", help="Forecast open questions")
    parser.add_argument("--question-set", default="latest")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--search", action="store_true")
    parser.add_argument("--exa-key", default="")
    parser.add_argument("--fred-key", default="", help="FRED API key")
    parser.add_argument("--source", default="", help="Filter by source")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--output", "-o", help="Save results")
    parser.add_argument("--local-questions", help="Local question set JSON")
    parser.add_argument("--local-resolutions", help="Local resolution set JSON")
    parser.add_argument("--list-sets", action="store_true")
    args = parser.parse_args()

    if args.list_sets:
        from forecast.data import _list_forecastbench_sets

        sets = _list_forecastbench_sets()
        for k, v in sets.items():
            print(f"\n{k}:")
            for s in v:
                print(f"  {s}")
        return

    if args.provider == "anthropic" and not os.environ.get("ANTHROPIC_API_KEY"):
        print('ERROR: $env:ANTHROPIC_API_KEY="sk-ant-..."')
        sys.exit(1)

    global _fred_api_key
    if args.exa_key:
        set_exa_key(args.exa_key)
    if args.fred_key:
        _fred_api_key = args.fred_key
    elif os.environ.get("FRED_API_KEY"):
        _fred_api_key = os.environ["FRED_API_KEY"]
    use_fred = bool(_fred_api_key)

    if args.local_questions:
        with open(args.local_questions) as f:
            q_data = json.load(f)
    else:
        q_data = download_forecastbench_questions(args.question_set)

    questions = q_data["questions"]
    print(f"Question set: {q_data.get('question_set', '?')} | Due: {q_data.get('forecast_due_date', '?')}")
    print(f"Total questions: {len(questions)}")

    if args.source:
        questions = [q for q in questions if q.get("source") == args.source]
        print(f"Filtered to {len(questions)} {args.source} questions")

    if args.resolved:
        if args.local_resolutions:
            with open(args.local_resolutions) as f:
                r_data = json.load(f)
        else:
            r_data = download_forecastbench_resolutions(args.question_set)
        resolutions = r_data.get("resolutions", [])
        print(f"Resolutions: {len(resolutions)}")
        questions = match_resolutions(questions, resolutions)
        print(f"Matched resolved: {len(questions)}")
        if not questions:
            print("No resolved questions. Try --open instead.")
            return

    questions = questions[: args.limit]
    sources = Counter(q.get("source") for q in questions)
    print(f"By source: {dict(sources)}")
    print(
        f"\nModel: {args.model} | Search: {'ON' if args.search else 'OFF'} | FRED data: {'ON' if use_fred else 'OFF'}"
    )
    print(f"Questions: {len(questions)}")
    print(f"{'=' * 75}\n")

    preds: list[BenchmarkPrediction] = []
    for i, q in enumerate(questions):
        src = q.get("source", "?")
        print(f"[{i + 1}/{len(questions)}] [{src:>10}] {q['question'][:58]}...", end=" ", flush=True)
        pred = forecast_question(q, args.provider, args.model, args.cheap_model, args.search, use_fred)
        preds.append(pred)
        if args.resolved and pred.brier is not None:
            ok = "OK" if pred.brier < 0.25 else "MISS"
            print(f"{pred.predicted:.2f} (act={pred.actual:.0f}) brier={pred.brier:.3f} [{pred.method}] [{ok}]")
        else:
            print(f"{pred.predicted:.2f} ({pred.confidence}) [{pred.method}]")
        if args.verbose and pred.rationale:
            print(f"     {pred.rationale[:140]}")

    if args.resolved:
        scored = [p for p in preds if p.brier is not None]
        if scored:
            briers = [p.brier for p in scored]
            actuals = [p.actual for p in scored]
            probs = [p.predicted for p in scored]
            mean_brier = float(np.mean(briers))
            half_brier = float(np.mean([(0.5 - a) ** 2 for a in actuals]))
            base_rate_val = float(np.mean(actuals))
            br_brier = float(np.mean([(base_rate_val - a) ** 2 for a in actuals]))
            eps = 1e-15
            log_scores = [
                -(a * math.log(max(eps, min(1 - eps, p))) + (1 - a) * math.log(max(eps, min(1 - eps, 1 - p))))
                for p, a in zip(probs, actuals, strict=False)
            ]

            print_header("FORECASTBENCH RESULTS", width=75)
            print(f"  Brier Score:       {mean_brier:.4f}")
            print(f"  Log Score:         {float(np.mean(log_scores)):.4f}")
            print(f"  Sharpness:         {float(np.mean([abs(p - 0.5) for p in probs])):.4f}")
            print(f"  Predictions:       {len(scored)}")
            print(f"  Cost:              ${sum(p.cost for p in preds):.4f}")
            print(f"  Base Rate:         {base_rate_val:.2f}")
            print(f"{'=' * 75}")
            print(
                f"  vs Always-0.5:     {mean_brier - half_brier:+.4f} {'(BETTER)' if mean_brier < half_brier else '(worse)'}"
            )
            print(
                f"  vs Base-Rate:      {mean_brier - br_brier:+.4f} {'(BETTER)' if mean_brier < br_brier else '(worse)'}"
            )
            skill = 1 - mean_brier / half_brier if half_brier > 0 else 0
            print(f"  Skill Score:       {skill:.4f}")

            srcs = sorted({p.source for p in preds})
            if len(srcs) > 1:
                print(f"\n  {'Source':<12} {'Brier':>8} {'N':>5} {'Cost':>8}")
                print(f"  {'-' * 35}")
                for s in srcs:
                    sp = [p for p in preds if p.source == s and p.brier is not None]
                    if sp:
                        print(
                            f"  {s:<12} {np.mean([p.brier for p in sp]):>8.4f} {len(sp):>5} ${sum(p.cost for p in sp):>7.4f}"
                        )

            methods = sorted({p.method for p in preds})
            if len(methods) > 1:
                print(f"\n  {'Method':<18} {'Brier':>8} {'N':>5}")
                print(f"  {'-' * 33}")
                for m in methods:
                    mp = [p for p in preds if p.method == m and p.brier is not None]
                    if mp:
                        print(f"  {m:<18} {np.mean([p.brier for p in mp]):>8.4f} {len(mp):>5}")

            print(f"{'=' * 75}\n")

    if args.output:
        output = {
            "benchmark": "forecastbench",
            "question_set": q_data.get("question_set", ""),
            "timestamp": datetime.now(UTC).isoformat(),
            "config": {"model": args.model, "search": args.search, "fred_data": use_fred},
            "metrics": {},
            "forecasts": [
                {
                    "question_id": p.question_id,
                    "probability": p.predicted,
                    "source": p.source,
                    "actual": p.actual,
                    "brier": p.brier,
                    "method": p.method,
                    "rationale": p.rationale,
                }
                for p in preds
            ],
        }
        with open(args.output, "w") as f:
            json.dump(output, f, indent=2, default=str)
        print(f"Saved to {args.output}")


if __name__ == "__main__":
    main()
