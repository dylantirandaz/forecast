"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import MetricCard from "@/components/MetricCard";
import CostBreakdown from "@/components/CostBreakdown";
import CostPerformanceScatter from "@/components/CostPerformanceScatter";
import { DollarSign, TrendingDown, Target, Wallet } from "lucide-react";
import type { CostLogEntry, ExperimentResult } from "@/types/experiments";

// ── Mock data ───────────────────────────────────────────────────────

const costByOperation: Record<string, number> = {
  forecast_runs: 30.0,
  evidence_scoring: 8.0,
  backtests: 5.0,
  base_rates: 2.80,
};

const costByTier: Record<string, number> = {
  "Tier A": 12.30,
  "Tier B": 28.50,
  Other: 5.00,
};

const costOverTime = [
  { date: "Mar 1", cost: 1.2 },
  { date: "Mar 3", cost: 2.8 },
  { date: "Mar 5", cost: 5.1 },
  { date: "Mar 7", cost: 8.4 },
  { date: "Mar 9", cost: 12.0 },
  { date: "Mar 11", cost: 16.5 },
  { date: "Mar 13", cost: 21.2 },
  { date: "Mar 15", cost: 27.0 },
  { date: "Mar 17", cost: 32.8 },
  { date: "Mar 19", cost: 38.5 },
  { date: "Mar 21", cost: 42.1 },
  { date: "Mar 22", cost: 45.8 },
];

const mockCostLog: CostLogEntry[] = [
  { id: "cl-001", operation_type: "forecast_run", model_tier: "B", model_name: "gpt-4o", input_tokens: 3200, output_tokens: 850, cost_usd: 0.28, latency_ms: 4200, created_at: "2026-03-22T09:15:00Z" },
  { id: "cl-002", operation_type: "evidence_scoring", model_tier: "B", model_name: "gpt-4o", input_tokens: 2100, output_tokens: 420, cost_usd: 0.15, latency_ms: 2800, created_at: "2026-03-22T09:14:00Z" },
  { id: "cl-003", operation_type: "forecast_run", model_tier: "A", model_name: "gpt-4o-mini", input_tokens: 1800, output_tokens: 600, cost_usd: 0.04, latency_ms: 1500, created_at: "2026-03-22T09:10:00Z" },
  { id: "cl-004", operation_type: "base_rate_lookup", model_tier: "B", model_name: "gpt-4o", input_tokens: 1500, output_tokens: 350, cost_usd: 0.12, latency_ms: 2200, created_at: "2026-03-22T09:05:00Z" },
  { id: "cl-005", operation_type: "backtest", model_tier: "B", model_name: "gpt-4o", input_tokens: 4500, output_tokens: 1200, cost_usd: 0.42, latency_ms: 6100, created_at: "2026-03-22T08:55:00Z" },
  { id: "cl-006", operation_type: "forecast_run", model_tier: "B", model_name: "gpt-4o", input_tokens: 3800, output_tokens: 900, cost_usd: 0.31, latency_ms: 4800, created_at: "2026-03-22T08:45:00Z" },
  { id: "cl-007", operation_type: "evidence_scoring", model_tier: "A", model_name: "gpt-4o-mini", input_tokens: 1200, output_tokens: 280, cost_usd: 0.02, latency_ms: 900, created_at: "2026-03-22T08:40:00Z" },
  { id: "cl-008", operation_type: "forecast_run", model_tier: "B", model_name: "gpt-4o", input_tokens: 2900, output_tokens: 780, cost_usd: 0.25, latency_ms: 3900, created_at: "2026-03-22T08:30:00Z" },
];

// Reuse experiment data for scatter plot
const scatterExperiments: ExperimentResult[] = [
  { id: "s1", name: "baseline", experiment_type: "ablation", status: "completed", config: {} as ExperimentResult["config"], brier_score: 0.185, log_score: -0.362, total_cost: 2.40, total_questions: 50, created_at: "", completed_at: null },
  { id: "s2", name: "no_base_rates", experiment_type: "ablation", status: "completed", config: {} as ExperimentResult["config"], brier_score: 0.245, log_score: -0.48, total_cost: 2.35, total_questions: 50, created_at: "", completed_at: null },
  { id: "s3", name: "one_shot_direct", experiment_type: "ablation", status: "completed", config: {} as ExperimentResult["config"], brier_score: 0.290, log_score: -0.61, total_cost: 0.85, total_questions: 50, created_at: "", completed_at: null },
  { id: "s4", name: "domain_calibration", experiment_type: "ablation", status: "completed", config: {} as ExperimentResult["config"], brier_score: 0.178, log_score: -0.345, total_cost: 2.45, total_questions: 50, created_at: "", completed_at: null },
  { id: "s5", name: "always_deep", experiment_type: "ablation", status: "completed", config: {} as ExperimentResult["config"], brier_score: 0.170, log_score: -0.328, total_cost: 5.20, total_questions: 50, created_at: "", completed_at: null },
  { id: "s6", name: "disagreement_pass", experiment_type: "ablation", status: "completed", config: {} as ExperimentResult["config"], brier_score: 0.175, log_score: -0.340, total_cost: 3.80, total_questions: 50, created_at: "", completed_at: null },
];

const TOTAL_COST = 45.80;
const TOTAL_FORECASTS = 150;
const BUDGET = 100.0;

export default function CostsPage() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-100">
          Cost &amp; Performance
        </h1>
        <p className="mt-1 text-sm text-gray-500">
          Track spending, analyze cost efficiency, and monitor budget utilization
        </p>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          label="Total Cost"
          value={`$${TOTAL_COST.toFixed(2)}`}
          subtitle={`across ${TOTAL_FORECASTS} forecasts`}
          icon={DollarSign}
          trend={{ value: 12, label: "this month" }}
        />
        <MetricCard
          label="Cost per Question"
          value={`$${(TOTAL_COST / TOTAL_FORECASTS).toFixed(2)}`}
          subtitle="average across all runs"
          icon={TrendingDown}
          trend={{ value: -5, label: "vs last month" }}
        />
        <MetricCard
          label="Cost per Brier Point"
          value={`$${(TOTAL_COST / 0.185).toFixed(0)}`}
          subtitle="lower is more cost-efficient"
          icon={Target}
        />
        <MetricCard
          label="Budget Remaining"
          value={`$${(BUDGET - TOTAL_COST).toFixed(2)}`}
          subtitle={`of $${BUDGET.toFixed(2)} monthly budget`}
          icon={Wallet}
          trend={{ value: -((TOTAL_COST / BUDGET) * 100), label: "utilized" }}
        />
      </div>

      {/* Cost breakdowns */}
      <section>
        <h2 className="section-heading">Cost Breakdown</h2>
        <div className="card">
          <CostBreakdown
            costByOperation={costByOperation}
            costByTier={costByTier}
          />
        </div>
      </section>

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
        {/* Cost over time */}
        <section>
          <h2 className="section-heading">Cumulative Cost Over Time</h2>
          <div className="card">
            <p className="mb-4 text-xs text-gray-500">
              Running total of API costs for the current billing period.
            </p>
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart
                  data={costOverTime}
                  margin={{ top: 10, right: 20, left: 10, bottom: 10 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#2d3f5e" />
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 11, fill: "#94a3b8" }}
                    tickLine={false}
                    axisLine={{ stroke: "#2d3f5e" }}
                  />
                  <YAxis
                    tick={{ fontSize: 11, fill: "#94a3b8" }}
                    tickLine={false}
                    axisLine={{ stroke: "#2d3f5e" }}
                    tickFormatter={(v: number) => `$${v}`}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#1e293b",
                      border: "1px solid #2d3f5e",
                      borderRadius: 8,
                      fontSize: 12,
                    }}
                    formatter={(value: number) => [
                      `$${value.toFixed(2)}`,
                      "Cumulative Cost",
                    ]}
                  />
                  <Line
                    type="monotone"
                    dataKey="cost"
                    stroke="#6366f1"
                    strokeWidth={2}
                    dot={{ fill: "#6366f1", r: 3 }}
                    activeDot={{ r: 5, fill: "#818cf8" }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        </section>

        {/* Cost vs Performance */}
        <section>
          <h2 className="section-heading">Cost vs Performance Tradeoff</h2>
          <div className="card">
            <p className="mb-4 text-xs text-gray-500">
              Explore the tradeoff between spending and forecast accuracy across
              configurations.
            </p>
            <CostPerformanceScatter experiments={scatterExperiments} />
          </div>
        </section>
      </div>

      {/* Recent cost log entries */}
      <section>
        <h2 className="section-heading">Recent Cost Log</h2>
        <div className="overflow-hidden rounded-xl border border-surface-border">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-surface-border bg-surface">
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Operation
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Model
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Tier
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Input Tokens
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Output Tokens
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Cost
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Latency
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Time
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-border">
                {mockCostLog.map((entry) => (
                  <tr
                    key={entry.id}
                    className="bg-surface-raised hover:bg-surface-overlay transition-colors"
                  >
                    <td className="px-4 py-3 font-medium text-gray-200">
                      {entry.operation_type.replace(/_/g, " ")}
                    </td>
                    <td className="px-4 py-3 text-gray-400">
                      {entry.model_name}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                          entry.model_tier === "A"
                            ? "bg-green-500/10 text-green-400"
                            : entry.model_tier === "B"
                              ? "bg-amber-500/10 text-amber-400"
                              : "bg-blue-500/10 text-blue-400"
                        }`}
                      >
                        {entry.model_tier}
                      </span>
                    </td>
                    <td className="px-4 py-3 tabular-nums text-gray-400">
                      {entry.input_tokens.toLocaleString()}
                    </td>
                    <td className="px-4 py-3 tabular-nums text-gray-400">
                      {entry.output_tokens.toLocaleString()}
                    </td>
                    <td className="px-4 py-3 tabular-nums text-gray-300">
                      ${entry.cost_usd.toFixed(2)}
                    </td>
                    <td className="px-4 py-3 tabular-nums text-gray-400">
                      {(entry.latency_ms / 1000).toFixed(1)}s
                    </td>
                    <td className="px-4 py-3 text-gray-500">
                      {new Date(entry.created_at).toLocaleTimeString()}
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
