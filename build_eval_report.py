#!/usr/bin/env python3
"""
Build a comprehensive eval report combining baseline (no search) and
AskNews search results, with contamination analysis.

Usage:
    python build_eval_report.py
    python build_eval_report.py --baseline eval_baseline_no_search.json --search eval_asknews_search.json
"""

import argparse
import json
import csv
from datetime import datetime, timezone
from pathlib import Path


def load_results(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def compute_contamination(baseline_preds: list, search_preds: list) -> list:
    """
    Compare each prediction with and without search to assess contamination.

    Contamination signals:
    - If the model gets it right WITHOUT search, the answer may be in training data.
    - If search IMPROVES accuracy, the pipeline is adding genuine value.
    - If search WORSENS accuracy, the judge may be leaking misleading info.
    """
    # Group by (question, cutoff)
    baseline_map = {}
    for p in baseline_preds:
        key = (p["question"], p["cutoff"])
        baseline_map[key] = p

    results = []
    for sp in search_preds:
        key = (sp["question"], sp["cutoff"])
        bp = baseline_map.get(key)
        if not bp:
            continue

        actual = sp["actual"]
        b_pred = bp["predicted"]
        s_pred = sp["predicted"]
        b_brier = bp["brier"]
        s_brier = sp["brier"]

        # Direction correct?
        b_correct = (b_pred > 0.5) == (actual == 1) if actual in (0, 1) else None
        s_correct = (s_pred > 0.5) == (actual == 1) if actual in (0, 1) else None

        # Brier improvement from search
        brier_delta = s_brier - b_brier  # negative = search helped

        # Contamination risk scoring:
        # High: model nails it without search (brier < 0.05) -> training data leak
        # Medium: model roughly right without search (brier < 0.15)
        # Low: model uncertain without search (brier >= 0.15)
        # None: model wrong without search (brier >= 0.25)
        if b_brier < 0.05:
            contamination_risk = "high"
        elif b_brier < 0.15:
            contamination_risk = "medium"
        elif b_brier < 0.25:
            contamination_risk = "low"
        else:
            contamination_risk = "none"

        # Search value assessment
        if brier_delta < -0.1:
            search_value = "high_positive"
        elif brier_delta < -0.02:
            search_value = "positive"
        elif brier_delta < 0.02:
            search_value = "neutral"
        elif brier_delta < 0.1:
            search_value = "negative"
        else:
            search_value = "high_negative"

        results.append({
            "question": sp["question"],
            "domain": sp["domain"],
            "cutoff_days": sp["cutoff"],
            "actual": actual,
            "baseline_predicted": b_pred,
            "search_predicted": s_pred,
            "baseline_brier": round(b_brier, 6),
            "search_brier": round(s_brier, 6),
            "brier_delta": round(brier_delta, 6),
            "baseline_correct": b_correct,
            "search_correct": s_correct,
            "baseline_confidence": bp.get("confidence", ""),
            "search_confidence": sp.get("confidence", ""),
            "contamination_risk": contamination_risk,
            "search_value": search_value,
            "baseline_rationale": bp.get("rationale", ""),
            "search_rationale": sp.get("rationale", ""),
            "search_cost": sp.get("cost", 0),
        })

    return results


def build_report(baseline_path: str, search_path: str) -> dict:
    baseline = load_results(baseline_path)
    search = load_results(search_path)

    comparisons = compute_contamination(
        baseline["predictions"], search["predictions"]
    )

    # Aggregate contamination stats
    risk_counts = {"high": 0, "medium": 0, "low": 0, "none": 0}
    value_counts = {
        "high_positive": 0, "positive": 0, "neutral": 0,
        "negative": 0, "high_negative": 0,
    }
    total_baseline_brier = 0
    total_search_brier = 0

    for c in comparisons:
        risk_counts[c["contamination_risk"]] += 1
        value_counts[c["search_value"]] += 1
        total_baseline_brier += c["baseline_brier"]
        total_search_brier += c["search_brier"]

    n = len(comparisons)
    contamination_pct = round(
        (risk_counts["high"] + risk_counts["medium"]) / n * 100, 1
    ) if n else 0

    report = {
        "report_metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "baseline_config": baseline["config"],
            "search_config": search["config"],
            "n_predictions": n,
            "questions_evaluated": n // 3 if n else 0,
            "cutoffs": [90, 30, 7],
        },
        "summary": {
            "baseline_brier": round(total_baseline_brier / n, 4) if n else 0,
            "search_brier": round(total_search_brier / n, 4) if n else 0,
            "brier_improvement_pct": round(
                (1 - total_search_brier / total_baseline_brier) * 100, 1
            ) if total_baseline_brier else 0,
            "baseline_metrics": baseline["metrics"],
            "search_metrics": search["metrics"],
        },
        "contamination_analysis": {
            "contamination_pct": contamination_pct,
            "risk_breakdown": risk_counts,
            "interpretation": (
                f"{contamination_pct}% of predictions show medium-to-high "
                f"contamination risk (model accurate without search). "
                f"This is expected for questions within the model's training window. "
                f"Search improved accuracy for "
                f"{value_counts['high_positive'] + value_counts['positive']} "
                f"predictions and was neutral/negative for "
                f"{value_counts['neutral'] + value_counts['negative'] + value_counts['high_negative']}."
            ),
        },
        "search_value_analysis": {
            "value_breakdown": value_counts,
            "search_helped_pct": round(
                (value_counts["high_positive"] + value_counts["positive"]) / n * 100, 1
            ) if n else 0,
            "search_hurt_pct": round(
                (value_counts["negative"] + value_counts["high_negative"]) / n * 100, 1
            ) if n else 0,
        },
        "predictions": comparisons,
    }

    return report


def write_csv(comparisons: list, path: str):
    if not comparisons:
        return
    fields = list(comparisons[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(comparisons)


def main():
    parser = argparse.ArgumentParser(description="Build comprehensive eval report")
    parser.add_argument(
        "--baseline", default="eval_baseline_no_search.json",
        help="Baseline (no search) results JSON",
    )
    parser.add_argument(
        "--search", default="eval_asknews_search.json",
        help="AskNews search results JSON",
    )
    parser.add_argument(
        "--output", "-o", default="eval_report.json",
        help="Output report JSON path",
    )
    parser.add_argument(
        "--csv", default="eval_report.csv",
        help="Output CSV path",
    )
    args = parser.parse_args()

    report = build_report(args.baseline, args.search)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)
    print(f"Report saved to {args.output}")

    write_csv(report["predictions"], args.csv)
    print(f"CSV saved to {args.csv}")

    # Print summary
    s = report["summary"]
    c = report["contamination_analysis"]
    v = report["search_value_analysis"]
    print(f"\n{'=' * 60}")
    print(f"  EVAL REPORT — {report['report_metadata']['questions_evaluated']} questions, "
          f"{report['report_metadata']['n_predictions']} predictions")
    print(f"{'=' * 60}")
    print(f"  Baseline Brier:       {s['baseline_brier']:.4f}")
    print(f"  Search Brier:         {s['search_brier']:.4f}")
    print(f"  Improvement:          {s['brier_improvement_pct']:.1f}%")
    print(f"{'=' * 60}")
    print(f"  Contamination Risk:   {c['contamination_pct']:.1f}%")
    print(f"    High:    {c['risk_breakdown']['high']}")
    print(f"    Medium:  {c['risk_breakdown']['medium']}")
    print(f"    Low:     {c['risk_breakdown']['low']}")
    print(f"    None:    {c['risk_breakdown']['none']}")
    print(f"{'=' * 60}")
    print(f"  Search Helped:        {v['search_helped_pct']:.1f}%")
    print(f"  Search Hurt:          {v['search_hurt_pct']:.1f}%")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
