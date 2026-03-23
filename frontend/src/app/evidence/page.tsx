"use client";

import { useState } from "react";
import clsx from "clsx";
import { format } from "date-fns";
import {
  Search,
  ArrowUpRight,
  ArrowDownRight,
  Minus,
  ExternalLink,
  Newspaper,
  Database,
  Landmark,
  User,
  BarChart3,
  GraduationCap,
} from "lucide-react";
import type { EvidenceItem } from "@/types";

const sourceIcons: Record<string, typeof Newspaper> = {
  news: Newspaper,
  data: Database,
  policy: Landmark,
  expert: User,
  market: BarChart3,
  academic: GraduationCap,
};

const mockEvidence: EvidenceItem[] = [
  {
    id: "e1",
    question_id: "q1",
    title: "February rent data shows 3.2% MoM increase",
    source: "StreetEasy Market Report",
    source_type: "data",
    content: "Median asking rent hit $3,812 in February 2026, up 3.2% from January. This is the largest month-over-month jump since mid-2022, driven by low inventory and strong demand.",
    published_at: "2026-03-15T00:00:00Z",
    ingested_at: "2026-03-15T14:00:00Z",
    direction: "supports",
    impact_strength: 0.8,
    relevance_score: 0.95,
    url: "https://streeteasy.com/blog/market-report",
  },
  {
    id: "e2",
    question_id: "q1",
    title: "City of Yes expected to add 5,000 units to near-term pipeline",
    source: "NYC DCP Quarterly Report",
    source_type: "policy",
    content: "New zoning provisions have generated permits for approximately 5,000 additional units, with most expected to reach market in 2027-2028 timeframe.",
    published_at: "2026-03-10T00:00:00Z",
    ingested_at: "2026-03-10T09:00:00Z",
    direction: "opposes",
    impact_strength: 0.4,
    relevance_score: 0.7,
  },
  {
    id: "e3",
    question_id: "q1",
    title: "Tech layoffs reduce high-income renter demand in Manhattan",
    source: "Bloomberg",
    source_type: "news",
    content: "Three major tech firms announced layoffs affecting ~2,500 NYC-based employees, potentially dampening demand in luxury rental segments downtown and in Brooklyn waterfront.",
    published_at: "2026-03-05T00:00:00Z",
    ingested_at: "2026-03-05T16:00:00Z",
    direction: "opposes",
    impact_strength: 0.3,
    relevance_score: 0.6,
  },
  {
    id: "e4",
    question_id: "q2",
    title: "Good Cause Eviction pilot data from Albany shows 12% filing drop",
    source: "FURMAN Center Brief",
    source_type: "academic",
    content: "Analysis of eviction filings in Albany County, where a local good cause law has been in effect, shows a 12% year-over-year decline in new eviction petitions filed.",
    published_at: "2026-03-08T00:00:00Z",
    ingested_at: "2026-03-08T10:00:00Z",
    direction: "supports",
    impact_strength: 0.7,
    relevance_score: 0.8,
  },
  {
    id: "e5",
    question_id: "q4",
    title: "Senate housing committee advances 421-a successor bill",
    source: "Politico NY",
    source_type: "news",
    content: "The NY State Senate housing committee voted 8-3 to advance the Affordable Neighborhoods for New Yorkers (ANNY) program, a modified successor to the expired 421-a tax incentive.",
    published_at: "2026-03-18T00:00:00Z",
    ingested_at: "2026-03-18T13:00:00Z",
    direction: "supports",
    impact_strength: 0.9,
    relevance_score: 0.95,
  },
  {
    id: "e6",
    question_id: "q3",
    title: "Construction financing costs remain elevated despite rate pause",
    source: "Real Capital Analytics",
    source_type: "market",
    content: "Average construction loan rates for NYC multifamily projects remain at 7.8%, with lenders requiring higher equity contributions. Several planned projects have paused.",
    published_at: "2026-03-12T00:00:00Z",
    ingested_at: "2026-03-12T11:00:00Z",
    direction: "opposes",
    impact_strength: 0.6,
    relevance_score: 0.85,
  },
  {
    id: "e7",
    question_id: "q1",
    title: "Immigration inflows drive outer-borough rental demand",
    source: "NYC Comptroller Analysis",
    source_type: "data",
    content: "New arrivals concentrated in Brooklyn, Queens, and Bronx neighborhoods are increasing competition for mid-market rentals, pushing up median rents citywide.",
    published_at: "2026-02-28T00:00:00Z",
    ingested_at: "2026-02-28T11:00:00Z",
    direction: "supports",
    impact_strength: 0.6,
    relevance_score: 0.85,
  },
  {
    id: "e8",
    question_id: "q5",
    title: "Major office-to-residential conversion approved at 25 Water St",
    source: "The Real Deal",
    source_type: "news",
    content: "The city approved plans to convert the 1.1M sq ft office tower at 25 Water Street into 1,300 rental apartments, the largest single conversion project to date.",
    published_at: "2026-03-01T00:00:00Z",
    ingested_at: "2026-03-01T09:30:00Z",
    direction: "supports",
    impact_strength: 0.5,
    relevance_score: 0.75,
  },
  {
    id: "e9",
    question_id: "q2",
    title: "Landlord associations challenge Good Cause law in court",
    source: "NY Law Journal",
    source_type: "policy",
    content: "RSA and REBNY filed suit in state court arguing the Good Cause Eviction law exceeds legislative authority. A preliminary injunction hearing is set for April.",
    published_at: "2026-03-20T00:00:00Z",
    ingested_at: "2026-03-20T15:00:00Z",
    direction: "opposes",
    impact_strength: 0.5,
    relevance_score: 0.9,
  },
  {
    id: "e10",
    question_id: "q6",
    title: "Expert panel estimates City of Yes will yield 58,000-82,000 units over 15 years",
    source: "Regional Plan Association",
    source_type: "expert",
    content: "RPA convened modeling exercise projects that the full buildout under City of Yes could yield 58,000-82,000 net new units, but with significant front-loading uncertainty.",
    published_at: "2026-02-25T00:00:00Z",
    ingested_at: "2026-02-25T14:00:00Z",
    direction: "neutral",
    impact_strength: 0.4,
    relevance_score: 0.7,
  },
];

const sourceTypes = ["all", "news", "data", "policy", "expert", "market", "academic"];
const directions = ["all", "supports", "opposes", "neutral"];

const dirConfig = {
  supports: { icon: ArrowUpRight, color: "text-accent-positive", bg: "bg-accent-positive/10" },
  opposes: { icon: ArrowDownRight, color: "text-accent-negative", bg: "bg-accent-negative/10" },
  neutral: { icon: Minus, color: "text-accent-neutral", bg: "bg-accent-neutral/10" },
};

export default function EvidencePage() {
  const [search, setSearch] = useState("");
  const [sourceFilter, setSourceFilter] = useState("all");
  const [directionFilter, setDirectionFilter] = useState("all");

  const filtered = mockEvidence.filter((e) => {
    const matchesSearch =
      search === "" ||
      e.title.toLowerCase().includes(search.toLowerCase()) ||
      e.content.toLowerCase().includes(search.toLowerCase());
    const matchesSource = sourceFilter === "all" || e.source_type === sourceFilter;
    const matchesDir = directionFilter === "all" || e.direction === directionFilter;
    return matchesSearch && matchesSource && matchesDir;
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-100">Evidence Explorer</h1>
        <p className="mt-1 text-sm text-gray-500">
          Browse and filter evidence items across all forecast questions
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[240px] max-w-md">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-500" />
          <input
            type="text"
            placeholder="Search evidence..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-lg border border-surface-border bg-surface-raised py-2.5 pl-10 pr-4 text-sm text-gray-100 placeholder-gray-500 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
          />
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-500">Source:</span>
          <div className="flex gap-1">
            {sourceTypes.map((st) => (
              <button
                key={st}
                onClick={() => setSourceFilter(st)}
                className={clsx(
                  "rounded-lg px-2.5 py-1.5 text-xs font-medium capitalize transition-colors",
                  st === sourceFilter
                    ? "bg-brand-600/15 text-brand-400"
                    : "text-gray-500 hover:bg-surface-overlay hover:text-gray-300"
                )}
              >
                {st}
              </button>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-2 border-l border-surface-border pl-3">
          <span className="text-xs text-gray-500">Direction:</span>
          <div className="flex gap-1">
            {directions.map((d) => (
              <button
                key={d}
                onClick={() => setDirectionFilter(d)}
                className={clsx(
                  "rounded-lg px-2.5 py-1.5 text-xs font-medium capitalize transition-colors",
                  d === directionFilter
                    ? "bg-brand-600/15 text-brand-400"
                    : "text-gray-500 hover:bg-surface-overlay hover:text-gray-300"
                )}
              >
                {d}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Results count */}
      <p className="text-xs text-gray-500">
        Showing {filtered.length} of {mockEvidence.length} evidence items
      </p>

      {/* Evidence cards */}
      <div className="space-y-3">
        {filtered.map((item) => {
          const dir = dirConfig[item.direction];
          const DirIcon = dir.icon;
          const SourceIcon = sourceIcons[item.source_type] || Newspaper;

          return (
            <div key={item.id} className="card-hover">
              <div className="flex items-start gap-4">
                {/* Direction indicator */}
                <div
                  className={clsx(
                    "flex h-10 w-10 shrink-0 items-center justify-center rounded-lg",
                    dir.bg
                  )}
                >
                  <DirIcon className={clsx("h-5 w-5", dir.color)} />
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-4">
                    <h3 className="text-sm font-semibold text-gray-100">
                      {item.title}
                    </h3>
                    {item.url && (
                      <a
                        href={item.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="shrink-0 text-gray-500 hover:text-brand-400 transition-colors"
                      >
                        <ExternalLink className="h-4 w-4" />
                      </a>
                    )}
                  </div>

                  <p className="mt-1 text-xs text-gray-400 line-clamp-2">
                    {item.content}
                  </p>

                  <div className="mt-3 flex flex-wrap items-center gap-4">
                    <div className="flex items-center gap-1.5 text-gray-500">
                      <SourceIcon className="h-3.5 w-3.5" />
                      <span className="text-xs">{item.source}</span>
                    </div>
                    <span className="text-xs text-gray-600">
                      {format(new Date(item.published_at), "MMM d, yyyy")}
                    </span>
                    <span
                      className={clsx(
                        "badge text-[10px] capitalize",
                        dir.bg,
                        dir.color
                      )}
                    >
                      {item.direction}
                    </span>

                    {/* Impact strength bar */}
                    <div className="flex items-center gap-1.5">
                      <span className="text-[10px] text-gray-500">Impact:</span>
                      <div className="flex gap-0.5">
                        {[1, 2, 3, 4, 5].map((level) => (
                          <div
                            key={level}
                            className={clsx(
                              "h-2 w-4 rounded-sm",
                              level <= Math.round(item.impact_strength * 5)
                                ? "bg-brand-500"
                                : "bg-gray-700"
                            )}
                          />
                        ))}
                      </div>
                    </div>

                    {/* Relevance score */}
                    <div className="flex items-center gap-1.5">
                      <span className="text-[10px] text-gray-500">Relevance:</span>
                      <span className="text-xs font-medium text-gray-300 tabular-nums">
                        {(item.relevance_score * 100).toFixed(0)}%
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {filtered.length === 0 && (
        <div className="card py-12 text-center text-sm text-gray-500">
          No evidence items match your filters.
        </div>
      )}
    </div>
  );
}
