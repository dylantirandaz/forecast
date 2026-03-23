"use client";

import clsx from "clsx";
import ProbabilityGauge from "./ProbabilityGauge";
import type { Scenario } from "@/types";

interface ScenarioComparisonProps {
  scenarios: Scenario[];
  className?: string;
}

export default function ScenarioComparison({
  scenarios,
  className,
}: ScenarioComparisonProps) {
  const sorted = [...scenarios].sort((a, b) => b.probability - a.probability);

  return (
    <div className={clsx("overflow-hidden rounded-xl border border-surface-border", className)}>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-surface-border bg-surface">
            <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
              Scenario
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
              Prior
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
              Posterior
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
              Shift
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
              Key Conditions
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-surface-border">
          {sorted.map((scenario) => {
            const shift = scenario.probability - scenario.prior_probability;
            const shiftPp = Math.round(shift * 100);
            return (
              <tr
                key={scenario.id}
                className="bg-surface-raised hover:bg-surface-overlay transition-colors"
              >
                <td className="px-4 py-3">
                  <div>
                    <p className="font-medium text-gray-100">
                      {scenario.name}
                    </p>
                    <p className="text-xs text-gray-500 line-clamp-1">
                      {scenario.description}
                    </p>
                  </div>
                </td>
                <td className="px-4 py-3">
                  <span className="text-gray-400 tabular-nums">
                    {Math.round(scenario.prior_probability * 100)}%
                  </span>
                </td>
                <td className="px-4 py-3 w-40">
                  <ProbabilityGauge
                    probability={scenario.probability}
                    size="sm"
                  />
                </td>
                <td className="px-4 py-3">
                  <span
                    className={clsx(
                      "text-xs font-semibold tabular-nums",
                      shiftPp > 0
                        ? "text-accent-positive"
                        : shiftPp < 0
                          ? "text-accent-negative"
                          : "text-accent-neutral"
                    )}
                  >
                    {shiftPp > 0 ? "+" : ""}
                    {shiftPp}pp
                  </span>
                </td>
                <td className="px-4 py-3">
                  <div className="flex flex-wrap gap-1">
                    {scenario.conditions.slice(0, 3).map((c, i) => (
                      <span
                        key={i}
                        className="badge bg-surface border border-surface-border text-gray-400"
                      >
                        {c}
                      </span>
                    ))}
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
