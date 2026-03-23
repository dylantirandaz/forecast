"use client";

import Link from "next/link";
import clsx from "clsx";
import { Clock, ArrowUpRight, ArrowDownRight, Minus } from "lucide-react";
import { format } from "date-fns";
import ProbabilityGauge from "./ProbabilityGauge";
import type { Question } from "@/types";

interface ForecastCardProps {
  question: Question;
  probability: number;
  priorProbability: number;
  lastUpdated: string;
  className?: string;
}

export default function ForecastCard({
  question,
  probability,
  priorProbability,
  lastUpdated,
  className,
}: ForecastCardProps) {
  const delta = probability - priorProbability;
  const absDelta = Math.abs(Math.round(delta * 100));

  const TrendIcon =
    delta > 0.01 ? ArrowUpRight : delta < -0.01 ? ArrowDownRight : Minus;
  const trendColor =
    delta > 0.01
      ? "text-accent-positive"
      : delta < -0.01
        ? "text-accent-negative"
        : "text-accent-neutral";

  const statusBadge =
    question.status === "active"
      ? "badge-active"
      : question.status === "resolved"
        ? "badge-resolved"
        : "badge-archived";

  return (
    <Link href={`/questions/${question.id}`}>
      <div className={clsx("card-hover cursor-pointer", className)}>
        <div className="flex items-start justify-between mb-3">
          <span className={statusBadge}>{question.status}</span>
          <span className="text-[10px] text-gray-500 uppercase tracking-wider">
            {question.category}
          </span>
        </div>

        <h3 className="text-sm font-semibold text-gray-100 leading-snug mb-4 line-clamp-2">
          {question.title}
        </h3>

        <ProbabilityGauge probability={probability} size="md" />

        <div className="mt-4 flex items-center justify-between">
          <div className="flex items-center gap-1">
            <TrendIcon className={clsx("h-3.5 w-3.5", trendColor)} />
            <span className={clsx("text-xs font-medium", trendColor)}>
              {absDelta > 0 ? `${absDelta}pp` : "No change"}
            </span>
          </div>
          <div className="flex items-center gap-1 text-gray-500">
            <Clock className="h-3 w-3" />
            <span className="text-[10px]">
              {format(new Date(lastUpdated), "MMM d, h:mm a")}
            </span>
          </div>
        </div>
      </div>
    </Link>
  );
}
