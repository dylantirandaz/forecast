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
  ReferenceLine,
} from "recharts";
import type { ExperimentResult } from "@/types/experiments";

interface AblationChartProps {
  experiments: ExperimentResult[];
  baselineScore?: number;
}

export default function AblationChart({
  experiments,
  baselineScore = 0.185,
}: AblationChartProps) {
  const sorted = [...experiments].sort(
    (a, b) => a.brier_score - b.brier_score
  );

  const minScore = Math.min(...sorted.map((e) => e.brier_score));
  const maxScore = Math.max(...sorted.map((e) => e.brier_score));

  const getBarColor = (score: number) => {
    if (score === minScore) return "#22c55e";
    if (score === maxScore) return "#ef4444";
    const ratio = (score - minScore) / (maxScore - minScore || 1);
    if (ratio < 0.33) return "#4ade80";
    if (ratio < 0.66) return "#f59e0b";
    return "#f87171";
  };

  const data = sorted.map((exp) => ({
    name: exp.name.replace(/_/g, " "),
    brier_score: exp.brier_score,
    log_score: exp.log_score,
    cost: exp.total_cost,
    fullName: exp.name,
  }));

  return (
    <div className="h-96">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 10, right: 30, left: 120, bottom: 10 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#2d3f5e" />
          <XAxis
            type="number"
            domain={[0, "auto"]}
            tick={{ fontSize: 11, fill: "#94a3b8" }}
            tickLine={false}
            axisLine={{ stroke: "#2d3f5e" }}
            label={{
              value: "Brier Score (lower is better)",
              position: "insideBottom",
              offset: -5,
              style: { fill: "#64748b", fontSize: 12 },
            }}
          />
          <YAxis
            dataKey="name"
            type="category"
            tick={{ fontSize: 11, fill: "#94a3b8" }}
            tickLine={false}
            axisLine={{ stroke: "#2d3f5e" }}
            width={115}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "#1e293b",
              border: "1px solid #2d3f5e",
              borderRadius: 8,
              fontSize: 12,
            }}
            formatter={(value: number, _name: string, props: { payload: { cost: number; log_score: number } }) => {
              const { cost, log_score } = props.payload;
              return [
                `Brier: ${value.toFixed(3)} | Log: ${log_score.toFixed(3)} | Cost: $${cost.toFixed(2)}`,
                "",
              ];
            }}
          />
          <ReferenceLine
            x={baselineScore}
            stroke="#6366f1"
            strokeDasharray="6 3"
            strokeWidth={2}
            label={{
              value: "Baseline",
              fill: "#818cf8",
              fontSize: 11,
              position: "top",
            }}
          />
          <Bar dataKey="brier_score" radius={[0, 4, 4, 0]} barSize={18}>
            {data.map((entry, index) => (
              <Cell
                key={index}
                fill={getBarColor(entry.brier_score)}
                fillOpacity={0.85}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
