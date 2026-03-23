"use client";

import clsx from "clsx";

interface ProbabilityGaugeProps {
  probability: number;
  size?: "sm" | "md" | "lg";
  showLabel?: boolean;
  className?: string;
}

function getColor(p: number): string {
  if (p < 0.2) return "text-probability-veryLow";
  if (p < 0.4) return "text-probability-low";
  if (p < 0.6) return "text-probability-medium";
  if (p < 0.8) return "text-probability-high";
  return "text-probability-veryHigh";
}

function getBgColor(p: number): string {
  if (p < 0.2) return "bg-probability-veryLow";
  if (p < 0.4) return "bg-probability-low";
  if (p < 0.6) return "bg-probability-medium";
  if (p < 0.8) return "bg-probability-high";
  return "bg-probability-veryHigh";
}

function getTrackColor(p: number): string {
  if (p < 0.2) return "bg-probability-veryLow/20";
  if (p < 0.4) return "bg-probability-low/20";
  if (p < 0.6) return "bg-probability-medium/20";
  if (p < 0.8) return "bg-probability-high/20";
  return "bg-probability-veryHigh/20";
}

const sizeConfig = {
  sm: { text: "text-lg", bar: "h-1.5" },
  md: { text: "text-2xl", bar: "h-2" },
  lg: { text: "text-4xl", bar: "h-3" },
};

export default function ProbabilityGauge({
  probability,
  size = "md",
  showLabel = true,
  className,
}: ProbabilityGaugeProps) {
  const pct = Math.round(probability * 100);
  const cfg = sizeConfig[size];

  return (
    <div className={clsx("space-y-1.5", className)}>
      {showLabel && (
        <div className="flex items-baseline gap-1">
          <span className={clsx("font-bold tabular-nums", cfg.text, getColor(probability))}>
            {pct}%
          </span>
        </div>
      )}
      <div className={clsx("w-full rounded-full overflow-hidden", cfg.bar, getTrackColor(probability))}>
        <div
          className={clsx("h-full rounded-full transition-all duration-500", getBgColor(probability))}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
