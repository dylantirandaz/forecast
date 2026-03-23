"""Experiment tracking for reproducibility and comparison.

Stores experiment configurations, per-forecast logs, and aggregate
results in memory with optional JSON persistence.  Supports querying
experiment history, comparing runs, and identifying the best
configurations.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------

@dataclass
class ForecastLog:
    """A single forecast logged within an experiment."""

    question_id: str
    prediction: float
    actual: float | None = None
    cost: float | None = None
    target_type: str = "binary"
    domain: str | None = None
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExperimentRecord:
    """Full record of an experiment run."""

    experiment_id: str
    name: str
    experiment_type: str  # "ablation", "backtest", "benchmark", "custom"
    config: dict[str, Any]
    status: str = "running"  # "running", "completed", "failed"
    forecasts: list[ForecastLog] = field(default_factory=list)
    results: dict[str, Any] = field(default_factory=dict)
    started_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    completed_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ComparisonResult:
    """Result of comparing multiple experiments."""

    experiment_ids: list[str]
    metrics_table: list[dict[str, Any]]
    best_by_metric: dict[str, str]  # metric_name -> experiment_id
    summary: str
    chart_data: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class ExperimentTracker:
    """Tracks experiment runs, configs, and results for reproducibility.

    Stores all data in memory with optional persistence to a JSON file.
    Thread-safe for single-process async use.
    """

    def __init__(
        self,
        persist_path: str | Path | None = None,
    ) -> None:
        self._experiments: dict[str, ExperimentRecord] = {}
        self._persist_path = Path(persist_path) if persist_path else None

        # Load existing data if persistence file exists.
        if self._persist_path and self._persist_path.exists():
            self._load()

    # ------------------------------------------------------------------
    # Experiment lifecycle
    # ------------------------------------------------------------------

    def create_experiment(
        self,
        name: str,
        config: dict[str, Any],
        experiment_type: str = "ablation",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Create a new experiment run.

        Parameters
        ----------
        name:
            Human-readable experiment name.
        config:
            Full configuration dict (should be JSON-serializable).
        experiment_type:
            ``"ablation"``, ``"backtest"``, ``"benchmark"``, or ``"custom"``.
        metadata:
            Optional additional metadata.

        Returns
        -------
        str
            Unique experiment_id.
        """
        experiment_id = str(uuid.uuid4())

        record = ExperimentRecord(
            experiment_id=experiment_id,
            name=name,
            experiment_type=experiment_type,
            config=config,
            metadata=metadata or {},
        )

        self._experiments[experiment_id] = record
        self._save()

        logger.info(
            "Created experiment '%s' (id=%s, type=%s).",
            name,
            experiment_id,
            experiment_type,
        )
        return experiment_id

    def log_forecast(
        self,
        experiment_id: str,
        question_id: str,
        prediction: float,
        actual: float | None = None,
        cost: float | None = None,
        target_type: str = "binary",
        domain: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Log a single forecast within an experiment.

        Parameters
        ----------
        experiment_id:
            The experiment to log to.
        question_id:
            Identifier for the question being forecast.
        prediction:
            The predicted value (probability for binary, point
            estimate for continuous).
        actual:
            The actual outcome, if known.
        cost:
            Cost incurred for this forecast.
        target_type:
            ``"binary"`` or ``"continuous"``.
        domain:
            Optional domain classification.
        metadata:
            Optional additional metadata.
        """
        record = self._get_experiment(experiment_id)

        log_entry = ForecastLog(
            question_id=question_id,
            prediction=prediction,
            actual=actual,
            cost=cost,
            target_type=target_type,
            domain=domain,
            metadata=metadata or {},
        )

        record.forecasts.append(log_entry)
        self._save()

    def complete_experiment(
        self,
        experiment_id: str,
        results: dict[str, Any],
    ) -> None:
        """Mark experiment complete with aggregate results.

        Parameters
        ----------
        experiment_id:
            The experiment to complete.
        results:
            Aggregate results dict (e.g. ``{"brier_score": 0.12, ...}``).
        """
        record = self._get_experiment(experiment_id)
        record.status = "completed"
        record.results = results
        record.completed_at = datetime.now(timezone.utc).isoformat()
        self._save()

        logger.info(
            "Experiment '%s' (id=%s) completed with %d forecasts.",
            record.name,
            experiment_id,
            len(record.forecasts),
        )

    def fail_experiment(
        self,
        experiment_id: str,
        error: str,
    ) -> None:
        """Mark experiment as failed.

        Parameters
        ----------
        experiment_id:
            The experiment that failed.
        error:
            Error description.
        """
        record = self._get_experiment(experiment_id)
        record.status = "failed"
        record.completed_at = datetime.now(timezone.utc).isoformat()
        record.metadata["error"] = error
        self._save()

        logger.error(
            "Experiment '%s' (id=%s) failed: %s",
            record.name,
            experiment_id,
            error,
        )

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_experiment(self, experiment_id: str) -> ExperimentRecord:
        """Retrieve experiment details.

        Parameters
        ----------
        experiment_id:
            The experiment to retrieve.

        Returns
        -------
        ExperimentRecord

        Raises
        ------
        KeyError
            If experiment_id is not found.
        """
        return self._get_experiment(experiment_id)

    def list_experiments(
        self,
        experiment_type: str | None = None,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[ExperimentRecord]:
        """List all experiments, optionally filtered.

        Parameters
        ----------
        experiment_type:
            Filter by type (e.g. ``"ablation"``).
        status:
            Filter by status (e.g. ``"completed"``).
        limit:
            Maximum number of results (most recent first).

        Returns
        -------
        list[ExperimentRecord]
        """
        records = list(self._experiments.values())

        if experiment_type is not None:
            records = [
                r for r in records if r.experiment_type == experiment_type
            ]

        if status is not None:
            records = [r for r in records if r.status == status]

        # Sort by start time descending.
        records.sort(key=lambda r: r.started_at, reverse=True)

        if limit is not None:
            records = records[:limit]

        return records

    def compare_experiments(
        self,
        experiment_ids: list[str],
    ) -> ComparisonResult:
        """Compare multiple experiment runs side-by-side.

        Parameters
        ----------
        experiment_ids:
            List of experiment IDs to compare.

        Returns
        -------
        ComparisonResult
        """
        records = [self._get_experiment(eid) for eid in experiment_ids]

        # Build metrics table.
        metrics_table: list[dict[str, Any]] = []
        all_metric_keys: set[str] = set()

        for record in records:
            row: dict[str, Any] = {
                "experiment_id": record.experiment_id,
                "name": record.name,
                "type": record.experiment_type,
                "status": record.status,
                "n_forecasts": len(record.forecasts),
            }

            # Include aggregate results.
            for key, value in record.results.items():
                if isinstance(value, (int, float)):
                    row[key] = value
                    all_metric_keys.add(key)

            # Compute cost from logged forecasts.
            costs = [
                f.cost for f in record.forecasts if f.cost is not None
            ]
            if costs:
                row["total_cost"] = sum(costs)
                row["avg_cost"] = sum(costs) / len(costs)
                all_metric_keys.update(["total_cost", "avg_cost"])

            # Compute accuracy from logged forecasts with actuals.
            scored = [
                f for f in record.forecasts if f.actual is not None
            ]
            if scored:
                binary = [
                    f for f in scored if f.target_type == "binary"
                ]
                if binary:
                    brier = sum(
                        (f.prediction - f.actual) ** 2 for f in binary
                    ) / len(binary)
                    row["computed_brier"] = round(brier, 6)
                    all_metric_keys.add("computed_brier")

                continuous = [
                    f for f in scored if f.target_type == "continuous"
                ]
                if continuous:
                    mae = sum(
                        abs(f.prediction - f.actual) for f in continuous
                    ) / len(continuous)
                    row["computed_mae"] = round(mae, 6)
                    all_metric_keys.add("computed_mae")

            metrics_table.append(row)

        # Find best experiment per metric (lower is better for all).
        best_by_metric: dict[str, str] = {}
        for metric in all_metric_keys:
            candidates = [
                (row["experiment_id"], row[metric])
                for row in metrics_table
                if metric in row and isinstance(row[metric], (int, float))
            ]
            if candidates:
                best = min(candidates, key=lambda x: x[1])
                best_by_metric[metric] = best[0]

        # Summary.
        lines = [f"Experiment Comparison ({len(records)} experiments):"]
        for row in metrics_table:
            line = f"  {row['name']} (id={row['experiment_id'][:8]}...): "
            parts: list[str] = []
            for key in sorted(all_metric_keys):
                if key in row:
                    val = row[key]
                    if isinstance(val, float):
                        parts.append(f"{key}={val:.4f}")
                    else:
                        parts.append(f"{key}={val}")
            line += ", ".join(parts)
            lines.append(line)

        if best_by_metric:
            lines.append("  Best by metric:")
            for metric, eid in best_by_metric.items():
                name = next(
                    (r.name for r in records if r.experiment_id == eid),
                    eid[:8],
                )
                lines.append(f"    {metric}: {name}")

        # Chart data.
        chart_data: dict[str, Any] = {
            "labels": [r.name for r in records],
            "metrics": {},
        }
        for metric in all_metric_keys:
            chart_data["metrics"][metric] = [
                row.get(metric) for row in metrics_table
            ]

        return ComparisonResult(
            experiment_ids=experiment_ids,
            metrics_table=metrics_table,
            best_by_metric=best_by_metric,
            summary="\n".join(lines),
            chart_data=chart_data,
        )

    def get_best_config(
        self,
        metric: str = "brier_score",
        n: int = 5,
        experiment_type: str | None = None,
    ) -> list[ExperimentRecord]:
        """Get top N experiments by a metric (lower is better).

        Parameters
        ----------
        metric:
            Result metric to rank by (e.g. ``"brier_score"``,
            ``"crps"``, ``"mae"``).
        n:
            Number of top experiments to return.
        experiment_type:
            Optional filter by experiment type.

        Returns
        -------
        list[ExperimentRecord]
            Top N experiments sorted by the given metric (ascending).
        """
        candidates = self.list_experiments(
            experiment_type=experiment_type,
            status="completed",
        )

        # Filter to those with the requested metric in results.
        scored: list[tuple[float, ExperimentRecord]] = []
        for record in candidates:
            value = record.results.get(metric)
            if isinstance(value, (int, float)):
                scored.append((float(value), record))

        # Also try computing from logged forecasts if metric is
        # "brier_score" and not in results.
        if not scored and metric == "brier_score":
            for record in candidates:
                binary = [
                    f
                    for f in record.forecasts
                    if f.actual is not None and f.target_type == "binary"
                ]
                if binary:
                    brier = sum(
                        (f.prediction - f.actual) ** 2 for f in binary
                    ) / len(binary)
                    scored.append((brier, record))

        scored.sort(key=lambda x: x[0])
        return [record for _, record in scored[:n]]

    # ------------------------------------------------------------------
    # Bulk operations
    # ------------------------------------------------------------------

    def delete_experiment(self, experiment_id: str) -> None:
        """Delete an experiment record.

        Parameters
        ----------
        experiment_id:
            The experiment to delete.
        """
        if experiment_id not in self._experiments:
            raise KeyError(f"Experiment {experiment_id} not found.")
        del self._experiments[experiment_id]
        self._save()

    def export_all(self) -> list[dict[str, Any]]:
        """Export all experiments as JSON-serializable dicts.

        Returns
        -------
        list[dict[str, Any]]
        """
        return [
            self._record_to_dict(record)
            for record in self._experiments.values()
        ]

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _save(self) -> None:
        """Persist experiments to JSON file if path is configured."""
        if self._persist_path is None:
            return

        try:
            self._persist_path.parent.mkdir(parents=True, exist_ok=True)
            data = self.export_all()
            with open(self._persist_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as exc:
            logger.warning("Failed to persist experiments: %s", exc)

    def _load(self) -> None:
        """Load experiments from JSON file."""
        if self._persist_path is None or not self._persist_path.exists():
            return

        try:
            with open(self._persist_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            for item in data:
                forecasts = [
                    ForecastLog(**fl) for fl in item.get("forecasts", [])
                ]
                record = ExperimentRecord(
                    experiment_id=item["experiment_id"],
                    name=item["name"],
                    experiment_type=item["experiment_type"],
                    config=item["config"],
                    status=item.get("status", "completed"),
                    forecasts=forecasts,
                    results=item.get("results", {}),
                    started_at=item.get(
                        "started_at",
                        datetime.now(timezone.utc).isoformat(),
                    ),
                    completed_at=item.get("completed_at"),
                    metadata=item.get("metadata", {}),
                )
                self._experiments[record.experiment_id] = record

            logger.info(
                "Loaded %d experiments from %s.",
                len(self._experiments),
                self._persist_path,
            )
        except Exception as exc:
            logger.warning("Failed to load experiments: %s", exc)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_experiment(self, experiment_id: str) -> ExperimentRecord:
        """Look up an experiment by ID, raising KeyError if missing."""
        if experiment_id not in self._experiments:
            raise KeyError(
                f"Experiment '{experiment_id}' not found. "
                f"Available: {list(self._experiments.keys())[:5]}"
            )
        return self._experiments[experiment_id]

    @staticmethod
    def _record_to_dict(record: ExperimentRecord) -> dict[str, Any]:
        """Convert an ExperimentRecord to a JSON-serializable dict."""
        return {
            "experiment_id": record.experiment_id,
            "name": record.name,
            "experiment_type": record.experiment_type,
            "config": record.config,
            "status": record.status,
            "forecasts": [
                {
                    "question_id": f.question_id,
                    "prediction": f.prediction,
                    "actual": f.actual,
                    "cost": f.cost,
                    "target_type": f.target_type,
                    "domain": f.domain,
                    "timestamp": f.timestamp,
                    "metadata": f.metadata,
                }
                for f in record.forecasts
            ],
            "results": record.results,
            "started_at": record.started_at,
            "completed_at": record.completed_at,
            "metadata": record.metadata,
        }
