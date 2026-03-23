"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import ProbabilityGauge from "@/components/ProbabilityGauge";
import UncertaintyBand from "@/components/UncertaintyBand";
import EvidenceTimeline from "@/components/EvidenceTimeline";
import ScenarioComparison from "@/components/ScenarioComparison";
import MetricCard from "@/components/MetricCard";
import type { EvidenceItem, Scenario } from "@/types";

// ── Mock data ───────────────────────────────────────────────────────

const mockQuestion = {
  id: "q1",
  title: "Will NYC median rent exceed $4,000/mo by Q4 2026?",
  description:
    "Tracks whether citywide median asking rent crosses the $4,000 threshold. Considers supply pipeline, wage growth, migration patterns, and policy interventions.",
  category: "Rental Market",
  resolution_date: "2026-12-31",
  created_at: "2025-09-01T00:00:00Z",
  updated_at: "2026-03-20T14:30:00Z",
  status: "active" as const,
  resolution_criteria:
    "StreetEasy median asking rent for NYC exceeds $4,000 in any month of Q4 2026.",
  tags: ["rent", "affordability", "market-data"],
};

const forecastHistory = [
  { date: "Oct 2025", posterior: 0.30, lower: 0.18, upper: 0.44 },
  { date: "Nov 2025", posterior: 0.32, lower: 0.19, upper: 0.46 },
  { date: "Dec 2025", posterior: 0.33, lower: 0.20, upper: 0.47 },
  { date: "Jan 2026", posterior: 0.35, lower: 0.22, upper: 0.49 },
  { date: "Feb 2026", posterior: 0.38, lower: 0.24, upper: 0.52 },
  { date: "Mar 2026", posterior: 0.42, lower: 0.27, upper: 0.56 },
];

const mockEvidence: EvidenceItem[] = [
  {
    id: "e1",
    question_id: "q1",
    title: "February rent data shows 3.2% MoM increase",
    source: "StreetEasy Market Report",
    source_type: "data",
    content: "Median asking rent hit $3,812 in February 2026, up 3.2% from January. This is the largest month-over-month jump since mid-2022.",
    published_at: "2026-03-15T00:00:00Z",
    ingested_at: "2026-03-15T14:00:00Z",
    direction: "supports",
    impact_strength: 0.8,
    relevance_score: 0.95,
  },
  {
    id: "e2",
    question_id: "q1",
    title: "City of Yes expected to add 5,000 units to near-term pipeline",
    source: "NYC DCP Quarterly Report",
    source_type: "policy",
    content: "New zoning provisions have generated permits for approximately 5,000 additional units, with most expected to reach market in 2027-2028.",
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
    content: "Three major tech firms announced layoffs affecting ~2,500 NYC-based employees, potentially dampening demand in luxury rental segments.",
    published_at: "2026-03-05T00:00:00Z",
    ingested_at: "2026-03-05T16:00:00Z",
    direction: "opposes",
    impact_strength: 0.3,
    relevance_score: 0.6,
  },
  {
    id: "e4",
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
    id: "e5",
    question_id: "q1",
    title: "Federal Reserve signals potential rate cut in Q3",
    source: "FOMC Minutes",
    source_type: "market",
    content: "Fed officials indicated potential for a 25bp rate cut if inflation trends continue, which could stimulate housing demand.",
    published_at: "2026-02-20T00:00:00Z",
    ingested_at: "2026-02-20T15:00:00Z",
    direction: "supports",
    impact_strength: 0.5,
    relevance_score: 0.65,
  },
];

const mockScenarios: Scenario[] = [
  {
    id: "s1",
    question_id: "q1",
    name: "Strong Demand / Tight Supply",
    description: "Continued migration inflows + slow construction completions push rents rapidly upward.",
    probability: 0.32,
    prior_probability: 0.25,
    conditions: ["Net migration > 50k", "Completions < 20k", "Wage growth > 4%"],
    created_at: "2025-09-01T00:00:00Z",
    updated_at: "2026-03-20T00:00:00Z",
  },
  {
    id: "s2",
    question_id: "q1",
    name: "Moderate Growth",
    description: "Balanced supply-demand dynamics with rents climbing but falling short of $4k threshold.",
    probability: 0.38,
    prior_probability: 0.40,
    conditions: ["Normal migration", "Steady completions", "Inflation ~3%"],
    created_at: "2025-09-01T00:00:00Z",
    updated_at: "2026-03-20T00:00:00Z",
  },
  {
    id: "s3",
    question_id: "q1",
    name: "Demand Shock",
    description: "Economic downturn or policy changes significantly reduce rental demand.",
    probability: 0.15,
    prior_probability: 0.20,
    conditions: ["Recession", "Outmigration spike", "Remote work shift"],
    created_at: "2025-09-01T00:00:00Z",
    updated_at: "2026-03-20T00:00:00Z",
  },
  {
    id: "s4",
    question_id: "q1",
    name: "Supply Surge",
    description: "Accelerated completions from delayed projects flood the market.",
    probability: 0.15,
    prior_probability: 0.15,
    conditions: ["Completions > 35k", "Conversion pipeline", "Policy incentives"],
    created_at: "2025-09-01T00:00:00Z",
    updated_at: "2026-03-20T00:00:00Z",
  },
];

// ── Component ───────────────────────────────────────────────────────

export default function QuestionDetailPage() {
  const q = mockQuestion;

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <Link
          href="/questions"
          className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-300 transition-colors mb-4"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Questions
        </Link>
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <div className="flex items-center gap-3 mb-2">
              <span className="badge-active">{q.status}</span>
              <span className="badge bg-surface border border-surface-border text-gray-400">
                {q.category}
              </span>
              {q.tags.map((tag) => (
                <span
                  key={tag}
                  className="badge bg-brand-600/10 text-brand-400"
                >
                  {tag}
                </span>
              ))}
            </div>
            <h1 className="text-2xl font-bold text-gray-100">{q.title}</h1>
            <p className="mt-2 text-sm text-gray-400 max-w-3xl">
              {q.description}
            </p>
          </div>
          <div className="ml-8 w-48 shrink-0">
            <ProbabilityGauge probability={0.42} size="lg" />
            <p className="mt-1 text-xs text-gray-500 text-center">
              Current Posterior
            </p>
          </div>
        </div>
      </div>

      {/* Key metrics */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard label="Prior" value="30%" subtitle="Initial estimate" />
        <MetricCard label="Posterior" value="42%" subtitle="Current estimate" />
        <MetricCard
          label="90% CI"
          value="27% - 56%"
          subtitle="Confidence interval"
        />
        <MetricCard
          label="Evidence Items"
          value={5}
          subtitle="3 supporting, 2 opposing"
        />
      </div>

      {/* Resolution criteria */}
      <div className="card">
        <h2 className="text-sm font-semibold text-gray-100 mb-2">
          Resolution Criteria
        </h2>
        <p className="text-sm text-gray-400">{q.resolution_criteria}</p>
        <p className="mt-2 text-xs text-gray-500">
          Resolves by: {q.resolution_date}
        </p>
      </div>

      {/* Uncertainty band chart */}
      <section>
        <h2 className="section-heading">Forecast History with Uncertainty</h2>
        <div className="card">
          <UncertaintyBand data={forecastHistory} />
        </div>
      </section>

      {/* Scenario comparison */}
      <section>
        <h2 className="section-heading">Scenario Comparison</h2>
        <ScenarioComparison scenarios={mockScenarios} />
      </section>

      {/* Evidence timeline */}
      <section>
        <h2 className="section-heading">Evidence Timeline</h2>
        <div className="card">
          <EvidenceTimeline items={mockEvidence} />
        </div>
      </section>
    </div>
  );
}
