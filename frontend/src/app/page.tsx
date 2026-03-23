"use client";

import {
  Activity,
  Target,
  TrendingUp,
  FileSearch,
  ArrowUpRight,
  ArrowDownRight,
  Minus,
} from "lucide-react";
import { format } from "date-fns";
import clsx from "clsx";
import MetricCard from "@/components/MetricCard";
import ForecastCard from "@/components/ForecastCard";
import ProbabilityGauge from "@/components/ProbabilityGauge";
import type { Question, ForecastUpdate } from "@/types";

// ── Mock data ───────────────────────────────────────────────────────

const mockQuestions: (Question & {
  probability: number;
  priorProbability: number;
  lastUpdated: string;
})[] = [
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
    priorProbability: 0.35,
    lastUpdated: "2026-03-20T14:30:00Z",
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
    tags: ["policy", "eviction", "tenant-protection"],
    probability: 0.58,
    priorProbability: 0.55,
    lastUpdated: "2026-03-19T09:15:00Z",
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
    tags: ["construction", "supply", "permits"],
    probability: 0.28,
    priorProbability: 0.34,
    lastUpdated: "2026-03-18T16:45:00Z",
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
    tags: ["tax-incentive", "421a", "affordable-housing"],
    probability: 0.65,
    priorProbability: 0.50,
    lastUpdated: "2026-03-21T11:00:00Z",
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
    tags: ["office", "vacancy", "conversion"],
    probability: 0.22,
    priorProbability: 0.25,
    lastUpdated: "2026-03-17T08:30:00Z",
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
    tags: ["zoning", "city-of-yes", "pipeline"],
    probability: 0.48,
    priorProbability: 0.45,
    lastUpdated: "2026-03-20T10:00:00Z",
  },
];

const mockUpdates: (ForecastUpdate & { questionTitle: string })[] = [
  {
    id: "u1",
    forecast_run_id: "fr1",
    question_id: "q4",
    timestamp: "2026-03-21T11:00:00Z",
    old_probability: 0.50,
    new_probability: 0.65,
    reason: "Budget committee hearing signals bipartisan support for 421-a successor.",
    questionTitle: "421-a Replacement Program",
  },
  {
    id: "u2",
    forecast_run_id: "fr2",
    question_id: "q1",
    timestamp: "2026-03-20T14:30:00Z",
    old_probability: 0.35,
    new_probability: 0.42,
    reason: "February rent data shows 3.2% MoM increase, stronger than seasonal norms.",
    questionTitle: "Median Rent > $4,000",
  },
  {
    id: "u3",
    forecast_run_id: "fr3",
    question_id: "q3",
    timestamp: "2026-03-18T16:45:00Z",
    old_probability: 0.34,
    new_probability: 0.28,
    reason: "Q1 permit data tracking 18% below prior year; construction financing tighter.",
    questionTitle: "Housing Starts > 30k",
  },
  {
    id: "u4",
    forecast_run_id: "fr4",
    question_id: "q2",
    timestamp: "2026-03-19T09:15:00Z",
    old_probability: 0.55,
    new_probability: 0.58,
    reason: "Early implementation data shows slight decline in filings in pilot boroughs.",
    questionTitle: "Good Cause Eviction Impact",
  },
];

const scenarioSummary = [
  { name: "Accelerated Supply", probability: 0.18 },
  { name: "Status Quo Drift", probability: 0.35 },
  { name: "Policy Breakthrough", probability: 0.27 },
  { name: "Market Correction", probability: 0.12 },
  { name: "Affordability Crisis Deepens", probability: 0.08 },
];

// ── Component ───────────────────────────────────────────────────────

export default function OverviewPage() {
  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-100">Dashboard</h1>
        <p className="mt-1 text-sm text-gray-500">
          NYC Housing Market Forecasting System — Overview
        </p>
      </div>

      {/* Metric cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          label="Active Forecasts"
          value={6}
          subtitle="2 resolving this quarter"
          icon={Activity}
          trend={{ value: 12, label: "vs last month" }}
        />
        <MetricCard
          label="Avg. Brier Score"
          value="0.182"
          subtitle="Lower is better"
          icon={Target}
          trend={{ value: -8, label: "improving" }}
        />
        <MetricCard
          label="Evidence Ingested"
          value={147}
          subtitle="Last 30 days"
          icon={FileSearch}
          trend={{ value: 23, label: "vs prior period" }}
        />
        <MetricCard
          label="Model Updates"
          value={34}
          subtitle="Last 7 days"
          icon={TrendingUp}
        />
      </div>

      {/* Active forecasts grid */}
      <section>
        <h2 className="section-heading">Active Forecasts</h2>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {mockQuestions.map((q) => (
            <ForecastCard
              key={q.id}
              question={q}
              probability={q.probability}
              priorProbability={q.priorProbability}
              lastUpdated={q.lastUpdated}
            />
          ))}
        </div>
      </section>

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
        {/* Scenario summary */}
        <section>
          <h2 className="section-heading">Scenario Probabilities</h2>
          <div className="card space-y-4">
            {scenarioSummary.map((s) => (
              <div key={s.name}>
                <div className="mb-1 flex items-center justify-between">
                  <span className="text-sm text-gray-300">{s.name}</span>
                  <span className="text-sm font-semibold text-gray-100 tabular-nums">
                    {Math.round(s.probability * 100)}%
                  </span>
                </div>
                <ProbabilityGauge
                  probability={s.probability}
                  showLabel={false}
                  size="sm"
                />
              </div>
            ))}
          </div>
        </section>

        {/* Recent updates feed */}
        <section>
          <h2 className="section-heading">Recent Updates</h2>
          <div className="space-y-3">
            {mockUpdates.map((u) => {
              const delta = u.new_probability - u.old_probability;
              const absDelta = Math.abs(Math.round(delta * 100));
              const Icon =
                delta > 0 ? ArrowUpRight : delta < 0 ? ArrowDownRight : Minus;
              const color =
                delta > 0
                  ? "text-accent-positive"
                  : delta < 0
                    ? "text-accent-negative"
                    : "text-accent-neutral";

              return (
                <div key={u.id} className="card-hover">
                  <div className="flex items-start justify-between mb-1">
                    <span className="text-xs font-medium text-brand-400">
                      {u.questionTitle}
                    </span>
                    <span className="text-[10px] text-gray-500">
                      {format(new Date(u.timestamp), "MMM d, h:mm a")}
                    </span>
                  </div>
                  <p className="text-sm text-gray-300 mb-2">{u.reason}</p>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-gray-500 tabular-nums">
                      {Math.round(u.old_probability * 100)}%
                    </span>
                    <Icon className={clsx("h-3.5 w-3.5", color)} />
                    <span className={clsx("text-xs font-semibold tabular-nums", color)}>
                      {Math.round(u.new_probability * 100)}%
                    </span>
                    <span className={clsx("text-[10px]", color)}>
                      ({delta > 0 ? "+" : ""}{absDelta}pp)
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      </div>
    </div>
  );
}
