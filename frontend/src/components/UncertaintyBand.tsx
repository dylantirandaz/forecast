"use client";

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Line,
} from "recharts";
import clsx from "clsx";

interface UncertaintyBandProps {
  data: {
    date: string;
    posterior: number;
    lower: number;
    upper: number;
  }[];
  className?: string;
}

export default function UncertaintyBand({
  data,
  className,
}: UncertaintyBandProps) {
  return (
    <div className={clsx("h-72", className)}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart
          data={data}
          margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
        >
          <defs>
            <linearGradient id="bandGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.3} />
              <stop offset="100%" stopColor="#3b82f6" stopOpacity={0.02} />
            </linearGradient>
          </defs>
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
            labelStyle={{ color: "#94a3b8" }}
            formatter={(value: number) => `${(value * 100).toFixed(1)}%`}
          />
          <Area
            type="monotone"
            dataKey="upper"
            stroke="none"
            fill="url(#bandGradient)"
            fillOpacity={1}
          />
          <Area
            type="monotone"
            dataKey="lower"
            stroke="none"
            fill="#0f1729"
            fillOpacity={1}
          />
          <Area
            type="monotone"
            dataKey="posterior"
            stroke="#3b82f6"
            strokeWidth={2}
            fill="none"
            dot={{ r: 3, fill: "#3b82f6", stroke: "#0f1729", strokeWidth: 2 }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
