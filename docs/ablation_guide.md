# Ablation Experiment Guide

## What Are Ablation Experiments?

Ablation experiments measure the marginal contribution of each component
in the forecasting pipeline by systematically disabling one component at
a time and measuring the resulting change in forecast accuracy. If
removing a component causes a large drop in accuracy, that component is
contributing significant value. If removing it has little effect, the
component may be redundant or under-performing.

Every ablation run is recorded in the `experiment_runs` table with
`experiment_type = 'ablation'`.

## Available Ablation Experiments

| #  | Flag Name                    | Description                                                   |
|----|------------------------------|---------------------------------------------------------------|
| 1  | `no_evidence_scoring`        | Disables the multi-dimensional evidence scoring pipeline.     |
|    |                              | Evidence items are still ingested but not scored for           |
|    |                              | relevance, reliability, or directional effect. The Bayesian   |
|    |                              | updater receives unweighted evidence.                         |
| 2  | `no_bayesian_update`         | Skips the Bayesian belief-updating step entirely. The         |
|    |                              | forecast returns the base-rate prior as the final prediction. |
| 3  | `no_base_rate`               | Removes the base-rate prior. The updater starts from a        |
|    |                              | uniform (0.5) prior instead of a historically informed one.   |
| 4  | `no_scenario_conditioning`   | Ignores all scenario assumptions. Forecasts are generated     |
|    |                              | as if no policy scenario were specified.                      |
| 5  | `no_recency_weighting`       | Disables time-decay weighting in evidence scoring. Old and    |
|    |                              | new evidence receive equal weight.                            |
| 6  | `no_source_credibility`      | Treats every source as having maximum credibility (1.0).      |
|    |                              | Removes the quality filter on unreliable sources.             |
| 7  | `no_redundancy_detection`    | Disables the redundancy discount that down-weights            |
|    |                              | correlated or duplicative evidence items.                     |
| 8  | `no_calibration_adjustment`  | Skips the post-hoc calibration correction step that adjusts   |
|    |                              | raw probabilities based on historical calibration curves.     |
| 9  | `no_ensemble`                | Uses a single model rather than the full ensemble. Defaults   |
|    |                              | to the `bayesian_updater` model type.                         |
| 10 | `no_llm_reasoning`           | Removes LLM-generated chain-of-thought rationales. The       |
|    |                              | system relies solely on numerical scoring without natural     |
|    |                              | language reasoning.                                           |

## How to Run Ablation Experiments

### Via CLI

Run a single ablation experiment:

```bash
python -m app.cli experiment run-ablation \
    --name "No evidence scoring - 2026Q1" \
    --flag no_evidence_scoring \
    --question-set active \
    --model-version latest
```

Run all 10 standard ablation experiments:

```bash
python -m app.cli experiment run-ablation-suite \
    --name-prefix "Full ablation - 2026Q1" \
    --question-set active \
    --model-version latest
```

### Via API

Create and start an ablation experiment:

```bash
curl -X POST http://localhost:8000/api/v1/experiments \
  -H "Content-Type: application/json" \
  -d '{
    "name": "No evidence scoring - 2026Q1",
    "experiment_type": "ablation",
    "ablation_flags": {
      "no_evidence_scoring": true
    },
    "config": {
      "question_set": "active",
      "model_version": "latest"
    }
  }'
```

Start the experiment:

```bash
curl -X POST http://localhost:8000/api/v1/experiments/{experiment_id}/start
```

### Via Python

```python
from app.services.experiment_runner import ExperimentRunner

runner = ExperimentRunner(db_session)
run = await runner.create_ablation(
    name="No evidence scoring - 2026Q1",
    flags={"no_evidence_scoring": True},
    question_set="active",
    model_version="latest",
)
results = await runner.execute(run.id)
```

## Interpreting Results

After an ablation run completes, the `experiment_runs` record contains:

- **mean_brier_score** -- Average Brier score across all questions. Lower
  is better. Compare to the full-pipeline baseline to see the impact.
- **mean_log_score** -- Average logarithmic score. More sensitive to
  confident wrong predictions than Brier.
- **total_cost_usd** -- Total cost of the run. Useful for
  cost-effectiveness analysis.
- **results** (JSONB) -- Detailed per-question breakdown including
  individual scores, predicted values, and actual values.

### Comparison workflow

1. Run the full pipeline (no flags disabled) as a baseline.
2. Run each ablation experiment.
3. Use the comparison endpoint or CLI to view deltas:

```bash
python -m app.cli experiment compare \
    --baseline {baseline_id} \
    --runs {ablation_run_id_1} {ablation_run_id_2} ...
```

```bash
curl http://localhost:8000/api/v1/experiments/compare?baseline={baseline_id}&runs={id1},{id2}
```

The comparison output includes:

| Metric              | Baseline | no_evidence_scoring | Delta   |
|---------------------|----------|---------------------|---------|
| Mean Brier Score    | 0.182    | 0.241               | +0.059  |
| Mean Log Score      | -0.312   | -0.487              | -0.175  |
| Total Cost (USD)    | $1.24    | $0.87               | -$0.37  |

A positive delta in Brier score means the ablated run is **worse** (less
accurate). A negative delta in cost means the ablated run is **cheaper**.

### Key questions to answer

- Which component contributes the most to accuracy? (largest Brier
  delta)
- Which component is most cost-effective? (best accuracy-per-dollar)
- Are any components not pulling their weight? (small accuracy delta,
  high cost)

## Adding New Ablation Configurations

To add a new ablation flag:

1. **Define the flag** in `app/services/ablation_flags.py`:

```python
# In ABLATION_FLAGS dict
ABLATION_FLAGS = {
    # ... existing flags ...
    "no_my_new_component": AblationFlag(
        name="no_my_new_component",
        description="Disables the new component",
        affects=["component_name"],
    ),
}
```

2. **Implement the gate** in the relevant service. Each component should
   check `ablation_flags` before executing:

```python
async def score_evidence(self, item, ablation_flags=None):
    if ablation_flags and ablation_flags.get("no_evidence_scoring"):
        return EvidenceScore.default()
    # ... normal scoring logic ...
```

3. **Register the flag** in the ablation suite so it is included in
   full suite runs. Add the flag name to `STANDARD_ABLATION_SUITE` in
   `app/services/experiment_runner.py`.

4. **Add a test** in `tests/test_ablation.py` to verify the flag
   correctly disables the component.

5. **Update this guide** to document the new experiment in the table
   above.
