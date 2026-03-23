"""Forecasting engine services for the NYC Housing Forecasting system.

This package contains the core analytical services that power the
Bayesian-updating forecast pipeline: base-rate estimation, evidence
scoring, belief updating, scenario analysis, calibration, resolution
tracking, backtesting, cost-aware orchestration, tiered model routing,
benchmarking, ablation testing, experiment tracking, replay evaluation,
comprehensive metrics, and baseline predictors.
"""

from .ablation_runner import AblationRunner
from .backtester import Backtester
from .base_rate_engine import BaseRateEngine
from .baseline_predictors import (
    AlwaysHalfPredictor,
    BaseRatePredictor,
    NaiveDirectionalPredictor,
    BASELINE_PREDICTORS,
)
from .benchmark_harness import BenchmarkHarness
from .belief_updater import BeliefUpdater
from .calibration import CalibrationEngine
from .cost_tracker import CostTracker
from .eval_metrics import (
    BaselineComparison,
    EvalMetricsEngine,
    FullEvalReport,
    MetricsSummary,
)
from .evidence_scorer import EvidenceScorer
from .experiment_tracker import ExperimentTracker
from .forecast_engine import ForecastEngine
from .model_router import ModelRouter
from .orchestrator import ForecastOrchestrator
from .question_router import QuestionRouter
from .replay_engine import (
    ReplayConfig,
    ReplayPrediction,
    ReplayResult,
    ReplayRunner,
)
from .resolution_engine import ResolutionEngine
from .scenario_engine import ScenarioEngine

__all__ = [
    "AblationRunner",
    "AlwaysHalfPredictor",
    "BASELINE_PREDICTORS",
    "BaseRateEngine",
    "BaseRatePredictor",
    "BaselineComparison",
    "BenchmarkHarness",
    "EvalMetricsEngine",
    "EvidenceScorer",
    "BeliefUpdater",
    "ExperimentTracker",
    "ForecastEngine",
    "FullEvalReport",
    "MetricsSummary",
    "NaiveDirectionalPredictor",
    "ReplayConfig",
    "ReplayPrediction",
    "ReplayResult",
    "ReplayRunner",
    "ScenarioEngine",
    "CalibrationEngine",
    "ResolutionEngine",
    "Backtester",
    "CostTracker",
    "ModelRouter",
    "ForecastOrchestrator",
    "QuestionRouter",
]
