from __future__ import annotations

import math
from typing import Protocol

import numpy as np


class HasPrediction(Protocol):
    predicted: float
    actual: float


class HasBrierAndLog(Protocol):
    predicted: float
    actual: float
    brier: float
    log_score: float


def brier_score(predicted: float, actual: float) -> float:
    return (predicted - actual) ** 2


def log_score(predicted: float, actual: float) -> float:
    eps = 1e-15
    clamped = max(eps, min(1 - eps, predicted))
    return -(actual * math.log(clamped) + (1 - actual) * math.log(1 - clamped))


def compute_ece(predictions: list[float], actuals: list[float], n_bins: int = 10) -> float:
    if not predictions:
        return 0.0
    bins: list[list[tuple[float, float]]] = [[] for _ in range(n_bins)]
    for pred, act in zip(predictions, actuals, strict=False):
        b = min(int(pred * n_bins), n_bins - 1)
        bins[b].append((pred, act))
    total = len(predictions)
    return sum(len(b) / total * abs(np.mean([x[0] for x in b]) - np.mean([x[1] for x in b])) for b in bins if b)


def compute_sharpness(predictions: list[float]) -> float:
    if not predictions:
        return 0.0
    return float(np.mean([abs(p - 0.5) for p in predictions]))


def compute_metrics(predictions: list) -> dict:
    if not predictions:
        return {}
    briers = [p.brier for p in predictions]
    logs = [p.log_score for p in predictions]
    probs = [p.predicted for p in predictions]
    actuals = [p.actual for p in predictions]

    ece = compute_ece(probs, actuals)

    result = {
        "brier": round(float(np.mean(briers)), 6),
        "log_score": round(float(np.mean(logs)), 6),
        "ece": round(float(ece), 6),
        "sharpness": round(float(np.mean([abs(p - 0.5) for p in probs])), 6),
        "n": len(predictions),
    }

    if hasattr(predictions[0], "cost"):
        result["cost"] = round(sum(getattr(p, "cost", 0) for p in predictions), 4)
    if hasattr(predictions[0], "latency_ms"):
        result["avg_latency_ms"] = round(float(np.mean([getattr(p, "latency_ms", 0) for p in predictions])))

    return result


def baseline_always_half(actuals: list[float]) -> float:
    return float(np.mean([(0.5 - a) ** 2 for a in actuals]))


def baseline_base_rate(actuals: list[float]) -> float:
    rate = float(np.mean(actuals))
    return float(np.mean([(rate - a) ** 2 for a in actuals]))


def skill_score(model_brier: float, baseline_brier: float) -> float:
    if baseline_brier <= 0:
        return 0.0
    return 1 - model_brier / baseline_brier
