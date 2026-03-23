"use client";

import clsx from "clsx";
import { format } from "date-fns";
import {
  ArrowUpRight,
  ArrowDownRight,
  Minus,
  Newspaper,
  Database,
  Landmark,
  User,
  BarChart3,
  GraduationCap,
} from "lucide-react";
import type { EvidenceItem } from "@/types";

const sourceIcons: Record<EvidenceItem["source_type"], typeof Newspaper> = {
  news: Newspaper,
  data: Database,
  policy: Landmark,
  expert: User,
  market: BarChart3,
  academic: GraduationCap,
};

const directionConfig = {
  supports: {
    icon: ArrowUpRight,
    color: "text-accent-positive",
    bg: "bg-accent-positive/10",
    border: "border-accent-positive/30",
    label: "Supports",
  },
  opposes: {
    icon: ArrowDownRight,
    color: "text-accent-negative",
    bg: "bg-accent-negative/10",
    border: "border-accent-negative/30",
    label: "Opposes",
  },
  neutral: {
    icon: Minus,
    color: "text-accent-neutral",
    bg: "bg-accent-neutral/10",
    border: "border-accent-neutral/30",
    label: "Neutral",
  },
};

interface EvidenceTimelineProps {
  items: EvidenceItem[];
  className?: string;
}

export default function EvidenceTimeline({
  items,
  className,
}: EvidenceTimelineProps) {
  return (
    <div className={clsx("space-y-0", className)}>
      {items.map((item, idx) => {
        const dir = directionConfig[item.direction];
        const DirIcon = dir.icon;
        const SourceIcon = sourceIcons[item.source_type] || Newspaper;
        const isLast = idx === items.length - 1;

        return (
          <div key={item.id} className="flex gap-4">
            {/* Timeline line + dot */}
            <div className="flex flex-col items-center">
              <div
                className={clsx(
                  "flex h-8 w-8 shrink-0 items-center justify-center rounded-full border",
                  dir.bg,
                  dir.border
                )}
              >
                <DirIcon className={clsx("h-4 w-4", dir.color)} />
              </div>
              {!isLast && (
                <div className="w-px flex-1 bg-surface-border" />
              )}
            </div>

            {/* Content */}
            <div className={clsx("pb-6", isLast && "pb-0")}>
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-gray-100">
                  {item.title}
                </span>
                <span
                  className={clsx(
                    "badge text-[10px]",
                    dir.bg,
                    dir.color
                  )}
                >
                  {dir.label}
                </span>
              </div>

              <p className="mt-1 text-xs text-gray-400 line-clamp-2">
                {item.content}
              </p>

              <div className="mt-2 flex items-center gap-3">
                <div className="flex items-center gap-1 text-gray-500">
                  <SourceIcon className="h-3 w-3" />
                  <span className="text-[10px] capitalize">
                    {item.source_type}
                  </span>
                </div>
                <span className="text-[10px] text-gray-600">
                  {format(new Date(item.published_at), "MMM d, yyyy")}
                </span>
                <div className="flex items-center gap-1">
                  <span className="text-[10px] text-gray-500">Impact:</span>
                  <div className="flex gap-0.5">
                    {[1, 2, 3, 4, 5].map((level) => (
                      <div
                        key={level}
                        className={clsx(
                          "h-1.5 w-3 rounded-sm",
                          level <= Math.round(item.impact_strength * 5)
                            ? dir.color.replace("text-", "bg-")
                            : "bg-gray-700"
                        )}
                      />
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
