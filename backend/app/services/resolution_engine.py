"""Resolution engine for scoring forecasts against actual outcomes.

Handles the lifecycle of forecast resolution: marking outcomes,
computing all scoring metrics, and generating human-readable feedback.
"""

from __future__ import annotations

import logging
import math
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Sequence

from .calibration import CalibrationEngine

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------

@dataclass
class ResolutionRecord:
    """Represents the resolution of a single forecast run."""

    id: uuid.UUID
    forecast_run_id: uuid.UUID
    question_id: uuid.UUID
    predicted_value: float
    actual_value: float
    actual_date: date
    brier_score: float | None = None
    log_score: float | None = None
    absolute_error: float | None = None
    relative_error: float | None = None
    resolved_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ResolutionFeedback:
    """Human-readable feedback on a resolved forecast."""

    resolution_id: uuid.UUID
    grade: str  # "excellent", "good", "fair", "poor"
    summary: str
    brier_score: float
    log_score: float
    details: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class ResolutionEngine:
    """Resolve forecasting questions and compute performance scores.

    This engine does **not** access the database directly.  The caller
    provides serialised forecast-run data and receives plain dataclass
    results to persist.
    """

    def __init__(
        self,
        calibration_engine: CalibrationEngine | None = None,
    ) -> None:
        self.calibration = calibration_engine or CalibrationEngine()

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------

    def resolve_forecast(
        self,
        forecast_run: dict[str, Any],
        actual_value: float,
        actual_date: date,
    ) -> ResolutionRecord:
        """Mark a forecast as resolved and compute raw scores.

        Parameters
        ----------
        forecast_run:
            Serialised ``ForecastRun`` dict with at least ``id``,
            ``question_id``, and ``posterior_value``.
        actual_value:
            The realised outcome.  For binary questions this is 0 or 1.
            For continuous questions it is the observed measurement.
        actual_date:
            The date the outcome was determined.

        Returns
        -------
        ResolutionRecord
        """
        forecast_run_id = uuid.UUID(str(forecast_run["id"]))
        question_id = uuid.UUID(str(forecast_run["question_id"]))
        predicted = float(forecast_run["posterior_value"])
        target_type = forecast_run.get("target_type", "binary")

        if target_type == "binary":
            brier = (predicted - actual_value) ** 2
            eps = 1e-15
            p_clipped = max(min(predicted, 1.0 - eps), eps)
            if actual_value == 1.0:
                log_s = -math.log(p_clipped)
            else:
                log_s = -math.log(1.0 - p_clipped)
            abs_err = abs(predicted - actual_value)
            rel_err = None
        else:
            brier = None
            log_s = None
            abs_err = abs(predicted - actual_value)
            rel_err = (
                abs_err / abs(actual_value) if actual_value != 0 else None
            )

        record = ResolutionRecord(
            id=uuid.uuid4(),
            forecast_run_id=forecast_run_id,
            question_id=question_id,
            predicted_value=predicted,
            actual_value=actual_value,
            actual_date=actual_date,
            brier_score=brier,
            log_score=log_s,
            absolute_error=abs_err,
            relative_error=rel_err,
        )

        logger.info(
            "Resolved forecast %s: predicted=%.4f, actual=%.4f, "
            "brier=%s, abs_err=%.4f",
            forecast_run_id,
            predicted,
            actual_value,
            f"{brier:.4f}" if brier is not None else "N/A",
            abs_err,
        )
        return record

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def score_forecast(
        self,
        resolution: ResolutionRecord,
    ) -> dict[str, float | None]:
        """Compute all available scores for a resolved forecast.

        Parameters
        ----------
        resolution:
            A ``ResolutionRecord`` (from :py:meth:`resolve_forecast`).

        Returns
        -------
        dict
            Keys: ``brier_score``, ``log_score``, ``absolute_error``,
            ``relative_error``, ``surprise`` (how unexpected the
            outcome was on a 0-1 scale).
        """
        # Surprise metric: how far is the outcome from the prediction?
        # For binary: surprise = |predicted - actual|.
        # For continuous: normalised by the prediction itself.
        if resolution.brier_score is not None:
            surprise = abs(resolution.predicted_value - resolution.actual_value)
        elif resolution.relative_error is not None:
            surprise = min(resolution.relative_error, 1.0)
        else:
            surprise = abs(
                resolution.predicted_value - resolution.actual_value
            )

        return {
            "brier_score": resolution.brier_score,
            "log_score": resolution.log_score,
            "absolute_error": resolution.absolute_error,
            "relative_error": resolution.relative_error,
            "surprise": surprise,
        }

    # ------------------------------------------------------------------
    # Feedback
    # ------------------------------------------------------------------

    def generate_feedback(
        self,
        resolution: ResolutionRecord,
    ) -> ResolutionFeedback:
        """Generate a human-readable summary of forecast performance.

        The grade scale for binary forecasts (by Brier score):
            - **Excellent**: Brier < 0.05
            - **Good**:      Brier < 0.15
            - **Fair**:      Brier < 0.30
            - **Poor**:      Brier >= 0.30

        For continuous forecasts (by relative error):
            - **Excellent**: rel. error < 5 %
            - **Good**:      rel. error < 15 %
            - **Fair**:      rel. error < 30 %
            - **Poor**:      rel. error >= 30 %

        Parameters
        ----------
        resolution:
            A ``ResolutionRecord``.

        Returns
        -------
        ResolutionFeedback
        """
        brier = resolution.brier_score
        log_s = resolution.log_score

        if brier is not None:
            # Binary grading.
            if brier < 0.05:
                grade = "excellent"
                comment = (
                    "The forecast was highly accurate.  The predicted "
                    f"probability ({resolution.predicted_value:.2f}) closely "
                    f"matched the outcome ({resolution.actual_value:.0f})."
                )
            elif brier < 0.15:
                grade = "good"
                comment = (
                    "The forecast was reasonably well-calibrated.  "
                    f"Predicted {resolution.predicted_value:.2f}, "
                    f"outcome was {resolution.actual_value:.0f}."
                )
            elif brier < 0.30:
                grade = "fair"
                comment = (
                    "The forecast showed moderate accuracy.  Consider "
                    "reviewing evidence scoring weights and base-rate "
                    "estimation."
                )
            else:
                grade = "poor"
                comment = (
                    "The forecast was significantly off.  A thorough "
                    "review of the evidence pipeline and prior "
                    "calibration is recommended."
                )
            summary = (
                f"Grade: {grade.upper()}.  Brier={brier:.4f}, "
                f"Log={log_s:.4f}.  {comment}"
            )
        else:
            # Continuous grading.
            rel = resolution.relative_error
            if rel is not None and rel < 0.05:
                grade = "excellent"
            elif rel is not None and rel < 0.15:
                grade = "good"
            elif rel is not None and rel < 0.30:
                grade = "fair"
            else:
                grade = "poor"

            abs_err = resolution.absolute_error or 0.0
            summary = (
                f"Grade: {grade.upper()}.  "
                f"Absolute error={abs_err:.4f}, "
                f"Relative error={rel:.2%}.  "
                f"Predicted {resolution.predicted_value:.4f}, "
                f"actual {resolution.actual_value:.4f}."
            ) if rel is not None else (
                f"Grade: {grade.upper()}.  "
                f"Absolute error={abs_err:.4f}.  "
                f"Predicted {resolution.predicted_value:.4f}, "
                f"actual {resolution.actual_value:.4f}."
            )

        return ResolutionFeedback(
            resolution_id=resolution.id,
            grade=grade,
            summary=summary,
            brier_score=brier if brier is not None else 0.0,
            log_score=log_s if log_s is not None else 0.0,
        )

    # ------------------------------------------------------------------
    # Batch operations
    # ------------------------------------------------------------------

    def batch_resolve(
        self,
        forecast_runs: Sequence[dict[str, Any]],
        actuals: Sequence[dict[str, Any]],
    ) -> list[ResolutionRecord]:
        """Resolve multiple forecasts in bulk.

        Parameters
        ----------
        forecast_runs:
            List of serialised ``ForecastRun`` dicts.
        actuals:
            List of dicts with ``actual_value`` and ``actual_date``,
            positionally matching ``forecast_runs``.

        Returns
        -------
        list[ResolutionRecord]
        """
        if len(forecast_runs) != len(actuals):
            raise ValueError(
                f"Length mismatch: {len(forecast_runs)} forecast runs "
                f"vs {len(actuals)} actuals."
            )

        records: list[ResolutionRecord] = []
        for run, actual in zip(forecast_runs, actuals):
            actual_val = float(actual["actual_value"])
            actual_dt = actual["actual_date"]
            if isinstance(actual_dt, str):
                actual_dt = date.fromisoformat(actual_dt)

            record = self.resolve_forecast(run, actual_val, actual_dt)
            records.append(record)

        logger.info("Batch resolved %d forecasts.", len(records))
        return records
