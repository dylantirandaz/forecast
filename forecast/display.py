from __future__ import annotations

from forecast.metrics import baseline_always_half, baseline_base_rate, skill_score


def print_header(title: str, width: int = 70) -> None:
    print(f"\n{'=' * width}")
    print(f"  {title}")
    print(f"{'=' * width}")


def print_metrics(metrics: dict, model: str = "", mode: str = "") -> None:
    label = f"{mode.upper()} mode, {model}" if mode and model else "RESULTS"
    print_header(f"RESULTS — {label}" if model else f"EVALUATION: {label}")
    print(f"  Mean Brier Score:     {metrics['brier']:.4f}")
    print(f"  Mean Log Score:       {metrics['log_score']:.4f}")
    print(f"  Calibration Error:    {metrics['ece']:.4f}")
    print(f"  Sharpness:            {metrics['sharpness']:.4f}")
    print(f"  Predictions:          {metrics['n']}")
    if "cost" in metrics:
        print(f"  Total Cost:           ${metrics['cost']:.4f}")
    if "avg_latency_ms" in metrics:
        print(f"  Avg Latency:          {metrics['avg_latency_ms']:.0f}ms")
    print(f"{'=' * 70}")


def print_baselines(metrics: dict, actuals: list[float]) -> None:
    half_brier = baseline_always_half(actuals)
    br_brier = baseline_base_rate(actuals)
    label_better = "(BETTER)" if metrics["brier"] < half_brier else "(worse)"
    label_br = "(BETTER)" if metrics["brier"] < br_brier else "(worse)"
    print(f"  vs Always-0.5:        {metrics['brier'] - half_brier:+.4f} {label_better}")
    print(f"  vs Base-Rate-Only:    {metrics['brier'] - br_brier:+.4f} {label_br}")
    print(f"  Skill Score:          {skill_score(metrics['brier'], half_brier):.4f}")


def print_domain_breakdown(predictions: list, compute_fn: callable, show_cost: bool = False) -> None:
    domains = sorted({p.domain for p in predictions})
    if len(domains) <= 1:
        return
    if show_cost:
        print(f"\n  {'Domain':<15} {'Brier':>8} {'Log':>8} {'N':>5} {'Cost':>8}")
        print(f"  {'-' * 46}")
    else:
        print(f"\n  {'Domain':<15} {'Brier':>8} {'Log':>8} {'N':>5}")
        print(f"  {'-' * 38}")
    for d in domains:
        dm = compute_fn([p for p in predictions if p.domain == d])
        if show_cost:
            print(f"  {d:<15} {dm['brier']:>8.4f} {dm['log_score']:>8.4f} {dm['n']:>5} ${dm.get('cost', 0):>7.4f}")
        else:
            print(f"  {d:<15} {dm['brier']:>8.4f} {dm['log_score']:>8.4f} {dm['n']:>5}")


def print_horizon_breakdown(predictions: list, cutoffs: list[int], compute_fn: callable) -> None:
    if len(cutoffs) <= 1:
        return
    print(f"\n  {'Horizon':<10} {'Brier':>8} {'Log':>8} {'Sharp':>8} {'N':>5}")
    print(f"  {'-' * 42}")
    for h in sorted(cutoffs, reverse=True):
        hm = compute_fn([p for p in predictions if p.cutoff_days == h])
        if hm:
            print(f"  {h}d{'':<8} {hm['brier']:>8.4f} {hm['log_score']:>8.4f} {hm['sharpness']:>8.4f} {hm['n']:>5}")


def print_comparison_table(results: dict[str, dict]) -> None:
    best_name = min(results, key=lambda k: results[k]["metrics"]["brier"])
    best_brier = results[best_name]["metrics"]["brier"]

    print_header("COMPARISON TABLE (sorted by Brier score)", width=90)
    print(f"  {'Config':<30} {'Brier':>8} {'Delta':>8} {'Log':>8} {'ECE':>8} {'Sharp':>8}")
    print(f"  {'-' * 75}")

    for name in sorted(results, key=lambda k: results[k]["metrics"]["brier"]):
        m = results[name]["metrics"]
        delta = m["brier"] - best_brier
        marker = " *BEST*" if delta == 0 else ""
        print(
            f"  {name:<30} {m['brier']:>8.4f} {delta:>+8.4f} {m['log_score']:>8.4f} {m['ece']:>8.4f} {m['sharpness']:>8.4f}{marker}"
        )

    print("\n  *BEST* = best configuration")


def print_prediction_row(pred, verbose: bool = False) -> None:
    text = pred.question_text[:52] + "..." if len(pred.question_text) > 55 else pred.question_text
    print(f"  {text:<55} {pred.cutoff_days:>3}d {pred.predicted:>6.3f} {pred.actual:>4.0f} {pred.brier:>7.4f}")


def print_confidence_breakdown(predictions: list, compute_fn: callable) -> None:
    confs = sorted({getattr(p, "confidence", "medium") for p in predictions})
    if len(confs) <= 1:
        return
    print(f"\n  {'Confidence':<12} {'Brier':>8} {'Sharp':>8} {'N':>5}")
    print(f"  {'-' * 36}")
    for c in confs:
        cm = compute_fn([p for p in predictions if getattr(p, "confidence", "medium") == c])
        if cm:
            print(f"  {c:<12} {cm['brier']:>8.4f} {cm['sharpness']:>8.4f} {cm['n']:>5}")


def format_evidence(evidence: list[dict]) -> str:
    if not evidence:
        return "No evidence available."
    return "\n\n".join(
        f"[{i}] {ev.get('source', '?')} ({ev.get('source_type', '?')}) — {ev.get('published_at', '?')}\n"
        f"    {ev.get('title', '')}\n"
        f"    {ev.get('content', '')}"
        for i, ev in enumerate(evidence[:15])
    )
