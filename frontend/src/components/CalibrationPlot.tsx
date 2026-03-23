"use client";

import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import clsx from "clsx";
import type { CalibrationBucket } from "@/types";

interface CalibrationPlotProps {
  buckets: CalibrationBucket[];
  className?: string;
}

export default function CalibrationPlot({
  buckets,
  className,
}: CalibrationPlotProps) {
  const data = buckets.map((b) => ({
    predicted: b.predicted_mean,
    observed: b.observed_frequency,
    count: b.count,
  }));

  return (
    <div className={clsx("h-80", className)}>
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 10, right: 10, left: 0, bottom: 10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#2d3f5e" />
          <XAxis
            type="number"
            dataKey="predicted"
            domain={[0, 1]}
            tickFormatter={(v: number) => `${Math.round(v * 100)}%`}
            tick={{ fontSize: 11, fill: "#94a3b8" }}
            tickLine={false}
            axisLine={{ stroke: "#2d3f5e" }}
            name="Predicted"
            label={{
              value: "Predicted Probability",
              position: "insideBottom",
              offset: -5,
              style: { fill: "#64748b", fontSize: 12 },
            }}
          />
          <YAxis
            type="number"
            dataKey="observed"
            domain={[0, 1]}
            tickFormatter={(v: number) => `${Math.round(v * 100)}%`}
            tick={{ fontSize: 11, fill: "#94a3b8" }}
            tickLine={false}
            axisLine={{ stroke: "#2d3f5e" }}
            name="Observed"
            label={{
              value: "Observed Frequency",
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
              `${(value * 100).toFixed(1)}%`,
              name,
            ]}
          />
          {/* Perfect calibration line */}
          <ReferenceLine
            segment={[
              { x: 0, y: 0 },
              { x: 1, y: 1 },
            ]}
            stroke="#64748b"
            strokeDasharray="6 4"
            strokeWidth={1}
          />
          <Scatter
            data={data}
            fill="#3b82f6"
            stroke="#1e40af"
            strokeWidth={1}
            r={6}
          />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}
