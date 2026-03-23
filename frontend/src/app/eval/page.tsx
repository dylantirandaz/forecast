"use client";

import { useState } from "react";
import Link from "next/link";
import MetricCard from "@/components/MetricCard";
import {
  ClipboardCheck,
  Target,
  Crosshair,
  HelpCircle,
  Play,
  X,
  Trophy,
} from "lucide-react";

// ── Mock data ───────────────────────────────────────────────────────

const evalRuns = [
  {
    id: "run-001",
    name: "Full Pipeline v1",
    status: "completed" as const,
    brier: 0.192,
    logScore: 0.55,
    calError: 0.035,
    questions: 80,
    cost: 2.4,
    date: "2026-03-18",
  },
  {
    id: "run-002",
    name: "No Base Rates",
    status: "completed" as const,
    brier: 0.248,
    logScore: 0.72,
    calError: 0.068,
    questions: 80,
    cost: 2.35,
    date: "2026-03-17",
  },
  {
    id: "run-003",
    name: "Static Prior",
    status: "completed" as const,
    brier: 0.265,
    logScore: 0.78,
    calError: 0.082,
    questions: 80,
    cost: 1.9,
    date: "2026-03-16",
  },
  {
    id: "run-004",
    name: "No Calibration",
    status: "completed" as const,
    brier: 0.215,
    logScore: 0.62,
    calError: 0.095,
    questions: 80,
    cost: 2.3,
    date: "2026-03-15",
  },
  {
    id: "run-005",
    name: "Uniform Weights",
    status: "completed" as const,
    brier: 0.208,
    logScore: 0.59,
    calError: 0.042,
    questions: 80,
    cost: 2.38,
    date: "2026-03-14",
  },
  {
    id: "run-006",
    name: "Tier B Only",
    status: "completed" as const,
    brier: 0.178,
    logScore: 0.48,
    calError: 0.028,
    questions: 80,
    cost: 5.2,
    date: "2026-03-13",
  },
];

const bestBrier = Math.min(...evalRuns.map((r) => r.brier));
const avgCalError =
  evalRuns.reduce((s, r) => s + r.calError, 0) / evalRuns.length;
const totalQuestions = evalRuns.reduce((s, r) => s + r.questions, 0);

function statusBadge(status: string) {
  const colors: Record<string, string> = {
    completed: "bg-accent-positive/15 text-accent-positive",
    running: "bg-blue-500/15 text-blue-400",
    failed: "bg-accent-negative/15 text-accent-negative",
    pending: "bg-yellow-500/15 text-yellow-400",
  };
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${colors[status] ?? colors.pending}`}
    >
      {status}
    </span>
  );
}

export default function EvalDashboardPage() {
  const [showConfig, setShowConfig] = useState(false);

  const bestRuns = [...evalRuns].sort((a, b) => a.brier - b.brier).slice(0, 3);

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">
            Evaluation Dashboard
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            Compare evaluation runs and track forecasting performance
          </p>
        </div>
        <button
          onClick={() => setShowConfig(true)}
          className="inline-flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-brand-500"
        >
          <Play className="h-4 w-4" />
          Run Evaluation
        </button>
      </div>

      {/* Config modal */}
      {showConfig && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div className="w-full max-w-lg rounded-xl border border-surface-border bg-surface p-6 shadow-2xl">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-100">
                Evaluation Configuration
              </h2>
              <button
                onClick={() => setShowConfig(false)}
                className="rounded-lg p-1 text-gray-400 hover:bg-surface-overlay hover:text-gray-200"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-gray-400 mb-1">
                  Run Name
                </label>
                <input
                  type="text"
                  placeholder="e.g. Full Pipeline v2"
                  className="w-full rounded-lg border border-surface-border bg-surface-raised px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:border-brand-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-400 mb-1">
                  Question Set
                </label>
                <select className="w-full rounded-lg border border-surface-border bg-surface-raised px-3 py-2 text-sm text-gray-200 focus:border-brand-500 focus:outline-none">
                  <option>All Resolved (80 questions)</option>
                  <option>Macro Only (22 questions)</option>
                  <option>Geopolitical Only (18 questions)</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-400 mb-1">
                  Horizons
                </label>
                <div className="flex gap-2">
                  {["90d", "30d", "7d"].map((h) => (
                    <label
                      key={h}
                      className="flex items-center gap-1.5 rounded-lg border border-surface-border bg-surface-raised px-3 py-1.5 text-xs text-gray-300"
                    >
                      <input
                        type="checkbox"
                        defaultChecked
                        className="rounded border-gray-600"
                      />
                      {h}
                    </label>
                  ))}
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-400 mb-1">
                  Model Tier
                </label>
                <select className="w-full rounded-lg border border-surface-border bg-surface-raised px-3 py-2 text-sm text-gray-200 focus:border-brand-500 focus:outline-none">
                  <option>Tier A (GPT-4 class)</option>
                  <option>Tier B (GPT-4o class)</option>
                  <option>Tier C (GPT-3.5 class)</option>
                </select>
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <button
                  onClick={() => setShowConfig(false)}
                  className="rounded-lg px-4 py-2 text-sm font-medium text-gray-400 hover:text-gray-200"
                >
                  Cancel
                </button>
                <button
                  onClick={() => setShowConfig(false)}
                  className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-500"
                >
                  Start Run
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Summary metrics */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          label="Total Runs"
          value={evalRuns.length}
          subtitle="Evaluation runs completed"
          icon={ClipboardCheck}
        />
        <MetricCard
          label="Best Brier Score"
          value={bestBrier.toFixed(3)}
          subtitle="Lower is better (0 = perfect)"
          icon={Target}
          trend={{ value: -12, label: "vs always-0.5" }}
        />
        <MetricCard
          label="Avg Calibration Error"
          value={avgCalError.toFixed(3)}
          subtitle="Mean absolute deviation"
          icon={Crosshair}
        />
        <MetricCard
          label="Total Questions Evaluated"
          value={totalQuestions}
          subtitle={`Across ${evalRuns.length} runs`}
          icon={HelpCircle}
        />
      </div>

      {/* Best performing configs */}
      <section>
        <h2 className="section-heading flex items-center gap-2">
          <Trophy className="h-4 w-4 text-yellow-500" />
          Best Performing Configs
        </h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {bestRuns.map((run, idx) => (
            <Link key={run.id} href={`/eval/${run.id}`}>
              <div className="card group cursor-pointer transition-all hover:border-brand-500/50">
                <div className="flex items-center gap-2 mb-2">
                  <span
                    className={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold ${
                      idx === 0
                        ? "bg-yellow-500/20 text-yellow-400"
                        : idx === 1
                          ? "bg-gray-400/20 text-gray-300"
                          : "bg-orange-500/20 text-orange-400"
                    }`}
                  >
                    #{idx + 1}
                  </span>
                  <span className="text-sm font-semibold text-gray-200 group-hover:text-brand-400 transition-colors">
                    {run.name}
                  </span>
                </div>
                <div className="grid grid-cols-3 gap-2 text-xs">
                  <div>
                    <span className="text-gray-500">Brier</span>
                    <p className="text-gray-200 font-mono tabular-nums">
                      {run.brier.toFixed(3)}
                    </p>
                  </div>
                  <div>
                    <span className="text-gray-500">Log</span>
                    <p className="text-gray-200 font-mono tabular-nums">
                      {run.logScore.toFixed(2)}
                    </p>
                  </div>
                  <div>
                    <span className="text-gray-500">Cal Err</span>
                    <p className="text-gray-200 font-mono tabular-nums">
                      {run.calError.toFixed(3)}
                    </p>
                  </div>
                </div>
              </div>
            </Link>
          ))}
        </div>
      </section>

      {/* Eval runs table */}
      <section>
        <h2 className="section-heading">Recent Evaluation Runs</h2>
        <div className="overflow-hidden rounded-xl border border-surface-border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-surface-border bg-surface">
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Name
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
                  Cal Error
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Questions
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Cost
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Date
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-border">
              {evalRuns.map((run) => (
                <tr
                  key={run.id}
                  className="bg-surface-raised hover:bg-surface-overlay transition-colors"
                >
                  <td className="px-4 py-3">
                    <Link
                      href={`/eval/${run.id}`}
                      className="font-medium text-brand-400 hover:text-brand-300 transition-colors"
                    >
                      {run.name}
                    </Link>
                  </td>
                  <td className="px-4 py-3">{statusBadge(run.status)}</td>
                  <td className="px-4 py-3 font-mono text-gray-300 tabular-nums">
                    {run.brier.toFixed(3)}
                  </td>
                  <td className="px-4 py-3 font-mono text-gray-300 tabular-nums">
                    {run.logScore.toFixed(2)}
                  </td>
                  <td className="px-4 py-3 font-mono text-gray-300 tabular-nums">
                    {run.calError.toFixed(3)}
                  </td>
                  <td className="px-4 py-3 text-gray-400 tabular-nums">
                    {run.questions}
                  </td>
                  <td className="px-4 py-3 text-gray-400 tabular-nums">
                    ${run.cost.toFixed(2)}
                  </td>
                  <td className="px-4 py-3 text-gray-500 tabular-nums">
                    {run.date}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
