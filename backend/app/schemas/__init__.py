"""Pydantic v2 schemas for the NYC Housing Forecasting system."""

from .backtest import BacktestCreate, BacktestResponse, BacktestResultSummary
from .base_rate import BaseRateCompute, BaseRateResponse
from .benchmark import (
    BenchmarkExportPayload,
    BenchmarkStatus,
    BenchmarkSubmissionCreate,
    BenchmarkSubmissionResponse,
)
from .calibration import (
    CalibrationBucket,
    CalibrationMethod,
    CalibrationMetrics,
    CalibrationRunCreate,
    CalibrationRunResponse,
    CalibrationScope,
)
from .common import ErrorResponse, HealthResponse, PaginatedResponse
from .cost import (
    CostLogCreate,
    CostLogResponse,
    CostPerformanceTradeoff,
    CostSummary,
    OperationType,
)
from .evidence import (
    DirectionalEffect,
    EvidenceCreate,
    EvidenceResponse,
    EvidenceScoreCreate,
    EvidenceScoreResponse,
    SourceType,
)
from .experiment import (
    AblationFlags,
    ExperimentComparisonResponse,
    ExperimentCreate,
    ExperimentResponse,
    ExperimentStatus,
    ExperimentType,
)
from .forecast import (
    ForecastHistory,
    ForecastRunCreate,
    ForecastRunResponse,
    ForecastUpdateCreate,
    ForecastUpdateResponse,
)
from .question import (
    QuestionCreate,
    QuestionList,
    QuestionResponse,
    QuestionStatus,
    QuestionUpdate,
    TargetType,
)
from .resolution import ResolutionCreate, ResolutionResponse, ScoreResponse
from .scenario import ScenarioCreate, ScenarioIntensity, ScenarioResponse, ScenarioUpdate
from .scenario_comparison import (
    ScenarioComparisonRequest,
    ScenarioComparisonResponse,
    ScenarioForecastSummary,
)

__all__ = [
    # Common
    "ErrorResponse",
    "HealthResponse",
    "PaginatedResponse",
    # Question
    "QuestionCreate",
    "QuestionList",
    "QuestionResponse",
    "QuestionStatus",
    "QuestionUpdate",
    "TargetType",
    # Scenario
    "ScenarioCreate",
    "ScenarioIntensity",
    "ScenarioResponse",
    "ScenarioUpdate",
    # Forecast
    "ForecastHistory",
    "ForecastRunCreate",
    "ForecastRunResponse",
    "ForecastUpdateCreate",
    "ForecastUpdateResponse",
    # Evidence
    "DirectionalEffect",
    "EvidenceCreate",
    "EvidenceResponse",
    "EvidenceScoreCreate",
    "EvidenceScoreResponse",
    "SourceType",
    # Base Rate
    "BaseRateCompute",
    "BaseRateResponse",
    # Backtest
    "BacktestCreate",
    "BacktestResponse",
    "BacktestResultSummary",
    # Resolution
    "ResolutionCreate",
    "ResolutionResponse",
    "ScoreResponse",
    # Calibration
    "CalibrationBucket",
    "CalibrationMethod",
    "CalibrationMetrics",
    "CalibrationRunCreate",
    "CalibrationRunResponse",
    "CalibrationScope",
    # Scenario Comparison
    "ScenarioComparisonRequest",
    "ScenarioComparisonResponse",
    "ScenarioForecastSummary",
    # Experiment
    "AblationFlags",
    "ExperimentComparisonResponse",
    "ExperimentCreate",
    "ExperimentResponse",
    "ExperimentStatus",
    "ExperimentType",
    # Benchmark
    "BenchmarkExportPayload",
    "BenchmarkStatus",
    "BenchmarkSubmissionCreate",
    "BenchmarkSubmissionResponse",
    # Cost
    "CostLogCreate",
    "CostLogResponse",
    "CostPerformanceTradeoff",
    "CostSummary",
    "OperationType",
]
