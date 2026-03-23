"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Area,
  ReferenceLine,
} from "recharts";
import clsx from "clsx";

interface HorizonDataPoint {
  horizon: string;
  model: number;
  baseline: number;
  upper?: number;
  lower?: number;
}

interface HorizonChartProps {
  data: HorizonDataPoint[];
  className?: string;
}

export default function HorizonChart({ data, className }: HorizonChartProps) {
  return (
    <div className={clsx("h-80", className)}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart
          data={data}
          margin={{ top: 10, right: 20, left: 0, bottom: 10 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#2d3f5e" />
          <XAxis
            dataKey="horizon"
            tick={{ fontSize: 11, fill: "#94a3b8" }}
            tickLine={false}
            axisLine={{ stroke: "#2d3f5e" }}
            label={{
              value: "Horizon",
              position: "insideBottom",
              offset: -5,
              style: { fill: "#64748b", fontSize: 12 },
            }}
          />
          <YAxis
            domain={[0, 0.35]}
            tick={{ fontSize: 11, fill: "#94a3b8" }}
            tickLine={false}
            axisLine={{ stroke: "#2d3f5e" }}
            label={{
              value: "Brier Score",
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
            formatter={(value: number, name: string) => [
              value.toFixed(3),
              name === "model" ? "Model" : "Always 0.5 Baseline",
            ]}
          />
          <ReferenceLine
            y={0.25}
            stroke="#ef4444"
            strokeDasharray="6 4"
            strokeWidth={1}
            label={{
              value: "Coin flip",
              position: "right",
              style: { fill: "#ef4444", fontSize: 10 },
            }}
          />
          {/* Confidence band */}
          <Area
            dataKey="upper"
            stroke="none"
            fill="#3b82f6"
            fillOpacity={0.1}
          />
          <Area
            dataKey="lower"
            stroke="none"
            fill="#3b82f6"
            fillOpacity={0.1}
          />
          <Line
            type="monotone"
            dataKey="model"
            stroke="#3b82f6"
            strokeWidth={2}
            dot={{ r: 5, fill: "#3b82f6", stroke: "#1e40af" }}
            name="model"
          />
          <Line
            type="monotone"
            dataKey="baseline"
            stroke="#ef4444"
            strokeWidth={1.5}
            strokeDasharray="5 5"
            dot={{ r: 4, fill: "#ef4444", stroke: "#991b1b" }}
            name="baseline"
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
