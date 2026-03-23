# NYC Housing Forecasting System -- Architecture

## System Overview

The NYC Housing Forecasting system is a Bayesian forecasting platform that
generates calibrated probabilistic predictions for New York City housing
policy outcomes. It combines historical base rates, structured evidence
scoring, and Bayesian belief updating to produce forecasts that are
continuously evaluated and recalibrated.

```
                          +-------------------+
                          |   Next.js Front   |
                          |   End (port 3000) |
                          +--------+----------+
                                   |
                                   | REST / JSON
                                   v
                          +--------+----------+
                          |  FastAPI Backend   |
                          |   (port 8000)     |
                          +--+-----+------+---+
                             |     |      |
              +--------------+     |      +--------------+
              |                    |                      |
              v                    v                      v
     +--------+------+   +--------+------+   +-----------+----+
     |  PostgreSQL   |   |    Redis      |   |  Celery Worker |
     |  (port 5432)  |   |  (port 6379)  |   |  (background)  |
     +---------------+   +---------------+   +----------------+
                                                     |
                                              +------+------+
                                              |  Data       |
                                              |  Adapters   |
                                              +------+------+
                                                     |
                                    +----------------+----------------+
                                    |                |                |
                              Census / HVS     RGB Orders     DOB Permits
                              (external)       (external)     (external)
```

## Component Descriptions

### Frontend (Next.js)

- **Technology**: Next.js 14, React 18, TypeScript, Tailwind CSS, Recharts
- **Responsibilities**: Dashboard display, question management, forecast
  visualisation, scenario comparison, calibration charts.
- **Communication**: Consumes the REST API at `/api/v1/*` via Axios / React
  Query.

### Backend (FastAPI)

- **Technology**: FastAPI, SQLAlchemy (async), Pydantic v2, structlog
- **Responsibilities**: REST API, business logic orchestration, dependency
  injection, authentication.
- **Key packages**:
  - `app.api` -- route handlers organised by domain (questions, forecasts,
    evidence, scenarios, base rates, backtests, calibration, resolutions).
  - `app.services` -- core analytical engines (see below).
  - `app.models` -- SQLAlchemy ORM models.
  - `app.schemas` -- Pydantic request / response schemas.
  - `app.adapters` -- data ingestion adapters for external sources.
  - `app.core` -- cross-cutting concerns (logging, dependency injection).
  - `app.tasks` -- Celery task definitions.

### PostgreSQL

- Primary relational store for questions, forecasts, evidence, resolutions,
  calibration data, and backtest results.
- Schema managed via Alembic migrations.

### Redis

- Celery message broker and result backend.
- Optional caching layer for expensive query results.

### Celery Workers

- Execute long-running tasks asynchronously: forecast generation, backtest
  runs, data ingestion, and base-rate computation.
- Task queues: `forecasts`, `backtests`, `ingestion`, `default`.

### Data Adapters

- Pluggable adapter classes inheriting from `DataAdapter` (fetch, validate,
  transform, ingest).
- Sources include Census Housing Vacancy Survey (HVS), NYCHVS, Rent
  Guidelines Board (RGB) orders, DOB building permits, and others.

## Data Flow

```
 External Data Sources
        |
        v
 1. INGESTION -----> Data Adapters fetch, validate, transform raw data
        |
        v
 2. BASE RATES ----> BaseRateEngine computes historical distributions & trends
        |
        v
 3. EVIDENCE ------> EvidenceScorer evaluates new evidence items
        |             (relevance, reliability, directional effect)
        v
 4. FORECASTS -----> BeliefUpdater applies Bayesian updates to the prior
        |             ForecastEngine orchestrates the full pipeline
        |             ScenarioEngine conditions on policy assumptions
        v
 5. RESOLUTION ----> ResolutionEngine records actual outcomes, computes
        |             Brier scores and log scores
        v
 6. CALIBRATION ---> CalibrationEngine measures forecast-vs-outcome
                      alignment, detects systematic biases, generates
                      recalibration curves
```

## Forecasting Methodology

### Base Rates

The starting point for every forecast is a base-rate prior derived from
historical data. The `BaseRateEngine`:

- Computes distribution statistics (mean, median, percentiles, standard
  deviation) from chronologically ordered time-series data.
- Extracts polynomial trends (linear by default) and reports annualised
  change and R-squared.
- Optionally incorporates analog priors from weighted historical situations
  that resemble the current question.

### Evidence Scoring

Each piece of new evidence (policy announcements, economic indicators,
court rulings, etc.) is scored along three dimensions:

- **Relevance** (0--1): How directly the evidence bears on the question.
- **Reliability** (0--1): Source credibility and methodological rigour.
- **Directional effect**: Whether the evidence pushes the probability up,
  down, or is neutral, and by how much.

### Belief Updating

The `BeliefUpdater` applies a Bayesian update rule:

1. Start with the prior probability (from base rates or the most recent
   forecast).
2. For each scored evidence item compute a likelihood ratio.
3. Apply Bayes' theorem to obtain the posterior.
4. Clip extreme values to maintain calibration (no probability below 0.02
   or above 0.98).

### Scenario Analysis

The `ScenarioEngine` lets users define alternative policy scenarios (e.g.
"RGB approves 5% increase" vs. "RGB freezes rents") with varying intensity
levels.  Forecasts are generated independently for each scenario and can be
compared side-by-side.

### Calibration

The `CalibrationEngine` evaluates long-run forecast accuracy:

- Groups resolved forecasts into probability bins and compares predicted
  vs. observed frequencies.
- Computes Brier scores, log scores, and calibration error metrics.
- Detects systematic over- or under-confidence.
- Generates recalibration mappings to correct identified biases.

### Backtesting

The `Backtester` replays the forecasting pipeline on historical periods
where outcomes are known, measuring how accurately the system would have
performed.

## API Overview

All endpoints are served under `/api/v1`.

| Resource       | Prefix           | Key operations                        |
|----------------|------------------|---------------------------------------|
| Questions      | `/questions`     | CRUD, status transitions              |
| Scenarios      | `/scenarios`     | CRUD, attach to questions             |
| Forecasts      | `/forecasts`     | Generate, list history, compare       |
| Evidence       | `/evidence`      | Add items, score, list by question    |
| Base Rates     | `/base-rates`    | Compute, retrieve by metric           |
| Backtests      | `/backtests`     | Configure, run, retrieve results      |
| Calibration    | `/calibration`   | Compute scores, view calibration plot |
| Resolutions    | `/resolutions`   | Record outcomes, compute scores       |

| Experiments    | `/experiments`   | Ablation, benchmark, comparison runs  |
| Benchmarks     | `/benchmarks`    | Submit, score, export payloads        |
| Cost           | `/cost`          | Query cost logs, budget summaries     |
| Calibration    | `/calibration`   | Run calibration studies, view curves  |

Health check is available at `GET /health`.

## Database Schema Overview

The database contains the following primary tables (managed via SQLAlchemy
ORM models and Alembic migrations):

- **forecasting_questions** -- The questions being forecast (e.g. "Will
  median stabilised rent exceed $1,600 by 2026?"). Tracks status, target
  type, resolution date.
- **scenarios** -- Alternative policy assumptions attached to questions,
  with intensity levels.
- **targets** -- Measurable metrics (rent levels, vacancy rates, permit
  counts) with category and frequency metadata.
- **forecast_runs** / **forecast_updates** -- Each forecast generation
  produces a run; individual probability updates within a run are tracked.
- **evidence_items** / **evidence_scores** -- Pieces of evidence and their
  scored relevance, reliability, and directional effect.
- **base_rates** -- Cached base-rate priors per metric and geography.
- **resolutions** / **scores** -- Actual outcomes and scoring (Brier, log
  score) against forecasts.
- **backtest_runs** / **backtest_forecasts** -- Configuration and results
  of historical backtesting runs.
- **model_versions** -- Tracks which model version produced each forecast.
- **policy_events** -- Significant policy events (legislation, court
  rulings, RGB decisions) that may affect forecasts.
- **source_documents** -- Reference documents backing evidence items.
- **experiment_runs** -- Ablation, benchmark, calibration-study, and
  model-comparison experiments with config, results, and cost tracking.
- **benchmark_submissions** -- Payloads submitted to external benchmarks
  (ForecastBench, Metaculus) with scores and status.
- **cost_logs** -- Per-operation cost and token usage records for every LLM
  call, forecast run, evidence scoring pass, and data ingestion job.
- **calibration_runs** -- Structured calibration study results including
  pre/post Brier scores, calibration parameters, and bucket data.

## Benchmark Harness

The benchmark harness allows the system to participate in public
forecasting competitions and to evaluate its own accuracy against
established question sets.

```
  Question Set (ForecastBench / Metaculus / internal)
        |
        v
  BenchmarkRunner  -----> generates forecasts for each question
        |                  using the full pipeline
        v
  ExperimentRun record  -- stores config, ablation flags, results
        |
        v
  BenchmarkExporter -----> formats submission_payload (JSON / CSV)
        |
        v
  BenchmarkSubmission  --- tracks status (draft -> submitted -> scored)
```

Supported benchmarks:

- **ForecastBench** -- Open research benchmark with binary and continuous
  questions. Export produces a JSON payload matching the ForecastBench
  submission schema.
- **Metaculus** -- Community forecasting platform. Export produces
  predictions compatible with the Metaculus API.
- **Internal** -- Custom question sets for regression testing and
  continuous integration.

## Ablation Framework

Ablation experiments systematically disable individual components of the
forecasting pipeline to measure each component's marginal contribution to
accuracy.

The 10 standard ablation experiments:

| #  | Experiment                   | What is disabled                                   |
|----|------------------------------|----------------------------------------------------|
| 1  | `no_evidence_scoring`        | Skip evidence scoring; use raw evidence only       |
| 2  | `no_bayesian_update`         | Skip Bayesian belief updating; return base rate     |
| 3  | `no_base_rate`               | Remove base-rate prior; start from uniform prior   |
| 4  | `no_scenario_conditioning`   | Ignore scenario assumptions                        |
| 5  | `no_recency_weighting`       | Disable recency decay in evidence scoring          |
| 6  | `no_source_credibility`      | Treat all sources as equally credible              |
| 7  | `no_redundancy_detection`    | Disable redundancy discount for correlated evidence|
| 8  | `no_calibration_adjustment`  | Skip post-hoc calibration correction               |
| 9  | `no_ensemble`                | Use single model instead of ensemble               |
| 10 | `no_llm_reasoning`           | Remove LLM-generated rationales and chain-of-thought|

Each ablation run produces an `experiment_runs` record with
`experiment_type = 'ablation'` and an `ablation_flags` JSONB field that
records which flags were toggled.

## Cost-Aware Orchestration

The system tracks and optimises the cost of every LLM interaction and
analytical operation.

### Tier Routing

Models are assigned to one of three cost tiers:

- **Tier 1 (cheap)** -- Small / fast models used for evidence triage,
  simple classification, and formatting tasks.
- **Tier 2 (standard)** -- Mid-range models for evidence scoring,
  base-rate analysis, and routine forecasting.
- **Tier 3 (premium)** -- Frontier models reserved for high-stakes
  forecasts, disagreement resolution, and calibration studies.

The `CostRouter` selects the cheapest tier that meets the quality
threshold for a given operation, based on historical accuracy at each
tier.

### Value-of-Information (VoI) Gating

Before executing an expensive operation (e.g. a Tier-3 LLM call or a
full evidence-scoring pass), the system estimates the expected value of
the information gained relative to its cost. If the VoI is below a
configurable threshold, the operation is skipped or downgraded to a
cheaper tier.

### Disagreement Passes

When multiple models in the ensemble disagree beyond a configurable
threshold, a targeted "disagreement pass" is triggered using a
higher-tier model to arbitrate. This avoids paying premium-tier prices
for every question while still catching cases where cheap models diverge.

### Cost Logging

Every operation writes a row to `cost_logs` recording:

- Operation type and reference (which forecast run, experiment, etc.)
- Model tier and model name
- Input / output token counts
- USD cost and latency

Cost dashboards aggregate these records by time period, operation type,
and model tier.

## Experiment Tracking

All experiment types (ablation, benchmark, calibration study, model
comparison) share the `experiment_runs` table. Each run stores:

- Full configuration snapshot (`config` JSONB)
- Ablation flags where applicable
- Aggregate results (mean Brier score, mean log score, total questions)
- Total cost in USD
- Timing (started_at, completed_at)

Results can be compared across runs using the `/experiments/compare`
endpoint, which returns side-by-side score and cost breakdowns.

## Benchmark Export Layer

The `BenchmarkExporter` converts internal forecast data into
submission-ready payloads:

1. **Question mapping** -- Maps internal question IDs to benchmark
   question identifiers.
2. **Format conversion** -- Translates probability distributions into
   the target format (point estimates, CDF bins, or quantiles).
3. **Validation** -- Checks that all required questions are covered and
   probabilities are well-formed.
4. **Payload assembly** -- Produces the final JSON / CSV payload stored
   in `benchmark_submissions.submission_payload`.

## Updated System Diagram

```
                          +-------------------+
                          |   Next.js Front   |
                          |   End (port 3000) |
                          +--------+----------+
                                   |
                                   | REST / JSON
                                   v
                          +--------+----------+
                          |  FastAPI Backend   |
                          |   (port 8000)     |
                          +--+--+--+--+---+---+
                             |  |  |  |   |
              +--------------+  |  |  |   +------------------+
              |                 |  |  |                      |
              v                 |  |  v                      v
     +--------+------+         |  | +------------+  +-------+--------+
     |  PostgreSQL   |         |  | | Cost Router|  | Celery Worker  |
     |  (port 5432)  |         |  | +-----+------+  |  (background)  |
     +---------------+         |  |       |          +--+----+--------+
                               |  |       v             |    |
                               |  |  +----+------+      |    |
                               v  |  | LLM Tiers |      |    |
                         +-----+--++ | T1/T2/T3  |      |    |
                         |  Redis  | +----+------+      |    |
                         |(6379)   |      |             |    |
                         +---------+      v             |    |
                                   +------+------+     |    |
                                   | Experiment  |<----+    |
                                   | Runner      |         |
                                   +--+---+------+         |
                                      |   |                |
                              +-------+   +--------+       |
                              v                    v       v
                     +--------+------+    +--------+------++
                     | Benchmark     |    | Data Adapters  |
                     | Exporter      |    +--------+-------+
                     +--------+------+             |
                              |        +-----------+----------+
                              v        |           |          |
                     ForecastBench  Census/HVS  RGB Orders  DOB
                     Metaculus     (external)   (external) (external)
```
