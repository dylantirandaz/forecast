# Benchmark Evaluation Guide

## Overview

The benchmark system lets you evaluate the NYC Housing Forecasting
system against established forecasting competitions and internal
question sets. It handles question import, forecast generation, payload
export, submission tracking, and score recording.

All benchmark activity is tracked in two tables:

- **experiment_runs** -- The experiment that generated the forecasts
  (type `benchmark`).
- **benchmark_submissions** -- The exported payload, submission status,
  and returned scores.

## Supported Benchmarks

### ForecastBench

ForecastBench is an open research benchmark for evaluating automated
forecasting systems on binary and continuous questions across multiple
domains.

- **Question format**: Binary (yes/no) and continuous (numeric range)
  questions with defined resolution criteria and dates.
- **Submission format**: JSON payload containing question ID, predicted
  probability (binary) or CDF/quantile values (continuous), and
  metadata.
- **Scoring**: Brier score for binary questions; CRPS (Continuous Ranked
  Probability Score) for continuous questions.

### Metaculus

Metaculus is a community forecasting platform with thousands of
questions covering geopolitics, science, technology, and policy.

- **Question format**: Binary, numeric range, and date-range questions.
- **Submission format**: Predictions submitted via the Metaculus API as
  probability values or CDF specifications.
- **Scoring**: Metaculus uses its own scoring system combining
  calibration and resolution metrics. The system maps these back to
  Brier and log scores for internal comparison.

### Internal Question Sets

Custom question sets used for regression testing and continuous
integration. These are stored locally and do not require external
submission.

- **Question format**: Same as the internal `forecasting_questions`
  schema.
- **Scoring**: Brier score, log score, and calibration error computed
  locally against known resolutions.

## How to Run Benchmark Evaluation

### Step 1: Import Questions

Import a benchmark question set:

```bash
python -m app.cli benchmark import \
    --source forecastbench \
    --question-file questions_2026q1.json
```

Or via API:

```bash
curl -X POST http://localhost:8000/api/v1/benchmarks/import \
  -H "Content-Type: application/json" \
  -d '{
    "benchmark_name": "forecastbench",
    "question_file": "questions_2026q1.json"
  }'
```

### Step 2: Run Forecasts

Create a benchmark experiment and generate forecasts for all imported
questions:

```bash
python -m app.cli experiment run-benchmark \
    --name "ForecastBench 2026-Q1" \
    --benchmark forecastbench \
    --model-version latest \
    --cost-budget 5.00
```

Via API:

```bash
curl -X POST http://localhost:8000/api/v1/experiments \
  -H "Content-Type: application/json" \
  -d '{
    "name": "ForecastBench 2026-Q1",
    "experiment_type": "benchmark",
    "config": {
      "benchmark_name": "forecastbench",
      "model_version": "latest",
      "cost_budget_usd": 5.00
    }
  }'
```

### Step 3: Review Results

Check experiment status and results:

```bash
python -m app.cli experiment status {experiment_id}
```

```bash
curl http://localhost:8000/api/v1/experiments/{experiment_id}
```

## How to Export Submission Payloads

Once an experiment run completes, export the submission payload:

```bash
python -m app.cli benchmark export \
    --experiment-id {experiment_id} \
    --format forecastbench \
    --output submission_2026q1.json
```

Via API:

```bash
curl http://localhost:8000/api/v1/benchmarks/export/{experiment_id}?format=forecastbench \
  -o submission_2026q1.json
```

The exporter performs the following steps:

1. Maps internal question IDs to benchmark question identifiers.
2. Converts probability distributions to the target format (point
   estimates for binary; CDF bins or quantiles for continuous).
3. Validates that all required questions are covered and probabilities
   are well-formed.
4. Assembles the final payload and stores it in the
   `benchmark_submissions.submission_payload` column.

## How to Track Submissions and Scores

### Create a Submission Record

```bash
curl -X POST http://localhost:8000/api/v1/benchmarks/submissions \
  -H "Content-Type: application/json" \
  -d '{
    "benchmark_name": "forecastbench",
    "experiment_run_id": "{experiment_id}",
    "model_version_id": "{model_version_id}",
    "notes": "First submission for 2026-Q1 question set"
  }'
```

### Update Status After Submission

```bash
curl -X PATCH http://localhost:8000/api/v1/benchmarks/submissions/{submission_id} \
  -H "Content-Type: application/json" \
  -d '{
    "status": "submitted",
    "submission_date": "2026-03-22T00:00:00Z"
  }'
```

### Record Scores

Once the benchmark platform returns scores:

```bash
curl -X PATCH http://localhost:8000/api/v1/benchmarks/submissions/{submission_id} \
  -H "Content-Type: application/json" \
  -d '{
    "status": "scored",
    "scores": {
      "mean_brier_score": 0.187,
      "mean_log_score": -0.334,
      "n_questions": 150,
      "rank": 12,
      "percentile": 85
    }
  }'
```

### List All Submissions

```bash
curl http://localhost:8000/api/v1/benchmarks/submissions?benchmark_name=forecastbench
```

### Submission Lifecycle

```
  draft  -->  submitted  -->  scored
                  |
                  v
             invalidated
```

- **draft** -- Payload generated but not yet sent to the benchmark
  platform.
- **submitted** -- Payload sent; awaiting scoring.
- **scored** -- Benchmark platform has returned scores.
- **invalidated** -- Submission was disqualified or withdrawn.

## Cost-Performance Optimization

The benchmark system integrates with cost-aware orchestration to help
you find the best accuracy-per-dollar configuration.

### Budget-Constrained Runs

Set a cost budget for benchmark runs. The system will route operations
to cheaper model tiers when the budget is tight:

```bash
python -m app.cli experiment run-benchmark \
    --name "ForecastBench budget run" \
    --benchmark forecastbench \
    --cost-budget 2.00
```

### Tier Comparison

Run the same benchmark at different model tiers to find the
cost-accuracy sweet spot:

```bash
# Tier 1 only (cheapest)
python -m app.cli experiment run-benchmark \
    --name "ForecastBench T1" \
    --benchmark forecastbench \
    --force-tier 1

# Tier 2 only (standard)
python -m app.cli experiment run-benchmark \
    --name "ForecastBench T2" \
    --benchmark forecastbench \
    --force-tier 2

# Tier 3 only (premium)
python -m app.cli experiment run-benchmark \
    --name "ForecastBench T3" \
    --benchmark forecastbench \
    --force-tier 3
```

Then compare:

```bash
python -m app.cli experiment compare \
    --runs {t1_id} {t2_id} {t3_id}
```

### Cost Analysis

View cost breakdown for a benchmark run:

```bash
curl http://localhost:8000/api/v1/cost/summary?reference_id={experiment_id}
```

This returns a breakdown by operation type:

```json
{
  "total_cost_usd": 3.42,
  "breakdown": {
    "llm_call": {"count": 450, "cost_usd": 2.87},
    "evidence_scoring": {"count": 150, "cost_usd": 0.31},
    "base_rate_compute": {"count": 150, "cost_usd": 0.24}
  },
  "by_tier": {
    "tier_1": {"count": 300, "cost_usd": 0.45},
    "tier_2": {"count": 120, "cost_usd": 1.12},
    "tier_3": {"count": 30, "cost_usd": 1.85}
  }
}
```

### Optimization Strategies

1. **Start cheap, escalate selectively.** Use Tier 1 for all questions
   first, then re-run only the questions where confidence is low with
   higher tiers.

2. **Use VoI gating.** Enable value-of-information gating to
   automatically skip expensive operations when the expected
   information gain is low relative to cost.

3. **Batch by domain.** Group questions by domain and use domain-tuned
   prompts to reduce token usage.

4. **Cache base rates.** Pre-compute and cache base rates for common
   metrics to avoid redundant computation during benchmark runs.

5. **Track cost trends.** Monitor cost-per-question across runs. If
   cost is rising without accuracy improvement, investigate prompt
   bloat or unnecessary evidence retrieval.
