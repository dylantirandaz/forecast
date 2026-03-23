"use client";

import { useState } from "react";
import {
  ArrowLeft,
  CheckCircle2,
  XCircle,
  Clock,
  AlertTriangle,
  FileText,
  ChevronRight,
} from "lucide-react";
import Link from "next/link";

// ── Mock data ───────────────────────────────────────────────────────

interface EvidenceItem {
  date: string;
  source: string;
  title: string;
  quality: number;
  availableAtCutoff: Record<string, boolean>;
}

interface ReplayQuestion {
  id: string;
  text: string;
  domain: string;
  difficulty: string;
  openDate: string;
  resolveDate: string;
  resolutionCriteria: string;
  actual: number;
  actualLabel: string;
  evidence: EvidenceItem[];
  predictions: Record<string, { probability: number; baseRate: number; evidenceConsidered: number; rationale: string }>;
}

const questions: ReplayQuestion[] = [
  {
    id: "q1",
    text: "Will US CPI YoY exceed 4% in June 2023?",
    domain: "macro",
    difficulty: "medium",
    openDate: "2023-01-15",
    resolveDate: "2023-07-15",
    resolutionCriteria: "BLS CPI-U report for June 2023 shows YoY change > 4.0%",
    actual: 0,
    actualLabel: "No (June CPI was 3.0%)",
    evidence: [
      { date: "2023-01-12", source: "BLS", title: "December CPI at 6.5% YoY", quality: 0.95, availableAtCutoff: { "90d": true, "30d": true, "7d": true } },
      { date: "2023-02-22", source: "Federal Reserve", title: "Fed minutes signal continued tightening", quality: 0.90, availableAtCutoff: { "90d": true, "30d": true, "7d": true } },
      { date: "2023-03-14", source: "BLS", title: "February CPI at 6.0% YoY, declining trend", quality: 0.95, availableAtCutoff: { "90d": true, "30d": true, "7d": true } },
      { date: "2023-05-10", source: "BLS", title: "April CPI drops to 4.9%", quality: 0.95, availableAtCutoff: { "90d": false, "30d": true, "7d": true } },
      { date: "2023-07-12", source: "BLS", title: "June CPI at 3.0%, below 4% threshold", quality: 0.98, availableAtCutoff: { "90d": false, "30d": false, "7d": true } },
    ],
    predictions: {
      "90d": { probability: 0.72, baseRate: 0.55, evidenceConsidered: 3, rationale: "CPI declining but still well above 4%. Trend suggests possible overshoot. Base rate for sustained high inflation periods supports continued elevation." },
      "30d": { probability: 0.45, baseRate: 0.55, evidenceConsidered: 4, rationale: "April CPI at 4.9% shows rapid disinflation. Trend line projects June below 4%. Downward revision from prior estimate." },
      "7d": { probability: 0.15, baseRate: 0.55, evidenceConsidered: 5, rationale: "June CPI report confirms 3.0% YoY. Clear miss below 4% threshold. Very low probability of revision changing outcome." },
    },
  },
  {
    id: "q2",
    text: "Will the Fed raise rates in March 2023?",
    domain: "macro",
    difficulty: "easy",
    openDate: "2023-01-20",
    resolveDate: "2023-03-23",
    resolutionCriteria: "Federal Reserve announces rate increase at March 2023 FOMC meeting",
    actual: 1,
    actualLabel: "Yes (25bp hike to 4.75-5.00%)",
    evidence: [
      { date: "2023-01-25", source: "CME FedWatch", title: "Markets pricing 95% chance of 25bp hike", quality: 0.85, availableAtCutoff: { "90d": true, "30d": true, "7d": true } },
      { date: "2023-02-01", source: "Federal Reserve", title: "February FOMC: 25bp hike, signals more ahead", quality: 0.95, availableAtCutoff: { "90d": true, "30d": true, "7d": true } },
      { date: "2023-03-10", source: "Reuters", title: "SVB collapse raises pause speculation", quality: 0.80, availableAtCutoff: { "90d": false, "30d": true, "7d": true } },
      { date: "2023-03-20", source: "CME FedWatch", title: "Markets split 50/50 on March hike after banking stress", quality: 0.85, availableAtCutoff: { "90d": false, "30d": false, "7d": true } },
      { date: "2023-03-22", source: "Federal Reserve", title: "Fed raises rates 25bp despite banking concerns", quality: 0.99, availableAtCutoff: { "90d": false, "30d": false, "7d": true } },
    ],
    predictions: {
      "90d": { probability: 0.90, baseRate: 0.75, evidenceConsidered: 2, rationale: "Strong market consensus for continued hikes. Fed messaging consistently hawkish." },
      "30d": { probability: 0.65, baseRate: 0.75, evidenceConsidered: 3, rationale: "SVB collapse introduces uncertainty. Banking stress could force pause, but inflation still elevated." },
      "7d": { probability: 0.82, baseRate: 0.75, evidenceConsidered: 5, rationale: "Despite banking concerns, Fed signaling commitment to inflation fight. Markets recovering from panic." },
    },
  },
  {
    id: "q3",
    text: "Will EU approve the AI Act by end of 2023?",
    domain: "tech",
    difficulty: "hard",
    openDate: "2023-02-01",
    resolveDate: "2024-01-05",
    resolutionCriteria: "European Parliament and Council reach political agreement on AI Act text by Dec 31, 2023",
    actual: 1,
    actualLabel: "Yes (Political agreement Dec 8, 2023)",
    evidence: [
      { date: "2023-03-15", source: "EU Parliament", title: "Draft AI Act amendments published", quality: 0.85, availableAtCutoff: { "90d": true, "30d": true, "7d": true } },
      { date: "2023-06-14", source: "EU Parliament", title: "Parliament adopts negotiating position on AI Act", quality: 0.90, availableAtCutoff: { "90d": true, "30d": true, "7d": true } },
      { date: "2023-10-25", source: "Euractiv", title: "Trilogue negotiations intensify, foundation model rules debated", quality: 0.80, availableAtCutoff: { "90d": false, "30d": true, "7d": true } },
      { date: "2023-12-06", source: "Reuters", title: "Marathon trilogue session enters third day", quality: 0.85, availableAtCutoff: { "90d": false, "30d": false, "7d": true } },
      { date: "2023-12-08", source: "EU Council", title: "Political agreement reached on AI Act", quality: 0.98, availableAtCutoff: { "90d": false, "30d": false, "7d": true } },
    ],
    predictions: {
      "90d": { probability: 0.45, baseRate: 0.40, evidenceConsidered: 2, rationale: "EU legislative processes notoriously slow. Parliament position adopted but trilogues haven't started." },
      "30d": { probability: 0.62, baseRate: 0.40, evidenceConsidered: 3, rationale: "Trilogue negotiations progressing. Spanish presidency pushing for deal before year end." },
      "7d": { probability: 0.92, baseRate: 0.40, evidenceConsidered: 5, rationale: "Marathon session underway. Strong political will from all parties to reach deal." },
    },
  },
  {
    id: "q4",
    text: "Will Bitcoin exceed $40k by December 2023?",
    domain: "crypto",
    difficulty: "hard",
    openDate: "2023-03-01",
    resolveDate: "2024-01-01",
    resolutionCriteria: "Bitcoin spot price on any major exchange exceeds $40,000 USD at any point before Jan 1, 2024",
    actual: 1,
    actualLabel: "Yes (Hit $44k in Dec 2023)",
    evidence: [
      { date: "2023-03-15", source: "CoinDesk", title: "Bitcoin at $25k amid banking crisis flight-to-safety", quality: 0.80, availableAtCutoff: { "90d": true, "30d": true, "7d": true } },
      { date: "2023-06-15", source: "Reuters", title: "BlackRock files for spot Bitcoin ETF", quality: 0.90, availableAtCutoff: { "90d": true, "30d": true, "7d": true } },
      { date: "2023-10-24", source: "CoinDesk", title: "Bitcoin surges past $34k on ETF optimism", quality: 0.85, availableAtCutoff: { "90d": false, "30d": true, "7d": true } },
      { date: "2023-12-04", source: "Bloomberg", title: "Bitcoin breaks $40k, highest since April 2022", quality: 0.95, availableAtCutoff: { "90d": false, "30d": false, "7d": true } },
      { date: "2023-12-28", source: "CoinGecko", title: "Bitcoin trading at $42.5k, year-end rally continues", quality: 0.90, availableAtCutoff: { "90d": false, "30d": false, "7d": true } },
    ],
    predictions: {
      "90d": { probability: 0.20, baseRate: 0.30, evidenceConsidered: 2, rationale: "Bitcoin at $25k, needs 60% rally. Historically possible but macro headwinds significant." },
      "30d": { probability: 0.55, baseRate: 0.30, evidenceConsidered: 3, rationale: "ETF narrative driving momentum. Already at $34k, only needs ~18% more." },
      "7d": { probability: 0.98, baseRate: 0.30, evidenceConsidered: 5, rationale: "Already exceeded $40k. Question resolved positively." },
    },
  },
  {
    id: "q5",
    text: "Will global average temperature anomaly exceed 1.5C in 2023?",
    domain: "climate",
    difficulty: "medium",
    openDate: "2023-01-10",
    resolveDate: "2024-02-01",
    resolutionCriteria: "Annual global mean surface temperature anomaly relative to 1850-1900 baseline exceeds 1.5C per ERA5/Copernicus data",
    actual: 1,
    actualLabel: "Yes (1.48C ERA5, rounded to 1.5C)",
    evidence: [
      { date: "2023-02-05", source: "Copernicus", title: "January 2023 anomaly at +1.18C", quality: 0.95, availableAtCutoff: { "90d": true, "30d": true, "7d": true } },
      { date: "2023-05-03", source: "NOAA", title: "El Nino conditions developing in Pacific", quality: 0.90, availableAtCutoff: { "90d": true, "30d": true, "7d": true } },
      { date: "2023-09-06", source: "Copernicus", title: "August 2023 hottest month ever recorded", quality: 0.95, availableAtCutoff: { "90d": false, "30d": true, "7d": true } },
      { date: "2023-11-08", source: "WMO", title: "2023 virtually certain to be warmest year on record", quality: 0.95, availableAtCutoff: { "90d": false, "30d": false, "7d": true } },
      { date: "2024-01-09", source: "Copernicus", title: "2023 confirmed as warmest year, anomaly 1.48C", quality: 0.99, availableAtCutoff: { "90d": false, "30d": false, "7d": true } },
    ],
    predictions: {
      "90d": { probability: 0.35, baseRate: 0.25, evidenceConsidered: 2, rationale: "El Nino developing but 1.5C is a very high bar for annual average. No prior year has exceeded it." },
      "30d": { probability: 0.55, baseRate: 0.25, evidenceConsidered: 3, rationale: "Record-breaking months piling up. El Nino strengthening. Unprecedented heat wave data." },
      "7d": { probability: 0.85, baseRate: 0.25, evidenceConsidered: 5, rationale: "WMO confirmation and monthly data strongly suggest annual average near 1.48-1.50C threshold." },
    },
  },
];

const pipelineSteps = [
  { step: "base_rate", label: "Base Rate Lookup", color: "text-blue-400" },
  { step: "evidence_scoring", label: "Evidence Scoring", color: "text-purple-400" },
  { step: "belief_update", label: "Belief Update", color: "text-yellow-400" },
  { step: "calibration", label: "Calibration Adjust", color: "text-green-400" },
];

export default function ReplayViewerPage() {
  const [selectedQuestionId, setSelectedQuestionId] = useState(questions[0].id);
  const [selectedCutoff, setSelectedCutoff] = useState<"90d" | "30d" | "7d">("90d");
  const [showOutcome, setShowOutcome] = useState(false);

  const question = questions.find((q) => q.id === selectedQuestionId)!;
  const prediction = question.predictions[selectedCutoff];

  const brierScore = Math.pow(prediction.probability - question.actual, 2);
  const isCorrect =
    (prediction.probability >= 0.5 && question.actual === 1) ||
    (prediction.probability < 0.5 && question.actual === 0);

  function qualityBadge(quality: number) {
    if (quality >= 0.9) return "bg-accent-positive/15 text-accent-positive";
    if (quality >= 0.8) return "bg-blue-500/15 text-blue-400";
    return "bg-yellow-500/15 text-yellow-400";
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <Link
          href="/eval"
          className="mb-3 inline-flex items-center gap-1 text-xs text-gray-500 hover:text-gray-300 transition-colors"
        >
          <ArrowLeft className="h-3 w-3" />
          Back to Dashboard
        </Link>
        <h1 className="text-2xl font-bold text-gray-100">
          Question Replay Viewer
        </h1>
        <p className="mt-1 text-sm text-gray-500">
          Replay model predictions at different time horizons to understand reasoning
        </p>
      </div>

      {/* Controls */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end">
        <div className="flex-1">
          <label className="block text-xs font-medium text-gray-400 mb-1">
            Select Question
          </label>
          <select
            value={selectedQuestionId}
            onChange={(e) => {
              setSelectedQuestionId(e.target.value);
              setShowOutcome(false);
            }}
            className="w-full rounded-lg border border-surface-border bg-surface-raised px-3 py-2 text-sm text-gray-200 focus:border-brand-500 focus:outline-none"
          >
            {questions.map((q) => (
              <option key={q.id} value={q.id}>
                {q.text}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-xs font-medium text-gray-400 mb-1">
            Cutoff Horizon
          </label>
          <div className="flex rounded-lg border border-surface-border overflow-hidden">
            {(["90d", "30d", "7d"] as const).map((cutoff) => (
              <button
                key={cutoff}
                onClick={() => {
                  setSelectedCutoff(cutoff);
                  setShowOutcome(false);
                }}
                className={`px-4 py-2 text-sm font-medium transition-colors ${
                  selectedCutoff === cutoff
                    ? "bg-brand-600 text-white"
                    : "bg-surface-raised text-gray-400 hover:bg-surface-overlay hover:text-gray-200"
                }`}
              >
                {cutoff}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Question display */}
      <div className="card">
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-100">
              {question.text}
            </h2>
            <div className="mt-2 flex items-center gap-2">
              <span className="inline-flex items-center rounded-full bg-blue-500/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-blue-400">
                {question.domain}
              </span>
              <span
                className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${
                  question.difficulty === "easy"
                    ? "bg-accent-positive/15 text-accent-positive"
                    : question.difficulty === "medium"
                      ? "bg-yellow-500/15 text-yellow-400"
                      : "bg-accent-negative/15 text-accent-negative"
                }`}
              >
                {question.difficulty}
              </span>
            </div>
          </div>
          <div className="text-right text-xs text-gray-500">
            <p>Open: {question.openDate}</p>
            <p>Resolve: {question.resolveDate}</p>
          </div>
        </div>

        <div className="mt-4 rounded-lg bg-surface-raised p-3">
          <p className="text-xs font-medium text-gray-400 mb-1">
            Resolution Criteria
          </p>
          <p className="text-sm text-gray-300">{question.resolutionCriteria}</p>
        </div>

        {/* Reveal outcome */}
        <div className="mt-4">
          {!showOutcome ? (
            <button
              onClick={() => setShowOutcome(true)}
              className="inline-flex items-center gap-2 rounded-lg border border-surface-border bg-surface-raised px-4 py-2 text-sm text-gray-300 hover:bg-surface-overlay transition-colors"
            >
              <FileText className="h-4 w-4" />
              Reveal Actual Outcome
            </button>
          ) : (
            <div
              className={`rounded-lg p-3 ${
                question.actual === 1
                  ? "bg-accent-positive/10 border border-accent-positive/30"
                  : "bg-accent-negative/10 border border-accent-negative/30"
              }`}
            >
              <div className="flex items-center gap-2">
                {question.actual === 1 ? (
                  <CheckCircle2 className="h-5 w-5 text-accent-positive" />
                ) : (
                  <XCircle className="h-5 w-5 text-accent-negative" />
                )}
                <span
                  className={`text-sm font-semibold ${
                    question.actual === 1
                      ? "text-accent-positive"
                      : "text-accent-negative"
                  }`}
                >
                  Outcome: {question.actual === 1 ? "YES" : "NO"}
                </span>
              </div>
              <p className="mt-1 text-xs text-gray-400">
                {question.actualLabel}
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Evidence timeline */}
      <section>
        <h2 className="section-heading">
          Evidence Available at {selectedCutoff} Cutoff
        </h2>
        <div className="space-y-2">
          {question.evidence.map((ev, idx) => {
            const available = ev.availableAtCutoff[selectedCutoff];
            return (
              <div
                key={idx}
                className={`card flex items-start gap-4 ${
                  !available ? "opacity-40" : ""
                }`}
              >
                <div className="flex flex-col items-center">
                  <div
                    className={`flex h-8 w-8 items-center justify-center rounded-full ${
                      available
                        ? "bg-brand-600/20"
                        : "bg-red-500/20"
                    }`}
                  >
                    {available ? (
                      <Clock className="h-4 w-4 text-brand-400" />
                    ) : (
                      <AlertTriangle className="h-4 w-4 text-red-400" />
                    )}
                  </div>
                  {idx < question.evidence.length - 1 && (
                    <div className="h-full w-px bg-surface-border mt-1" />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-xs font-mono text-gray-500">
                      {ev.date}
                    </span>
                    <span className="text-xs text-gray-500">&middot;</span>
                    <span className="text-xs text-gray-400">{ev.source}</span>
                    <span
                      className={`inline-flex items-center rounded-full px-1.5 py-0.5 text-[10px] font-semibold ${qualityBadge(ev.quality)}`}
                    >
                      {ev.quality.toFixed(2)}
                    </span>
                    {!available && (
                      <span className="inline-flex items-center rounded bg-red-500/20 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-red-400">
                        NOT AVAILABLE AT CUTOFF
                      </span>
                    )}
                  </div>
                  <p
                    className={`mt-1 text-sm ${
                      available ? "text-gray-200" : "text-gray-500 line-through"
                    }`}
                  >
                    {ev.title}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* Model prediction */}
      <section>
        <h2 className="section-heading">
          Model Prediction at {selectedCutoff}
        </h2>
        <div className="card">
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            {/* Probability gauge */}
            <div>
              <p className="text-xs font-medium text-gray-400 mb-3">
                Predicted Probability
              </p>
              <div className="relative h-6 w-full rounded-full bg-surface-raised overflow-hidden">
                <div
                  className="absolute inset-y-0 left-0 rounded-full bg-gradient-to-r from-brand-600 to-brand-400 transition-all duration-500"
                  style={{ width: `${prediction.probability * 100}%` }}
                />
                <span className="absolute inset-0 flex items-center justify-center text-xs font-bold text-white">
                  {(prediction.probability * 100).toFixed(0)}%
                </span>
              </div>

              <div className="mt-4 grid grid-cols-2 gap-4 text-xs">
                <div className="rounded-lg bg-surface-raised p-3">
                  <span className="text-gray-500">Base Rate Used</span>
                  <p className="text-gray-200 font-mono text-lg tabular-nums">
                    {(prediction.baseRate * 100).toFixed(0)}%
                  </p>
                </div>
                <div className="rounded-lg bg-surface-raised p-3">
                  <span className="text-gray-500">Evidence Considered</span>
                  <p className="text-gray-200 font-mono text-lg tabular-nums">
                    {prediction.evidenceConsidered}
                  </p>
                </div>
              </div>
            </div>

            {/* Pipeline trace */}
            <div>
              <p className="text-xs font-medium text-gray-400 mb-3">
                Pipeline Trace
              </p>
              <div className="space-y-2">
                {pipelineSteps.map((step, idx) => (
                  <div
                    key={step.step}
                    className="flex items-center gap-2 rounded-lg bg-surface-raised p-2.5"
                  >
                    <span className="flex h-6 w-6 items-center justify-center rounded bg-surface-overlay text-[10px] font-bold text-gray-400">
                      {idx + 1}
                    </span>
                    <span className={`text-sm font-medium ${step.color}`}>
                      {step.label}
                    </span>
                    {idx < pipelineSteps.length - 1 && (
                      <ChevronRight className="h-3 w-3 text-gray-600 ml-auto" />
                    )}
                    {idx === pipelineSteps.length - 1 && (
                      <CheckCircle2 className="h-3 w-3 text-accent-positive ml-auto" />
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Rationale */}
          <div className="mt-6 rounded-lg bg-surface-raised p-4">
            <p className="text-xs font-medium text-gray-400 mb-2">
              Model Rationale
            </p>
            <p className="text-sm text-gray-300 leading-relaxed">
              {prediction.rationale}
            </p>
          </div>
        </div>
      </section>

      {/* Outcome comparison */}
      <section>
        <h2 className="section-heading">Outcome Comparison</h2>
        <div className="card">
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-3">
            <div className="rounded-lg bg-surface-raised p-4 text-center">
              <p className="text-xs text-gray-500 mb-1">Predicted</p>
              <p className="text-2xl font-bold text-brand-400 font-mono tabular-nums">
                {(prediction.probability * 100).toFixed(0)}%
              </p>
            </div>
            <div className="rounded-lg bg-surface-raised p-4 text-center">
              <p className="text-xs text-gray-500 mb-1">Actual</p>
              <p
                className={`text-2xl font-bold font-mono tabular-nums ${
                  question.actual === 1
                    ? "text-accent-positive"
                    : "text-accent-negative"
                }`}
              >
                {question.actual === 1 ? "YES (1)" : "NO (0)"}
              </p>
            </div>
            <div className="rounded-lg bg-surface-raised p-4 text-center">
              <p className="text-xs text-gray-500 mb-1">Brier Score</p>
              <p
                className={`text-2xl font-bold font-mono tabular-nums ${
                  brierScore < 0.1
                    ? "text-accent-positive"
                    : brierScore < 0.25
                      ? "text-accent-warning"
                      : "text-accent-negative"
                }`}
              >
                {brierScore.toFixed(3)}
              </p>
            </div>
          </div>

          <div className="mt-4 flex items-center justify-center gap-2">
            {isCorrect ? (
              <>
                <CheckCircle2 className="h-5 w-5 text-accent-positive" />
                <span className="text-sm font-semibold text-accent-positive">
                  Model prediction was directionally correct
                </span>
              </>
            ) : (
              <>
                <XCircle className="h-5 w-5 text-accent-negative" />
                <span className="text-sm font-semibold text-accent-negative">
                  Model prediction was directionally incorrect
                </span>
              </>
            )}
          </div>

          {/* All horizons comparison */}
          <div className="mt-6">
            <p className="text-xs font-medium text-gray-400 mb-3">
              Prediction Across All Horizons
            </p>
            <div className="overflow-hidden rounded-lg border border-surface-border">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-surface-border bg-surface">
                    <th className="px-4 py-2 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                      Horizon
                    </th>
                    <th className="px-4 py-2 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                      Predicted
                    </th>
                    <th className="px-4 py-2 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                      Brier
                    </th>
                    <th className="px-4 py-2 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                      Direction
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-border">
                  {(["90d", "30d", "7d"] as const).map((h) => {
                    const pred = question.predictions[h];
                    const b = Math.pow(pred.probability - question.actual, 2);
                    const correct =
                      (pred.probability >= 0.5 && question.actual === 1) ||
                      (pred.probability < 0.5 && question.actual === 0);
                    return (
                      <tr
                        key={h}
                        className={`bg-surface-raised ${
                          h === selectedCutoff ? "ring-1 ring-inset ring-brand-500/50" : ""
                        }`}
                      >
                        <td className="px-4 py-2 text-gray-300 font-mono">
                          {h}
                        </td>
                        <td className="px-4 py-2 text-gray-300 font-mono tabular-nums">
                          {(pred.probability * 100).toFixed(0)}%
                        </td>
                        <td className="px-4 py-2">
                          <span
                            className={`font-mono tabular-nums text-xs font-semibold ${
                              b < 0.1
                                ? "text-accent-positive"
                                : b < 0.25
                                  ? "text-accent-warning"
                                  : "text-accent-negative"
                            }`}
                          >
                            {b.toFixed(3)}
                          </span>
                        </td>
                        <td className="px-4 py-2">
                          {correct ? (
                            <CheckCircle2 className="h-4 w-4 text-accent-positive" />
                          ) : (
                            <XCircle className="h-4 w-4 text-accent-negative" />
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
