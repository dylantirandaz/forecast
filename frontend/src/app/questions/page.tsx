"use client";

import { useState } from "react";
import Link from "next/link";
import clsx from "clsx";
import { Search, Filter, Plus } from "lucide-react";
import { format } from "date-fns";
import ProbabilityGauge from "@/components/ProbabilityGauge";
import type { Question } from "@/types";

const mockQuestions: (Question & { probability: number })[] = [
  {
    id: "q1",
    title: "Will NYC median rent exceed $4,000/mo by Q4 2026?",
    description: "Tracks whether citywide median asking rent crosses the $4,000 threshold.",
    category: "Rental Market",
    resolution_date: "2026-12-31",
    created_at: "2025-09-01T00:00:00Z",
    updated_at: "2026-03-20T14:30:00Z",
    status: "active",
    resolution_criteria: "StreetEasy median asking rent for NYC exceeds $4,000 in any month of Q4 2026.",
    tags: ["rent", "affordability"],
    probability: 0.42,
  },
  {
    id: "q2",
    title: "Will Good Cause Eviction law significantly reduce eviction filings?",
    description: "Measures whether eviction filings drop 20%+ YoY after implementation.",
    category: "Policy",
    resolution_date: "2027-06-30",
    created_at: "2025-10-15T00:00:00Z",
    updated_at: "2026-03-19T09:15:00Z",
    status: "active",
    resolution_criteria: "NYC Housing Court eviction filings decline by 20% or more year-over-year.",
    tags: ["policy", "eviction"],
    probability: 0.58,
  },
  {
    id: "q3",
    title: "Will NYC housing starts exceed 30,000 units in 2026?",
    description: "Tracks new residential construction permit issuance citywide.",
    category: "Supply",
    resolution_date: "2027-03-31",
    created_at: "2025-11-01T00:00:00Z",
    updated_at: "2026-03-18T16:45:00Z",
    status: "active",
    resolution_criteria: "Census Bureau data shows 30,000+ housing unit permits issued in NYC in CY 2026.",
    tags: ["construction", "supply"],
    probability: 0.28,
  },
  {
    id: "q4",
    title: "Will 421-a replacement incentive program be enacted by mid-2026?",
    description: "Tracks legislative action on a successor to the 421-a tax abatement.",
    category: "Policy",
    resolution_date: "2026-06-30",
    created_at: "2025-08-15T00:00:00Z",
    updated_at: "2026-03-21T11:00:00Z",
    status: "active",
    resolution_criteria: "Governor signs legislation creating a successor affordable housing tax incentive program.",
    tags: ["tax-incentive", "421a"],
    probability: 0.65,
  },
  {
    id: "q5",
    title: "Will Manhattan office vacancy rate fall below 15% by end of 2026?",
    description: "Monitors office vacancy trend and potential conversion impacts on housing.",
    category: "Commercial",
    resolution_date: "2026-12-31",
    created_at: "2025-12-01T00:00:00Z",
    updated_at: "2026-03-17T08:30:00Z",
    status: "active",
    resolution_criteria: "CBRE or JLL quarterly report shows Manhattan office vacancy below 15%.",
    tags: ["office", "vacancy"],
    probability: 0.22,
  },
  {
    id: "q6",
    title: "Will City of Yes housing reforms produce 10,000+ new units in pipeline by 2027?",
    description: "Tracks impact of zoning text amendments on permitted housing units.",
    category: "Zoning",
    resolution_date: "2027-06-30",
    created_at: "2026-01-10T00:00:00Z",
    updated_at: "2026-03-20T10:00:00Z",
    status: "active",
    resolution_criteria: "DCP reports 10,000+ units in projects utilizing City of Yes provisions.",
    tags: ["zoning", "city-of-yes"],
    probability: 0.48,
  },
  {
    id: "q7",
    title: "Did remote work stabilize NYC residential migration outflows?",
    description: "Assessed whether net domestic migration from NYC stabilized by end of 2025.",
    category: "Demographics",
    resolution_date: "2026-01-31",
    created_at: "2025-06-01T00:00:00Z",
    updated_at: "2026-02-01T12:00:00Z",
    status: "resolved",
    resolution_criteria: "Census / IRS data shows net outflow reduced to pre-pandemic levels.",
    tags: ["migration", "remote-work"],
    probability: 0.72,
  },
];

const categories = ["All", "Rental Market", "Policy", "Supply", "Commercial", "Zoning", "Demographics"];
const statuses = ["all", "active", "resolved", "archived"] as const;

export default function QuestionsPage() {
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("All");
  const [status, setStatus] = useState<(typeof statuses)[number]>("all");

  const filtered = mockQuestions.filter((q) => {
    const matchesSearch =
      search === "" ||
      q.title.toLowerCase().includes(search.toLowerCase()) ||
      q.description.toLowerCase().includes(search.toLowerCase());
    const matchesCat = category === "All" || q.category === category;
    const matchesStatus = status === "all" || q.status === status;
    return matchesSearch && matchesCat && matchesStatus;
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">Questions</h1>
          <p className="mt-1 text-sm text-gray-500">
            Manage and monitor forecast questions
          </p>
        </div>
        <button className="flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-brand-700 transition-colors">
          <Plus className="h-4 w-4" />
          New Question
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[240px] max-w-md">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-500" />
          <input
            type="text"
            placeholder="Search questions..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-lg border border-surface-border bg-surface-raised py-2.5 pl-10 pr-4 text-sm text-gray-100 placeholder-gray-500 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
          />
        </div>
        <div className="flex gap-1.5">
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => setCategory(cat)}
              className={clsx(
                "rounded-lg px-3 py-2 text-xs font-medium transition-colors",
                cat === category
                  ? "bg-brand-600/15 text-brand-400"
                  : "text-gray-500 hover:bg-surface-overlay hover:text-gray-300"
              )}
            >
              {cat}
            </button>
          ))}
        </div>
        <div className="flex gap-1.5 border-l border-surface-border pl-3">
          {statuses.map((s) => (
            <button
              key={s}
              onClick={() => setStatus(s)}
              className={clsx(
                "rounded-lg px-3 py-2 text-xs font-medium capitalize transition-colors",
                s === status
                  ? "bg-brand-600/15 text-brand-400"
                  : "text-gray-500 hover:bg-surface-overlay hover:text-gray-300"
              )}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {/* Questions table */}
      <div className="overflow-hidden rounded-xl border border-surface-border">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-surface-border bg-surface">
              <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                Question
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                Category
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                Status
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500 w-44">
                Probability
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                Resolution Date
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                Updated
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-surface-border">
            {filtered.map((q) => (
              <tr
                key={q.id}
                className="bg-surface-raised hover:bg-surface-overlay transition-colors"
              >
                <td className="px-4 py-3">
                  <Link
                    href={`/questions/${q.id}`}
                    className="font-medium text-gray-100 hover:text-brand-400 transition-colors"
                  >
                    {q.title}
                  </Link>
                  <p className="mt-0.5 text-xs text-gray-500 line-clamp-1">
                    {q.description}
                  </p>
                </td>
                <td className="px-4 py-3">
                  <span className="badge bg-surface border border-surface-border text-gray-400">
                    {q.category}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <span
                    className={
                      q.status === "active"
                        ? "badge-active"
                        : q.status === "resolved"
                          ? "badge-resolved"
                          : "badge-archived"
                    }
                  >
                    {q.status}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <ProbabilityGauge
                    probability={q.probability}
                    size="sm"
                  />
                </td>
                <td className="px-4 py-3 text-xs text-gray-400 tabular-nums">
                  {format(new Date(q.resolution_date), "MMM d, yyyy")}
                </td>
                <td className="px-4 py-3 text-xs text-gray-500 tabular-nums">
                  {format(new Date(q.updated_at), "MMM d")}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {filtered.length === 0 && (
          <div className="py-12 text-center text-sm text-gray-500">
            No questions match your filters.
          </div>
        )}
      </div>
    </div>
  );
}
