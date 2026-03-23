"""Central API router that aggregates all sub-routers."""

from fastapi import APIRouter

from app.api.questions import router as questions_router
from app.api.scenarios import router as scenarios_router
from app.api.forecasts import router as forecasts_router
from app.api.evidence import router as evidence_router
from app.api.base_rates import router as base_rates_router
from app.api.backtests import router as backtests_router
from app.api.calibration import router as calibration_router
from app.api.resolutions import router as resolutions_router
from app.api.experiments import router as experiments_router
from app.api.benchmarks import router as benchmarks_router
from app.api.costs import router as costs_router
from app.api.evaluations import router as evaluations_router

api_router = APIRouter()

api_router.include_router(questions_router, prefix="/questions", tags=["questions"])
api_router.include_router(scenarios_router, prefix="/scenarios", tags=["scenarios"])
api_router.include_router(forecasts_router, prefix="/forecasts", tags=["forecasts"])
api_router.include_router(evidence_router, prefix="/evidence", tags=["evidence"])
api_router.include_router(base_rates_router, prefix="/base-rates", tags=["base-rates"])
api_router.include_router(backtests_router, prefix="/backtests", tags=["backtests"])
api_router.include_router(calibration_router, prefix="/calibration", tags=["calibration"])
api_router.include_router(resolutions_router, prefix="/resolutions", tags=["resolutions"])
api_router.include_router(experiments_router, prefix="/experiments", tags=["experiments"])
api_router.include_router(benchmarks_router, prefix="/benchmarks", tags=["benchmarks"])
api_router.include_router(costs_router, prefix="/costs", tags=["costs"])
api_router.include_router(evaluations_router, prefix="/eval", tags=["evaluations"])
