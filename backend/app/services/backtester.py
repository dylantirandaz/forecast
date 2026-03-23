"""Backtesting engine for evaluating model performance on historical data.

Replays forecasts at historical cutoff dates using only data that was
available at the time, then scores them against known outcomes.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Sequence

import numpy as np

from .calibration import CalibrationEngine
from .forecast_engine import ForecastEngine, ForecastResult
from .resolution_engine import ResolutionEngine, ResolutionRecord

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------

@dataclass
class BacktestConfig:
    """Configuration for a backtest run."""

    start_date: date
    end_date: date
    step_days: int = 90  # generate a cutoff every N days
    question: dict[str, Any] = field(default_factory=dict)
    scenario: dict[str, Any] | None = None
    model_version_id: uuid.UUID | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class BacktestForecast:
    """A single forecast produced during a backtest at a specific cutoff."""

    cutoff_date: date
    forecast_result: ForecastResult
    data_points_used: int


@dataclass
class BacktestScore:
    """Aggregated scores for a completed backtest."""

    mean_brier: float | None = None
    mean_log: float | None = None
    mean_absolute_error: float | None = None
    coverage_90: float | None = None  # fraction of actuals within 90% CI
    n_forecasts: int = 0
    per_cutoff_scores: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class BacktestRun:
    """Complete backtest run with forecasts and scores."""

    id: uuid.UUID
    config: BacktestConfig
    forecasts: list[BacktestForecast]
    resolutions: list[ResolutionRecord]
    score: BacktestScore | None = None
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


@dataclass
class ModelComparison:
    """Comparison of multiple backtest results."""

    model_scores: dict[str, BacktestScore]
    best_model: str
    summary: str


@dataclass
class BacktestReport:
    """Summary report for a backtest run."""

    backtest_id: uuid.UUID
    n_cutoffs: int
    score: BacktestScore
    calibration_summary: str
    summary: str
    plot_data: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class Backtester:
    """Run historical replay backtests to evaluate forecast configurations.

    The backtester simulates what would have happened if the model had
    been run at each historical cutoff date using only the data available
    at that time.  Forecasts are then scored against known outcomes.
    """

    def __init__(
        self,
        forecast_engine: ForecastEngine | None = None,
        resolution_engine: ResolutionEngine | None = None,
        calibration_engine: CalibrationEngine | None = None,
    ) -> None:
        self.forecast_engine = forecast_engine or ForecastEngine()
        self.resolution_engine = resolution_engine or ResolutionEngine()
        self.calibration_engine = calibration_engine or CalibrationEngine()

    # ------------------------------------------------------------------
    # Time-window generation
    # ------------------------------------------------------------------

    @staticmethod
    def create_time_windows(
        start: date,
        end: date,
        step_days: int = 90,
    ) -> list[date]:
        """Generate a list of cutoff dates between *start* and *end*.

        Parameters
        ----------
        start:
            First cutoff date (inclusive).
        end:
            Last possible cutoff date (inclusive).
        step_days:
            Number of days between successive cutoffs.

        Returns
        -------
        list[date]
            Chronologically ordered cutoff dates.
        """
        if start > end:
            raise ValueError(
                f"start ({start}) must be <= end ({end})."
            )

        cutoffs: list[date] = []
        current = start
        step = timedelta(days=step_days)
        while current <= end:
            cutoffs.append(current)
            current += step

        logger.info(
            "Generated %d cutoff dates from %s to %s (step=%d days).",
            len(cutoffs),
            start,
            end,
            step_days,
        )
        return cutoffs

    # ------------------------------------------------------------------
    # Single-cutoff simulation
    # ------------------------------------------------------------------

    def simulate_forecast_at(
        self,
        question: dict[str, Any],
        cutoff_date: date,
        full_time_series: Sequence[float],
        full_dates: Sequence[date],
        evidence_items: Sequence[dict[str, Any]],
        scenario: dict[str, Any] | None = None,
        model_version_id: uuid.UUID | None = None,
    ) -> BacktestForecast:
        """Produce a forecast using only data available before *cutoff_date*.

        Parameters
        ----------
        question:
            Serialised question dict.
        cutoff_date:
            Only observations with date <= cutoff_date are used.
        full_time_series:
            Complete historical time series values (same length as
            *full_dates*).
        full_dates:
            Dates corresponding to each observation in *full_time_series*.
        evidence_items:
            All evidence items; those published after *cutoff_date*
            will be filtered out.
        scenario:
            Optional scenario dict.
        model_version_id:
            Optional model version UUID.

        Returns
        -------
        BacktestForecast
        """
        # Filter time series to before cutoff.
        ts_values = []
        for val, dt in zip(full_time_series, full_dates):
            if dt <= cutoff_date:
                ts_values.append(val)

        if len(ts_values) < 2:
            raise ValueError(
                f"Not enough data points before cutoff {cutoff_date}: "
                f"got {len(ts_values)}, need >= 2."
            )

        # Filter evidence to before cutoff.
        available_evidence = []
        for ev in evidence_items:
            pub = ev.get("published_date")
            if pub is None:
                continue
            if isinstance(pub, str):
                pub = date.fromisoformat(pub)
            if pub <= cutoff_date:
                available_evidence.append(ev)

        result = self.forecast_engine.create_forecast(
            question=question,
            historical_data=ts_values,
            evidence_items=available_evidence,
            scenario=scenario,
            model_version_id=model_version_id,
        )

        return BacktestForecast(
            cutoff_date=cutoff_date,
            forecast_result=result,
            data_points_used=len(ts_values),
        )

    # ------------------------------------------------------------------
    # Full backtest run
    # ------------------------------------------------------------------

    def run_backtest(
        self,
        config: BacktestConfig,
        full_time_series: Sequence[float],
        full_dates: Sequence[date],
        evidence_items: Sequence[dict[str, Any]],
        actual_value: float,
        actual_date: date,
    ) -> BacktestRun:
        """Execute a full historical-replay backtest.

        Parameters
        ----------
        config:
            ``BacktestConfig`` with date range and question data.
        full_time_series:
            Complete time series of observations.
        full_dates:
            Dates for each observation.
        evidence_items:
            All available evidence items.
        actual_value:
            The true outcome to score against.
        actual_date:
            Date the outcome was realised.

        Returns
        -------
        BacktestRun
        """
        run_id = uuid.uuid4()
        cutoffs = self.create_time_windows(
            config.start_date, config.end_date, config.step_days
        )

        forecasts: list[BacktestForecast] = []
        for cutoff in cutoffs:
            try:
                bt_forecast = self.simulate_forecast_at(
                    question=config.question,
                    cutoff_date=cutoff,
                    full_time_series=full_time_series,
                    full_dates=full_dates,
                    evidence_items=evidence_items,
                    scenario=config.scenario,
                    model_version_id=config.model_version_id,
                )
                forecasts.append(bt_forecast)
            except ValueError as exc:
                logger.warning(
                    "Skipping cutoff %s: %s", cutoff, exc
                )
                continue

        # Resolve each forecast.
        resolutions: list[ResolutionRecord] = []
        for bt_fc in forecasts:
            run_dict = {
                "id": str(bt_fc.forecast_result.forecast_run_id),
                "question_id": str(bt_fc.forecast_result.question_id),
                "posterior_value": bt_fc.forecast_result.posterior_value,
                "target_type": config.question.get("target_type", "binary"),
            }
            resolution = self.resolution_engine.resolve_forecast(
                forecast_run=run_dict,
                actual_value=actual_value,
                actual_date=actual_date,
            )
            resolutions.append(resolution)

        backtest_run = BacktestRun(
            id=run_id,
            config=config,
            forecasts=forecasts,
            resolutions=resolutions,
        )

        # Score.
        backtest_run.score = self.score_backtest(backtest_run)

        logger.info(
            "Backtest %s complete: %d cutoffs, %d forecasts, "
            "mean_brier=%s",
            run_id,
            len(cutoffs),
            len(forecasts),
            (
                f"{backtest_run.score.mean_brier:.4f}"
                if backtest_run.score.mean_brier is not None
                else "N/A"
            ),
        )
        return backtest_run

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def score_backtest(
        self,
        backtest_run: BacktestRun,
    ) -> BacktestScore:
        """Score all forecasts in a backtest run against their actuals.

        Parameters
        ----------
        backtest_run:
            A ``BacktestRun`` with populated ``resolutions``.

        Returns
        -------
        BacktestScore
        """
        resolutions = backtest_run.resolutions
        if not resolutions:
            return BacktestScore(n_forecasts=0)

        brier_scores = [
            r.brier_score for r in resolutions if r.brier_score is not None
        ]
        log_scores = [
            r.log_score for r in resolutions if r.log_score is not None
        ]
        abs_errors = [
            r.absolute_error for r in resolutions
            if r.absolute_error is not None
        ]

        mean_brier = (
            float(np.mean(brier_scores)) if brier_scores else None
        )
        mean_log = (
            float(np.mean(log_scores)) if log_scores else None
        )
        mean_abs = (
            float(np.mean(abs_errors)) if abs_errors else None
        )

        # Coverage: fraction of actuals within the 90% confidence
        # interval (approximated as [conf_lower, conf_upper]).
        in_ci = 0
        ci_count = 0
        for bt_fc, res in zip(backtest_run.forecasts, resolutions):
            lo = bt_fc.forecast_result.confidence_lower
            hi = bt_fc.forecast_result.confidence_upper
            if lo is not None and hi is not None:
                ci_count += 1
                if lo <= res.actual_value <= hi:
                    in_ci += 1

        coverage = in_ci / ci_count if ci_count > 0 else None

        # Per-cutoff detail.
        per_cutoff: list[dict[str, Any]] = []
        for bt_fc, res in zip(backtest_run.forecasts, resolutions):
            per_cutoff.append({
                "cutoff_date": bt_fc.cutoff_date.isoformat(),
                "predicted": res.predicted_value,
                "actual": res.actual_value,
                "brier": res.brier_score,
                "log_score": res.log_score,
                "absolute_error": res.absolute_error,
                "data_points_used": bt_fc.data_points_used,
            })

        return BacktestScore(
            mean_brier=mean_brier,
            mean_log=mean_log,
            mean_absolute_error=mean_abs,
            coverage_90=coverage,
            n_forecasts=len(resolutions),
            per_cutoff_scores=per_cutoff,
        )

    # ------------------------------------------------------------------
    # Model comparison
    # ------------------------------------------------------------------

    @staticmethod
    def compare_models(
        backtest_results: dict[str, BacktestRun],
    ) -> ModelComparison:
        """Compare backtest results across different model configurations.

        Parameters
        ----------
        backtest_results:
            Mapping of model label to ``BacktestRun``.

        Returns
        -------
        ModelComparison
        """
        scores: dict[str, BacktestScore] = {}
        for label, run in backtest_results.items():
            if run.score is not None:
                scores[label] = run.score

        if not scores:
            return ModelComparison(
                model_scores={},
                best_model="none",
                summary="No scored backtest runs to compare.",
            )

        # Determine best model by mean Brier (lowest wins) or mean
        # absolute error if Brier is unavailable.
        def _sort_key(item: tuple[str, BacktestScore]) -> float:
            s = item[1]
            if s.mean_brier is not None:
                return s.mean_brier
            if s.mean_absolute_error is not None:
                return s.mean_absolute_error
            return float("inf")

        ranked = sorted(scores.items(), key=_sort_key)
        best_label = ranked[0][0]

        lines = ["Model Comparison:"]
        for label, sc in ranked:
            marker = " *" if label == best_label else ""
            brier_str = (
                f"{sc.mean_brier:.4f}" if sc.mean_brier is not None else "N/A"
            )
            mae_str = (
                f"{sc.mean_absolute_error:.4f}"
                if sc.mean_absolute_error is not None
                else "N/A"
            )
            lines.append(
                f"  {label}: Brier={brier_str}, MAE={mae_str}, "
                f"n={sc.n_forecasts}{marker}"
            )
        lines.append(f"Best model: {best_label}")

        return ModelComparison(
            model_scores=scores,
            best_model=best_label,
            summary="\n".join(lines),
        )

    # ------------------------------------------------------------------
    # Report generation
    # ------------------------------------------------------------------

    def generate_backtest_report(
        self,
        backtest_run: BacktestRun,
    ) -> BacktestReport:
        """Generate a summary report with scores and plot-ready data.

        Parameters
        ----------
        backtest_run:
            A completed ``BacktestRun``.

        Returns
        -------
        BacktestReport
        """
        score = backtest_run.score or self.score_backtest(backtest_run)

        # Calibration analysis on the backtest predictions.
        predictions = [r.predicted_value for r in backtest_run.resolutions]
        actuals = [r.actual_value for r in backtest_run.resolutions]

        cal_summary = "Insufficient data for calibration curve."
        if len(predictions) >= 5:
            try:
                cal_report = self.calibration_engine.generate_calibration_report(
                    predictions, actuals
                )
                cal_summary = cal_report.summary
            except Exception as exc:
                cal_summary = f"Calibration analysis failed: {exc}"

        # Build plot data.
        cutoff_dates = [
            f.cutoff_date.isoformat() for f in backtest_run.forecasts
        ]
        predicted_vals = [
            f.forecast_result.posterior_value
            for f in backtest_run.forecasts
        ]
        actual_val = (
            backtest_run.resolutions[0].actual_value
            if backtest_run.resolutions
            else None
        )

        plot_data = {
            "cutoff_dates": cutoff_dates,
            "predicted_values": predicted_vals,
            "actual_value": actual_val,
            "confidence_lower": [
                f.forecast_result.confidence_lower
                for f in backtest_run.forecasts
            ],
            "confidence_upper": [
                f.forecast_result.confidence_upper
                for f in backtest_run.forecasts
            ],
        }

        brier_str = (
            f"{score.mean_brier:.4f}"
            if score.mean_brier is not None
            else "N/A"
        )
        cov_str = (
            f"{score.coverage_90:.1%}"
            if score.coverage_90 is not None
            else "N/A"
        )
        summary_lines = [
            f"Backtest Report (id={backtest_run.id})",
            f"  Cutoffs:        {len(backtest_run.forecasts)}",
            f"  Mean Brier:     {brier_str}",
            f"  90% Coverage:   {cov_str}",
            f"  Mean Abs Error: "
            + (
                f"{score.mean_absolute_error:.4f}"
                if score.mean_absolute_error is not None
                else "N/A"
            ),
        ]

        return BacktestReport(
            backtest_id=backtest_run.id,
            n_cutoffs=len(backtest_run.forecasts),
            score=score,
            calibration_summary=cal_summary,
            summary="\n".join(summary_lines),
            plot_data=plot_data,
        )
