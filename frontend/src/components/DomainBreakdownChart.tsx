"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Cell,
} from "recharts";
import clsx from "clsx";

interface DomainMetric {
  domain: string;
  brier: number;
  logScore: number;
  calError: number;
  count: number;
}

interface DomainBreakdownChartProps {
  data: DomainMetric[];
  className?: string;
}

function getBarColor(brier: number): string {
  if (brier < 0.2) return "#22c55e";
  if (brier <= 0.3) return "#eab308";
  return "#ef4444";
}

export default function DomainBreakdownChart({
  data,
  className,
}: DomainBreakdownChartProps) {
  return (
    <div className={clsx("h-80", className)}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 10, right: 20, left: 60, bottom: 10 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#2d3f5e" horizontal={false} />
          <XAxis
            type="number"
            domain={[0, 0.4]}
            tick={{ fontSize: 11, fill: "#94a3b8" }}
            tickLine={false}
            axisLine={{ stroke: "#2d3f5e" }}
            label={{
              value: "Brier Score",
              position: "insideBottom",
              offset: -5,
              style: { fill: "#64748b", fontSize: 12 },
            }}
          />
          <YAxis
            type="category"
            dataKey="domain"
            tick={{ fontSize: 11, fill: "#94a3b8" }}
            tickLine={false}
            axisLine={{ stroke: "#2d3f5e" }}
            width={55}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "#1e293b",
              border: "1px solid #2d3f5e",
              borderRadius: 8,
              fontSize: 12,
            }}
            formatter={(value: number, name: string) => {
              if (name === "brier") return [value.toFixed(3), "Brier Score"];
              return [value, name];
            }}
            labelFormatter={(label: string) => `Domain: ${label}`}
            cursor={{ fill: "rgba(255,255,255,0.03)" }}
          />
          <ReferenceLine
            x={0.25}
            stroke="#ef4444"
            strokeDasharray="6 4"
            strokeWidth={1}
            label={{
              value: "Always 0.5",
              position: "top",
              style: { fill: "#ef4444", fontSize: 10 },
            }}
          />
          <Bar dataKey="brier" radius={[0, 4, 4, 0]} barSize={20}>
            {data.map((entry, index) => (
              <Cell key={index} fill={getBarColor(entry.brier)} fillOpacity={0.8} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
