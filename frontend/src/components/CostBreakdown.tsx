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
  PieChart,
  Pie,
} from "recharts";

interface CostBreakdownProps {
  costByOperation: Record<string, number>;
  costByTier: Record<string, number>;
}

const TIER_COLORS: Record<string, string> = {
  "Tier A": "#22c55e",
  "Tier B": "#f59e0b",
  "Tier C": "#3b82f6",
  Other: "#6b7280",
};

const OP_COLORS = ["#6366f1", "#8b5cf6", "#a78bfa", "#c4b5fd", "#ddd6fe"];

interface PieLabelProps {
  cx: number;
  cy: number;
  midAngle: number;
  innerRadius: number;
  outerRadius: number;
  percent: number;
  name: string;
}

const renderLabel = ({
  cx,
  cy,
  midAngle,
  innerRadius,
  outerRadius,
  percent,
  name,
}: PieLabelProps) => {
  const RADIAN = Math.PI / 180;
  const radius = innerRadius + (outerRadius - innerRadius) * 1.4;
  const x = cx + radius * Math.cos(-midAngle * RADIAN);
  const y = cy + radius * Math.sin(-midAngle * RADIAN);

  return (
    <text
      x={x}
      y={y}
      fill="#94a3b8"
      textAnchor={x > cx ? "start" : "end"}
      dominantBaseline="central"
      fontSize={11}
    >
      {name} ({(percent * 100).toFixed(0)}%)
    </text>
  );
};

export default function CostBreakdown({
  costByOperation,
  costByTier,
}: CostBreakdownProps) {
  const opData = Object.entries(costByOperation).map(([name, value]) => ({
    name: name.replace(/_/g, " "),
    value: Number(value.toFixed(2)),
  }));

  const tierData = Object.entries(costByTier).map(([name, value]) => ({
    name,
    value: Number(value.toFixed(2)),
  }));

  return (
    <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
      {/* Cost by Operation - Pie Chart */}
      <div>
        <h3 className="mb-3 text-sm font-semibold text-gray-300">
          Cost by Operation
        </h3>
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={opData}
                cx="50%"
                cy="50%"
                outerRadius={90}
                dataKey="value"
                label={renderLabel}
              >
                {opData.map((_entry, index) => (
                  <Cell
                    key={index}
                    fill={OP_COLORS[index % OP_COLORS.length]}
                    fillOpacity={0.85}
                  />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  backgroundColor: "#1e293b",
                  border: "1px solid #2d3f5e",
                  borderRadius: 8,
                  fontSize: 12,
                }}
                formatter={(value: number) => [`$${value.toFixed(2)}`, "Cost"]}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Cost by Model Tier - Horizontal Bar */}
      <div>
        <h3 className="mb-3 text-sm font-semibold text-gray-300">
          Cost by Model Tier
        </h3>
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={tierData}
              layout="vertical"
              margin={{ top: 10, right: 30, left: 60, bottom: 10 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#2d3f5e" />
              <XAxis
                type="number"
                tick={{ fontSize: 11, fill: "#94a3b8" }}
                tickLine={false}
                axisLine={{ stroke: "#2d3f5e" }}
                tickFormatter={(v: number) => `$${v}`}
              />
              <YAxis
                dataKey="name"
                type="category"
                tick={{ fontSize: 12, fill: "#94a3b8" }}
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
                formatter={(value: number) => [`$${value.toFixed(2)}`, "Cost"]}
              />
              <Bar dataKey="value" radius={[0, 4, 4, 0]} barSize={24}>
                {tierData.map((entry, index) => (
                  <Cell
                    key={index}
                    fill={TIER_COLORS[entry.name] || "#6b7280"}
                    fillOpacity={0.85}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
