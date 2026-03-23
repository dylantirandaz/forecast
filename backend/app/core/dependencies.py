"""FastAPI dependency injection for core forecasting services.

Each ``get_*`` function is designed to be used with ``Depends()`` in
FastAPI route handlers.  Services are instantiated per-request so they
carry no mutable shared state.  If caching or connection pooling is
needed, the service constructors themselves handle it.
"""

from __future__ import annotations

from functools import lru_cache

from app.services.backtester import Backtester
from app.services.belief_updater import BeliefUpdater
from app.services.calibration import CalibrationEngine
from app.services.evidence_scorer import EvidenceScorer
from app.services.forecast_engine import ForecastEngine


@lru_cache
def get_forecast_engine() -> ForecastEngine:
    """Return a cached ForecastEngine instance."""
    return ForecastEngine()


@lru_cache
def get_evidence_scorer() -> EvidenceScorer:
    """Return a cached EvidenceScorer instance."""
    return EvidenceScorer()


@lru_cache
def get_belief_updater() -> BeliefUpdater:
    """Return a cached BeliefUpdater instance."""
    return BeliefUpdater()


@lru_cache
def get_calibration_engine() -> CalibrationEngine:
    """Return a cached CalibrationEngine instance."""
    return CalibrationEngine()


@lru_cache
def get_backtester() -> Backtester:
    """Return a cached Backtester instance."""
    return Backtester()
