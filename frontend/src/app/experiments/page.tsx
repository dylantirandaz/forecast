"use client";

import { useState } from "react";
import MetricCard from "@/components/MetricCard";
import AblationChart from "@/components/AblationChart";
import CostPerformanceScatter from "@/components/CostPerformanceScatter";
import { FlaskConical, Trophy, DollarSign, BarChart3 } from "lucide-react";
import type { ExperimentResult } from "@/types/experiments";

// ── Mock data ───────────────────────────────────────────────────────

const defaultConfig = {
  name: "",
  description: "",
  use_base_rates: true,
  use_evidence_scoring: true,
  use_recency_weighting: true,
  use_novelty_filter: true,
  use_calibration: true,
  calibration_scope: "global",
  evidence_weighting: "composite",
  model_tier: "B",
  use_disagreement_second_pass: false,
  use_voi_gating: true,
  update_strategy: "bayesian",
  max_budget_per_question: 0.5,
};

const mockExperiments: ExperimentResult[] = [
  {
    id: "exp-001", name: "baseline_full_pipeline", experiment_type: "ablation", status: "completed",
    config: { ...defaultConfig, name: "baseline_full_pipeline", description: "Full pipeline with all components enabled" },
    brier_score: 0.185, log_score: -0.362, total_cost: 2.40, total_questions: 50, created_at: "2026-03-10T10:00:00Z", completed_at: "2026-03-10T11:30:00Z",
  },
  {
    id: "exp-002", name: "no_base_rates", experiment_type: "ablation", status: "completed",
    config: { ...defaultConfig, name: "no_base_rates", description: "Disable base rate lookup", use_base_rates: false },
    brier_score: 0.245, log_score: -0.480, total_cost: 2.35, total_questions: 50, created_at: "2026-03-11T10:00:00Z", completed_at: "2026-03-11T11:25:00Z",
  },
  {
    id: "exp-003", name: "one_shot_direct", experiment_type: "ablation", status: "completed",
    config: { ...defaultConfig, name: "one_shot_direct", description: "Single LLM call, no pipeline", use_evidence_scoring: false, use_calibration: false, use_base_rates: false },
    brier_score: 0.290, log_score: -0.610, total_cost: 0.85, total_questions: 50, created_at: "2026-03-12T10:00:00Z", completed_at: "2026-03-12T10:45:00Z",
  },
  {
    id: "exp-004", name: "raw_no_calibration", experiment_type: "ablation", status: "completed",
    config: { ...defaultConfig, name: "raw_no_calibration", description: "Skip calibration post-processing", use_calibration: false },
    brier_score: 0.210, log_score: -0.410, total_cost: 2.30, total_questions: 50, created_at: "2026-03-13T10:00:00Z", completed_at: "2026-03-13T11:20:00Z",
  },
  {
    id: "exp-005", name: "uniform_evidence", experiment_type: "ablation", status: "completed",
    config: { ...defaultConfig, name: "uniform_evidence", description: "Equal weight to all evidence", evidence_weighting: "uniform" },
    brier_score: 0.205, log_score: -0.398, total_cost: 2.38, total_questions: 50, created_at: "2026-03-14T10:00:00Z", completed_at: "2026-03-14T11:28:00Z",
  },
  {
    id: "exp-006", name: "no_recency", experiment_type: "ablation", status: "completed",
    config: { ...defaultConfig, name: "no_recency", description: "Disable recency weighting", use_recency_weighting: false },
    brier_score: 0.195, log_score: -0.378, total_cost: 2.36, total_questions: 50, created_at: "2026-03-15T10:00:00Z", completed_at: "2026-03-15T11:22:00Z",
  },
  {
    id: "exp-007", name: "no_novelty", experiment_type: "ablation", status: "completed",
    config: { ...defaultConfig, name: "no_novelty", description: "Disable novelty filter", use_novelty_filter: false },
    brier_score: 0.200, log_score: -0.390, total_cost: 2.38, total_questions: 50, created_at: "2026-03-16T10:00:00Z", completed_at: "2026-03-16T11:26:00Z",
  },
  {
    id: "exp-008", name: "disagreement_pass", experiment_type: "ablation", status: "completed",
    config: { ...defaultConfig, name: "disagreement_pass", description: "Enable disagreement second pass", use_disagreement_second_pass: true },
    brier_score: 0.175, log_score: -0.340, total_cost: 3.80, total_questions: 50, created_at: "2026-03-17T10:00:00Z", completed_at: "2026-03-17T12:00:00Z",
  },
  {
    id: "exp-009", name: "always_deep", experiment_type: "ablation", status: "completed",
    config: { ...defaultConfig, name: "always_deep", description: "Always use deep analysis (no VOI gating)", use_voi_gating: false, use_disagreement_second_pass: true, model_tier: "A" },
    brier_score: 0.170, log_score: -0.328, total_cost: 5.20, total_questions: 50, created_at: "2026-03-18T10:00:00Z", completed_at: "2026-03-18T13:00:00Z",
  },
  {
    id: "exp-010", name: "domain_calibration", experiment_type: "ablation", status: "completed",
    config: { ...defaultConfig, name: "domain_calibration", description: "Per-domain calibration curves", calibration_scope: "domain" },
    brier_score: 0.178, log_score: -0.345, total_cost: 2.45, total_questions: 50, created_at: "2026-03-19T10:00:00Z", completed_at: "2026-03-19T11:35:00Z",
  },
  {
    id: "exp-011", name: "static_prior", experiment_type: "ablation", status: "completed",
    config: { ...defaultConfig, name: "static_prior", description: "Static 50% prior, no base rates", use_base_rates: false, update_strategy: "static" },
    brier_score: 0.260, log_score: -0.520, total_cost: 1.90, total_questions: 50, created_at: "2026-03-20T10:00:00Z", completed_at: "2026-03-20T11:15:00Z",
  },
];

const ablationToggles = mockExperiments.map((e) => ({
  name: e.name,
  description: e.config.description,
}));

export default function ExperimentsPage() {
  const [enabledExperiments, setEnabledExperiments] = useState<Set<string>>(
    new Set(mockExperiments.map((e) => e.name))
  );

  const toggleExperiment = (name: string) => {
    setEnabledExperiments((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  };

  const filteredExperiments = mockExperiments.filter((e) =>
    enabledExperiments.has(e.name)
  );

  const bestExperiment = [...filteredExperiments].sort(
    (a, b) => a.brier_score - b.brier_score
  )[0];

  const avgCost =
    filteredExperiments.reduce((s, e) => s + e.total_cost, 0) /
    (filteredExperiments.length || 1);

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">
            Experiments &amp; Ablations
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            Compare pipeline configurations and identify optimal setups
          </p>
        </div>
        <button className="flex items-center gap-2 rounded-lg bg-brand-600 px-5 py-2.5 text-sm font-semibold text-white shadow-lg shadow-brand-600/25 transition hover:bg-brand-500">
          <FlaskConical className="h-4 w-4" />
          Run All Ablations
        </button>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          label="Experiments Run"
          value={filteredExperiments.length}
          subtitle="ablation configurations tested"
          icon={FlaskConical}
        />
        <MetricCard
          label="Best Brier Score"
          value={bestExperiment?.brier_score.toFixed(3) ?? "—"}
          subtitle={bestExperiment?.name.replace(/_/g, " ") ?? ""}
          icon={Trophy}
          trend={{ value: -8, label: "vs baseline" }}
        />
        <MetricCard
          label="Avg Cost per Config"
          value={`$${avgCost.toFixed(2)}`}
          subtitle="across all experiments"
          icon={DollarSign}
        />
        <MetricCard
          label="Questions per Run"
          value={50}
          subtitle="backtest question set"
          icon={BarChart3}
        />
      </div>

      {/* Quick ablation selector */}
      <section>
        <h2 className="section-heading">Quick Ablation Selector</h2>
        <div className="card">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {ablationToggles.map((abl) => (
              <label
                key={abl.name}
                className="flex cursor-pointer items-center gap-3 rounded-lg border border-surface-border p-3 transition hover:border-brand-600/50"
              >
                <input
                  type="checkbox"
                  checked={enabledExperiments.has(abl.name)}
                  onChange={() => toggleExperiment(abl.name)}
                  className="h-4 w-4 rounded border-gray-600 bg-gray-800 text-brand-600 focus:ring-brand-600 focus:ring-offset-0"
                />
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-gray-200">
                    {abl.name.replace(/_/g, " ")}
                  </p>
                  <p className="truncate text-xs text-gray-500">
                    {abl.description}
                  </p>
                </div>
              </label>
            ))}
          </div>
        </div>
      </section>

      {/* Results comparison */}
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
        {/* Brier Score Comparison */}
        <section>
          <h2 className="section-heading">Brier Score Comparison</h2>
          <div className="card">
            <p className="mb-4 text-xs text-gray-500">
              Horizontal bars showing Brier scores for each configuration. Green
              is best, red is worst. Dashed line marks the baseline.
            </p>
            <AblationChart experiments={filteredExperiments} />
          </div>
        </section>

        {/* Cost vs Accuracy */}
        <section>
          <h2 className="section-heading">Cost vs Accuracy</h2>
          <div className="card">
            <p className="mb-4 text-xs text-gray-500">
              Each point is one experiment. The Pareto frontier (dashed green)
              connects configs with the best accuracy at each cost level.
            </p>
            <CostPerformanceScatter experiments={filteredExperiments} />
          </div>
        </section>
      </div>

      {/* Best Config highlight */}
      {bestExperiment && (
        <section>
          <h2 className="section-heading">Best Configuration</h2>
          <div className="card border-accent-positive/30">
            <div className="flex items-start gap-4">
              <div className="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-xl bg-accent-positive/10">
                <Trophy className="h-6 w-6 text-accent-positive" />
              </div>
              <div className="min-w-0 flex-1">
                <h3 className="text-lg font-bold text-gray-100">
                  {bestExperiment.name.replace(/_/g, " ")}
                </h3>
                <p className="mt-1 text-sm text-gray-400">
                  {bestExperiment.config.description}
                </p>
                <div className="mt-3 flex flex-wrap gap-4">
                  <span className="text-sm text-gray-300">
                    Brier:{" "}
                    <span className="font-semibold text-accent-positive">
                      {bestExperiment.brier_score.toFixed(3)}
                    </span>
                  </span>
                  <span className="text-sm text-gray-300">
                    Log Score:{" "}
                    <span className="font-semibold text-gray-100">
                      {bestExperiment.log_score.toFixed(3)}
                    </span>
                  </span>
                  <span className="text-sm text-gray-300">
                    Cost:{" "}
                    <span className="font-semibold text-gray-100">
                      ${bestExperiment.total_cost.toFixed(2)}
                    </span>
                  </span>
                  <span className="text-sm text-gray-300">
                    Tier:{" "}
                    <span className="font-semibold text-gray-100">
                      {bestExperiment.config.model_tier}
                    </span>
                  </span>
                </div>
              </div>
            </div>
          </div>
        </section>
      )}

      {/* Experiment list table */}
      <section>
        <h2 className="section-heading">All Experiments</h2>
        <div className="overflow-hidden rounded-xl border border-surface-border">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-surface-border bg-surface">
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Name
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Type
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Status
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Brier
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Log Score
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Cost
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Questions
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Created
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-border">
                {mockExperiments.map((exp) => (
                  <tr
                    key={exp.id}
                    className="bg-surface-raised hover:bg-surface-overlay transition-colors"
                  >
                    <td className="px-4 py-3 font-medium text-gray-200">
                      {exp.name.replace(/_/g, " ")}
                    </td>
                    <td className="px-4 py-3 text-gray-400">{exp.experiment_type}</td>
                    <td className="px-4 py-3">
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-accent-positive/10 px-2.5 py-0.5 text-xs font-medium text-accent-positive">
                        <span className="h-1.5 w-1.5 rounded-full bg-accent-positive" />
                        {exp.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 tabular-nums text-gray-300">
                      {exp.brier_score.toFixed(3)}
                    </td>
                    <td className="px-4 py-3 tabular-nums text-gray-300">
                      {exp.log_score.toFixed(3)}
                    </td>
                    <td className="px-4 py-3 tabular-nums text-gray-300">
                      ${exp.total_cost.toFixed(2)}
                    </td>
                    <td className="px-4 py-3 tabular-nums text-gray-400">
                      {exp.total_questions}
                    </td>
                    <td className="px-4 py-3 text-gray-500">
                      {new Date(exp.created_at).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>
    </div>
  );
}
