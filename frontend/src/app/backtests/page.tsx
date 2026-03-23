"use client";

import { useState } from "react";
import clsx from "clsx";
import { format } from "date-fns";
import { Play, CheckCircle, Clock, AlertCircle } from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import MetricCard from "@/components/MetricCard";

// ── Mock data ───────────────────────────────────────────────────────

const mockBacktests = [
  {
    id: "bt1",
    name: "2024 Rent Forecast Replay",
    start_date: "2024-01-01",
    end_date: "2024-12-31",
    question_ids: ["q1"],
    status: "completed" as const,
    created_at: "2026-03-15T10:00:00Z",
    completed_at: "2026-03-15T10:12:00Z",
    brier: 0.164,
    log_score: -0.312,
    n_forecasts: 52,
  },
  {
    id: "bt2",
    name: "2025 Policy Impact Backtest",
    start_date: "2025-01-01",
    end_date: "2025-12-31",
    question_ids: ["q2", "q4"],
    status: "completed" as const,
    created_at: "2026-03-18T14:00:00Z",
    completed_at: "2026-03-18T14:25:00Z",
    brier: 0.198,
    log_score: -0.401,
    n_forecasts: 104,
  },
  {
    id: "bt3",
    name: "Full Model Backtest 2023-2025",
    start_date: "2023-01-01",
    end_date: "2025-12-31",
    question_ids: ["q1", "q2", "q3", "q4", "q5"],
    status: "running" as const,
    created_at: "2026-03-21T09:00:00Z",
    completed_at: undefined,
    brier: undefined,
    log_score: undefined,
    n_forecasts: undefined,
  },
];

const forecastVsRealized = [
  { date: "Jan", predicted: 0.30, realized: 0 },
  { date: "Feb", predicted: 0.32, realized: 0 },
  { date: "Mar", predicted: 0.35, realized: 0 },
  { date: "Apr", predicted: 0.33, realized: 0 },
  { date: "May", predicted: 0.38, realized: 0 },
  { date: "Jun", predicted: 0.41, realized: 0 },
  { date: "Jul", predicted: 0.44, realized: 0 },
  { date: "Aug", predicted: 0.47, realized: 0 },
  { date: "Sep", predicted: 0.52, realized: 0 },
  { date: "Oct", predicted: 0.55, realized: 1 },
  { date: "Nov", predicted: 0.60, realized: 1 },
  { date: "Dec", predicted: 0.63, realized: 1 },
];

const statusConfig = {
  completed: { icon: CheckCircle, color: "text-accent-positive", bg: "bg-accent-positive/10", label: "Completed" },
  running: { icon: Clock, color: "text-accent-warning", bg: "bg-accent-warning/10", label: "Running" },
  pending: { icon: Clock, color: "text-gray-400", bg: "bg-gray-500/10", label: "Pending" },
  failed: { icon: AlertCircle, color: "text-accent-negative", bg: "bg-accent-negative/10", label: "Failed" },
};

export default function BacktestsPage() {
  const [selectedBacktest, setSelectedBacktest] = useState("bt1");

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">Backtesting</h1>
          <p className="mt-1 text-sm text-gray-500">
            Historical replay and forecast accuracy assessment
          </p>
        </div>
        <button className="flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-brand-700 transition-colors">
          <Play className="h-4 w-4" />
          New Backtest
        </button>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard label="Total Backtests" value={3} subtitle="1 running" />
        <MetricCard
          label="Best Brier Score"
          value="0.164"
          subtitle="2024 Rent Forecast"
        />
        <MetricCard
          label="Avg Log Score"
          value="-0.357"
          subtitle="Across completed runs"
        />
        <MetricCard
          label="Forecasts Evaluated"
          value={156}
          subtitle="Across all runs"
        />
      </div>

      {/* Backtest runs list */}
      <section>
        <h2 className="section-heading">Backtest Runs</h2>
        <div className="space-y-3">
          {mockBacktests.map((bt) => {
            const st = statusConfig[bt.status];
            const StatusIcon = st.icon;
            const isSelected = bt.id === selectedBacktest;

            return (
              <button
                key={bt.id}
                onClick={() => setSelectedBacktest(bt.id)}
                className={clsx(
                  "w-full text-left card-hover",
                  isSelected && "border-brand-500/40 ring-1 ring-brand-500/20"
                )}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className={clsx("flex h-9 w-9 items-center justify-center rounded-lg", st.bg)}>
                      <StatusIcon className={clsx("h-4 w-4", st.color)} />
                    </div>
                    <div>
                      <h3 className="text-sm font-semibold text-gray-100">
                        {bt.name}
                      </h3>
                      <p className="text-xs text-gray-500">
                        {bt.start_date} to {bt.end_date} &middot;{" "}
                        {bt.question_ids.length} question(s)
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-6">
                    {bt.brier !== undefined && (
                      <div className="text-right">
                        <p className="text-xs text-gray-500">Brier</p>
                        <p className="text-sm font-semibold text-gray-100 tabular-nums">
                          {bt.brier.toFixed(3)}
                        </p>
                      </div>
                    )}
                    {bt.log_score !== undefined && (
                      <div className="text-right">
                        <p className="text-xs text-gray-500">Log Score</p>
                        <p className="text-sm font-semibold text-gray-100 tabular-nums">
                          {bt.log_score.toFixed(3)}
                        </p>
                      </div>
                    )}
                    <span className={clsx("badge text-[10px]", st.bg, st.color)}>
                      {st.label}
                    </span>
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      </section>

      {/* Forecast vs Realized chart */}
      <section>
        <h2 className="section-heading">Forecast vs. Realized Outcome</h2>
        <div className="card">
          <p className="mb-4 text-xs text-gray-500">
            Showing results for: 2024 Rent Forecast Replay
          </p>
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart
                data={forecastVsRealized}
                margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#2d3f5e" />
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 11, fill: "#94a3b8" }}
                  tickLine={false}
                  axisLine={{ stroke: "#2d3f5e" }}
                />
                <YAxis
                  domain={[0, 1]}
                  tickFormatter={(v: number) => `${Math.round(v * 100)}%`}
                  tick={{ fontSize: 11, fill: "#94a3b8" }}
                  tickLine={false}
                  axisLine={{ stroke: "#2d3f5e" }}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#1e293b",
                    border: "1px solid #2d3f5e",
                    borderRadius: 8,
                    fontSize: 12,
                  }}
                  formatter={(value: number, name: string) => [
                    `${(value * 100).toFixed(0)}%`,
                    name === "predicted" ? "Predicted" : "Realized",
                  ]}
                />
                <Legend
                  wrapperStyle={{ fontSize: 12, color: "#94a3b8" }}
                />
                <Line
                  type="monotone"
                  dataKey="predicted"
                  stroke="#3b82f6"
                  strokeWidth={2}
                  dot={{ r: 3, fill: "#3b82f6", stroke: "#0f1729", strokeWidth: 2 }}
                  name="Predicted"
                />
                <Line
                  type="stepAfter"
                  dataKey="realized"
                  stroke="#22c55e"
                  strokeWidth={2}
                  strokeDasharray="6 4"
                  dot={false}
                  name="Realized"
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </section>
    </div>
  );
}
