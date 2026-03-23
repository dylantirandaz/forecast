"use client";

import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Line,
  Label,
} from "recharts";
import type { ExperimentResult } from "@/types/experiments";

interface CostPerformanceScatterProps {
  experiments: ExperimentResult[];
}

function computeParetoFrontier(
  points: { cost: number; brier: number; name: string }[]
) {
  const sorted = [...points].sort((a, b) => a.cost - b.cost);
  const frontier: typeof sorted = [];
  let bestBrier = Infinity;

  for (const p of sorted) {
    if (p.brier <= bestBrier) {
      frontier.push(p);
      bestBrier = p.brier;
    }
  }
  return frontier;
}

interface CustomDotProps {
  cx?: number;
  cy?: number;
  payload?: { name: string; cost: number; brier: number };
}

const CustomDot = ({ cx, cy, payload }: CustomDotProps) => {
  if (!cx || !cy || !payload) return null;
  return (
    <g>
      <circle cx={cx} cy={cy} r={6} fill="#6366f1" fillOpacity={0.8} stroke="#818cf8" strokeWidth={1.5} />
      <text x={cx + 10} y={cy - 8} fill="#94a3b8" fontSize={10}>
        {payload.name.replace(/_/g, " ").slice(0, 16)}
      </text>
    </g>
  );
};

export default function CostPerformanceScatter({
  experiments,
}: CostPerformanceScatterProps) {
  const data = experiments.map((exp) => ({
    cost: exp.total_cost,
    brier: exp.brier_score,
    name: exp.name,
  }));

  const frontier = computeParetoFrontier(data);

  return (
    <div className="h-80">
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 20, right: 30, left: 10, bottom: 20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#2d3f5e" />
          <XAxis
            type="number"
            dataKey="cost"
            tick={{ fontSize: 11, fill: "#94a3b8" }}
            tickLine={false}
            axisLine={{ stroke: "#2d3f5e" }}
            tickFormatter={(v: number) => `$${v.toFixed(1)}`}
          >
            <Label
              value="Cost (USD)"
              position="insideBottom"
              offset={-10}
              style={{ fill: "#64748b", fontSize: 12 }}
            />
          </XAxis>
          <YAxis
            type="number"
            dataKey="brier"
            tick={{ fontSize: 11, fill: "#94a3b8" }}
            tickLine={false}
            axisLine={{ stroke: "#2d3f5e" }}
            reversed
          >
            <Label
              value="Brier Score (lower = better)"
              angle={-90}
              position="insideLeft"
              offset={5}
              style={{ fill: "#64748b", fontSize: 12 }}
            />
          </YAxis>
          <Tooltip
            contentStyle={{
              backgroundColor: "#1e293b",
              border: "1px solid #2d3f5e",
              borderRadius: 8,
              fontSize: 12,
            }}
            formatter={(value: number, name: string) => {
              if (name === "brier") return [value.toFixed(3), "Brier Score"];
              return [`$${value.toFixed(2)}`, "Cost"];
            }}
            labelFormatter={(_, payload) => {
              if (payload?.[0]?.payload?.name) {
                return payload[0].payload.name.replace(/_/g, " ");
              }
              return "";
            }}
          />
          <Scatter data={data} shape={<CustomDot />} />
          {/* Pareto frontier as a line overlay */}
          <Scatter
            data={frontier}
            line={{ stroke: "#22c55e", strokeWidth: 2, strokeDasharray: "6 3" }}
            shape={() => <></>}
            legendType="none"
          />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}
