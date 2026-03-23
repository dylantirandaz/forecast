"""Celery application configuration for the NYC Housing Forecasting system.

The broker and result backend both default to the Redis instance defined
in ``app.config.Settings.REDIS_URL``.
"""

from __future__ import annotations

from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "forecast_tasks",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    # ── Serialisation ─────────────────────────────────────────────────
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # ── Time limits ───────────────────────────────────────────────────
    task_soft_time_limit=300,   # 5 minutes soft limit
    task_time_limit=600,        # 10 minutes hard limit

    # ── Result expiry ─────────────────────────────────────────────────
    result_expires=3600,        # 1 hour

    # ── Reliability ───────────────────────────────────────────────────
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,

    # ── Routing ───────────────────────────────────────────────────────
    task_default_queue="default",
    task_routes={
        "app.tasks.forecast_tasks.run_forecast_task": {"queue": "forecasts"},
        "app.tasks.forecast_tasks.run_backtest_task": {"queue": "backtests"},
        "app.tasks.forecast_tasks.ingest_data_task": {"queue": "ingestion"},
        "app.tasks.forecast_tasks.compute_base_rates_task": {"queue": "default"},
    },

    # ── Timezone ──────────────────────────────────────────────────────
    timezone="America/New_York",
    enable_utc=True,
)

# Auto-discover tasks in the app.tasks package
celery_app.autodiscover_tasks(["app.tasks"])
