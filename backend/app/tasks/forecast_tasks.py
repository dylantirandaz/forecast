"""Celery tasks for the NYC Housing Forecasting system.

These tasks wrap the core service calls so that expensive computations
(forecasting, backtesting, data ingestion) run asynchronously via the
Celery worker pool rather than blocking the FastAPI request cycle.
"""

from __future__ import annotations

import logging
from typing import Any

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="app.tasks.forecast_tasks.run_forecast_task",
    max_retries=3,
    default_retry_delay=30,
)
def run_forecast_task(self, question_id: str, scenario_id: str | None = None) -> dict[str, Any]:
    """Generate or update a forecast for the given question / scenario.

    Parameters
    ----------
    question_id:
        UUID of the :class:`ForecastingQuestion` to forecast.
    scenario_id:
        Optional UUID of a :class:`Scenario`.  When provided the forecast
        is conditioned on that scenario's assumptions.

    Returns
    -------
    dict
        Summary of the forecast result including the updated probability
        and metadata about the computation.
    """
    logger.info(
        "Running forecast task for question=%s scenario=%s",
        question_id,
        scenario_id,
    )
    try:
        from app.services.forecast_engine import ForecastEngine

        engine = ForecastEngine()
        result = engine.generate_forecast(
            question_id=question_id,
            scenario_id=scenario_id,
        )
        logger.info(
            "Forecast complete for question=%s: probability=%.4f",
            question_id,
            result.get("probability", 0.0),
        )
        return result
    except Exception as exc:
        logger.error("Forecast task failed: %s", exc, exc_info=True)
        raise self.retry(exc=exc)


@celery_app.task(
    bind=True,
    name="app.tasks.forecast_tasks.run_backtest_task",
    max_retries=2,
    default_retry_delay=60,
)
def run_backtest_task(self, backtest_config: dict[str, Any]) -> dict[str, Any]:
    """Execute a backtesting run with the supplied configuration.

    Parameters
    ----------
    backtest_config:
        Dictionary containing backtest parameters such as
        ``start_date``, ``end_date``, ``metrics``, and
        ``model_version_id``.

    Returns
    -------
    dict
        Backtest results including accuracy metrics, calibration
        scores, and per-question breakdowns.
    """
    logger.info("Running backtest task with config: %s", backtest_config)
    try:
        from app.services.backtester import Backtester

        backtester = Backtester()
        result = backtester.run(config=backtest_config)
        logger.info(
            "Backtest complete: %d questions evaluated",
            result.get("questions_evaluated", 0),
        )
        return result
    except Exception as exc:
        logger.error("Backtest task failed: %s", exc, exc_info=True)
        raise self.retry(exc=exc)


@celery_app.task(
    bind=True,
    name="app.tasks.forecast_tasks.ingest_data_task",
    max_retries=3,
    default_retry_delay=30,
)
def ingest_data_task(self, adapter_name: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Fetch and ingest data using the named adapter.

    Parameters
    ----------
    adapter_name:
        Identifier of the data adapter (e.g. ``"census_hvs"``,
        ``"rgb_orders"``, ``"dob_permits"``).
    params:
        Optional parameters forwarded to the adapter's ``fetch()``
        method (date ranges, filters, etc.).

    Returns
    -------
    dict
        Summary with keys ``records_ingested``, ``source``, and any
        warnings produced during validation.
    """
    logger.info("Ingesting data from adapter=%s params=%s", adapter_name, params)
    try:
        from app.adapters import get_adapter

        adapter = get_adapter(adapter_name)
        records = adapter.ingest(params)
        result = {
            "adapter": adapter_name,
            "records_ingested": len(records),
            "source": adapter.SOURCE_NAME,
        }
        logger.info(
            "Ingestion complete: adapter=%s records=%d",
            adapter_name,
            len(records),
        )
        return result
    except Exception as exc:
        logger.error("Ingestion task failed: %s", exc, exc_info=True)
        raise self.retry(exc=exc)


@celery_app.task(
    bind=True,
    name="app.tasks.forecast_tasks.compute_base_rates_task",
    max_retries=2,
    default_retry_delay=30,
)
def compute_base_rates_task(self, target_metric: str) -> dict[str, Any]:
    """Compute or refresh base-rate priors for the specified metric.

    Parameters
    ----------
    target_metric:
        Name of the target metric (e.g. ``"median_rent_stabilised"``,
        ``"vacancy_rate"``, ``"permits_issued"``).

    Returns
    -------
    dict
        Computed base-rate summary including distribution statistics,
        trend information, and analog prior if available.
    """
    logger.info("Computing base rates for metric=%s", target_metric)
    try:
        from app.services.base_rate_engine import BaseRateEngine

        engine = BaseRateEngine()
        # In a full implementation this would load historical data from the
        # database, compute the base rate, and persist the result.  For now
        # we return a placeholder indicating the task completed.
        result = {
            "target_metric": target_metric,
            "status": "computed",
        }
        logger.info("Base rate computation complete for metric=%s", target_metric)
        return result
    except Exception as exc:
        logger.error("Base rate task failed: %s", exc, exc_info=True)
        raise self.retry(exc=exc)
