"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import MetricCard from "@/components/MetricCard";
import CalibrationPlot from "@/components/CalibrationPlot";
import { Target, TrendingUp, BarChart3, Crosshair } from "lucide-react";
import type { CalibrationBucket } from "@/types";

// ── Mock data ───────────────────────────────────────────────────────

const mockBuckets: CalibrationBucket[] = [
  { predicted_low: 0.0, predicted_high: 0.1, predicted_mean: 0.05, observed_frequency: 0.08, count: 12 },
  { predicted_low: 0.1, predicted_high: 0.2, predicted_mean: 0.15, observed_frequency: 0.18, count: 15 },
  { predicted_low: 0.2, predicted_high: 0.3, predicted_mean: 0.25, observed_frequency: 0.22, count: 18 },
  { predicted_low: 0.3, predicted_high: 0.4, predicted_mean: 0.35, observed_frequency: 0.30, count: 22 },
  { predicted_low: 0.4, predicted_high: 0.5, predicted_mean: 0.45, observed_frequency: 0.48, count: 25 },
  { predicted_low: 0.5, predicted_high: 0.6, predicted_mean: 0.55, observed_frequency: 0.52, count: 20 },
  { predicted_low: 0.6, predicted_high: 0.7, predicted_mean: 0.65, observed_frequency: 0.68, count: 17 },
  { predicted_low: 0.7, predicted_high: 0.8, predicted_mean: 0.75, observed_frequency: 0.70, count: 14 },
  { predicted_low: 0.8, predicted_high: 0.9, predicted_mean: 0.85, observed_frequency: 0.82, count: 10 },
  { predicted_low: 0.9, predicted_high: 1.0, predicted_mean: 0.95, observed_frequency: 0.90, count: 8 },
];

const sharpnessData = [
  { bin: "0-10%", count: 12 },
  { bin: "10-20%", count: 15 },
  { bin: "20-30%", count: 18 },
  { bin: "30-40%", count: 22 },
  { bin: "40-50%", count: 25 },
  { bin: "50-60%", count: 20 },
  { bin: "60-70%", count: 17 },
  { bin: "70-80%", count: 14 },
  { bin: "80-90%", count: 10 },
  { bin: "90-100%", count: 8 },
];

const sharpnessColors = [
  "#ef4444", "#f97316", "#f59e0b", "#eab308", "#84cc16",
  "#22c55e", "#14b8a6", "#06b6d4", "#3b82f6", "#6366f1",
];

export default function CalibrationPage() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-100">Calibration</h1>
        <p className="mt-1 text-sm text-gray-500">
          Assess forecast accuracy and calibration across resolved questions
        </p>
      </div>

      {/* Metric cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          label="Brier Score"
          value="0.182"
          subtitle="0 = perfect, 0.25 = coin flip"
          icon={Target}
          trend={{ value: -8, label: "vs prior period" }}
        />
        <MetricCard
          label="Log Score"
          value="-0.357"
          subtitle="Higher (less negative) is better"
          icon={TrendingUp}
          trend={{ value: 5, label: "improving" }}
        />
        <MetricCard
          label="Calibration Error"
          value="0.034"
          subtitle="Mean absolute deviation from perfect"
          icon={Crosshair}
        />
        <MetricCard
          label="Sharpness"
          value="0.72"
          subtitle="Avg distance from 50%"
          icon={BarChart3}
        />
      </div>

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
        {/* Reliability plot */}
        <section>
          <h2 className="section-heading">Reliability Plot</h2>
          <div className="card">
            <p className="mb-4 text-xs text-gray-500">
              Points on the diagonal indicate perfect calibration. Points above
              the line mean the model is underconfident; below means overconfident.
            </p>
            <CalibrationPlot buckets={mockBuckets} />
          </div>
        </section>

        {/* Sharpness histogram */}
        <section>
          <h2 className="section-heading">Sharpness Distribution</h2>
          <div className="card">
            <p className="mb-4 text-xs text-gray-500">
              Distribution of forecast probabilities. A sharp forecaster pushes
              probabilities toward 0% or 100% rather than clustering near 50%.
            </p>
            <div className="h-80">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={sharpnessData}
                  margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#2d3f5e" />
                  <XAxis
                    dataKey="bin"
                    tick={{ fontSize: 10, fill: "#94a3b8" }}
                    tickLine={false}
                    axisLine={{ stroke: "#2d3f5e" }}
                  />
                  <YAxis
                    tick={{ fontSize: 11, fill: "#94a3b8" }}
                    tickLine={false}
                    axisLine={{ stroke: "#2d3f5e" }}
                    label={{
                      value: "Count",
                      angle: -90,
                      position: "insideLeft",
                      offset: 10,
                      style: { fill: "#64748b", fontSize: 12 },
                    }}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#1e293b",
                      border: "1px solid #2d3f5e",
                      borderRadius: 8,
                      fontSize: 12,
                    }}
                  />
                  <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                    {sharpnessData.map((_entry, index) => (
                      <Cell key={index} fill={sharpnessColors[index]} fillOpacity={0.8} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </section>
      </div>

      {/* Calibration detail table */}
      <section>
        <h2 className="section-heading">Calibration Buckets</h2>
        <div className="overflow-hidden rounded-xl border border-surface-border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-surface-border bg-surface">
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Predicted Range
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Predicted Mean
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Observed Freq.
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Deviation
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Count
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-border">
              {mockBuckets.map((bucket, idx) => {
                const deviation = bucket.observed_frequency - bucket.predicted_mean;
                const absDeviation = Math.abs(deviation);
                return (
                  <tr
                    key={idx}
                    className="bg-surface-raised hover:bg-surface-overlay transition-colors"
                  >
                    <td className="px-4 py-3 text-gray-300 tabular-nums">
                      {(bucket.predicted_low * 100).toFixed(0)}% -{" "}
                      {(bucket.predicted_high * 100).toFixed(0)}%
                    </td>
                    <td className="px-4 py-3 text-gray-300 tabular-nums">
                      {(bucket.predicted_mean * 100).toFixed(0)}%
                    </td>
                    <td className="px-4 py-3 text-gray-300 tabular-nums">
                      {(bucket.observed_frequency * 100).toFixed(0)}%
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`text-xs font-semibold tabular-nums ${
                          absDeviation <= 0.03
                            ? "text-accent-positive"
                            : absDeviation <= 0.06
                              ? "text-accent-warning"
                              : "text-accent-negative"
                        }`}
                      >
                        {deviation >= 0 ? "+" : ""}
                        {(deviation * 100).toFixed(1)}pp
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-400 tabular-nums">
                      {bucket.count}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
