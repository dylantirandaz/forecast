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
import clsx from "clsx";

interface HistogramBin {
  bin: string;
  count: number;
}

interface PredictionHistogramProps {
  data: HistogramBin[];
  className?: string;
}

const gradientColors = [
  "#ef4444",
  "#f97316",
  "#f59e0b",
  "#eab308",
  "#84cc16",
  "#22c55e",
  "#14b8a6",
  "#06b6d4",
  "#3b82f6",
  "#6366f1",
];

export default function PredictionHistogram({
  data,
  className,
}: PredictionHistogramProps) {
  return (
    <div className={clsx("h-80", className)}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={data}
          margin={{ top: 10, right: 10, left: 0, bottom: 10 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#2d3f5e" />
          <XAxis
            dataKey="bin"
            tick={{ fontSize: 10, fill: "#94a3b8" }}
            tickLine={false}
            axisLine={{ stroke: "#2d3f5e" }}
            label={{
              value: "Prediction Probability",
              position: "insideBottom",
              offset: -5,
              style: { fill: "#64748b", fontSize: 12 },
            }}
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
            {data.map((_entry, index) => (
              <Cell
                key={index}
                fill={gradientColors[index % gradientColors.length]}
                fillOpacity={0.8}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
