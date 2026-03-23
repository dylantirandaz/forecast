"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import MetricCard from "@/components/MetricCard";
import DomainBreakdownChart from "@/components/DomainBreakdownChart";
import HorizonChart from "@/components/HorizonChart";
import PredictionHistogram from "@/components/PredictionHistogram";
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import {
  Target,
  TrendingUp,
  Crosshair,
  Gauge,
  DollarSign,
  ArrowLeft,
} from "lucide-react";

// ── Mock data ───────────────────────────────────────────────────────

const evalRunsMeta: Record<
  string,
  {
    name: string;
    status: string;
    brier: number;
    logScore: number;
    calError: number;
    sharpness: number;
    cost: number;
    questions: number;
    date: string;
  }
> = {
  "run-001": { name: "Full Pipeline v1", status: "completed", brier: 0.192, logScore: 0.55, calError: 0.035, sharpness: 0.68, cost: 2.40, questions: 80, date: "2026-03-18" },
  "run-002": { name: "No Base Rates", status: "completed", brier: 0.248, logScore: 0.72, calError: 0.068, sharpness: 0.55, cost: 2.35, questions: 80, date: "2026-03-17" },
  "run-003": { name: "Static Prior", status: "completed", brier: 0.265, logScore: 0.78, calError: 0.082, sharpness: 0.48, cost: 1.90, questions: 80, date: "2026-03-16" },
  "run-004": { name: "No Calibration", status: "completed", brier: 0.215, logScore: 0.62, calError: 0.095, sharpness: 0.62, cost: 2.30, questions: 80, date: "2026-03-15" },
  "run-005": { name: "Uniform Weights", status: "completed", brier: 0.208, logScore: 0.59, calError: 0.042, sharpness: 0.60, cost: 2.38, questions: 80, date: "2026-03-14" },
  "run-006": { name: "Tier B Only", status: "completed", brier: 0.178, logScore: 0.48, calError: 0.028, sharpness: 0.72, cost: 5.20, questions: 80, date: "2026-03-13" },
};

const domainData = [
  { domain: "Macro", brier: 0.185, logScore: 0.52, calError: 0.030, count: 22 },
  { domain: "Geopolitical", brier: 0.210, logScore: 0.60, calError: 0.045, count: 18 },
  { domain: "Tech", brier: 0.165, logScore: 0.45, calError: 0.025, count: 15 },
  { domain: "Climate", brier: 0.240, logScore: 0.70, calError: 0.055, count: 12 },
  { domain: "Health", brier: 0.195, logScore: 0.54, calError: 0.038, count: 13 },
];

const horizonData = [
  { horizon: "90d", model: 0.225, baseline: 0.250, upper: 0.260, lower: 0.190 },
  { horizon: "30d", model: 0.185, baseline: 0.250, upper: 0.215, lower: 0.155 },
  { horizon: "7d", model: 0.135, baseline: 0.250, upper: 0.160, lower: 0.110 },
];

const calibrationData = [
  { predicted: 0.05, observed: 0.08, count: 12 },
  { predicted: 0.15, observed: 0.18, count: 15 },
  { predicted: 0.25, observed: 0.22, count: 18 },
  { predicted: 0.35, observed: 0.30, count: 22 },
  { predicted: 0.45, observed: 0.48, count: 25 },
  { predicted: 0.55, observed: 0.52, count: 20 },
  { predicted: 0.65, observed: 0.68, count: 17 },
  { predicted: 0.75, observed: 0.70, count: 14 },
  { predicted: 0.85, observed: 0.82, count: 10 },
  { predicted: 0.95, observed: 0.90, count: 8 },
];

const histogramData = [
  { bin: "0-0.1", count: 8 },
  { bin: "0.1-0.2", count: 12 },
  { bin: "0.2-0.3", count: 10 },
  { bin: "0.3-0.4", count: 7 },
  { bin: "0.4-0.5", count: 5 },
  { bin: "0.5-0.6", count: 6 },
  { bin: "0.6-0.7", count: 9 },
  { bin: "0.7-0.8", count: 11 },
  { bin: "0.8-0.9", count: 7 },
  { bin: "0.9-1.0", count: 5 },
];

const baselineComparison = [
  { name: "Model", brier: 0.192, logScore: 0.55, calError: 0.035 },
  { name: "Always 0.5", brier: 0.250, logScore: 0.693, calError: 0.0 },
  { name: "Base Rate Only", brier: 0.220, logScore: 0.62, calError: 0.050 },
];

const predictions = [
  { question: "Will US CPI YoY exceed 4% in June 2023?", cutoff: "90d", predicted: 0.72, actual: 0, brier: 0.518, evidenceCount: 5 },
  { question: "Will the Fed raise rates in March 2023?", cutoff: "30d", predicted: 0.88, actual: 1, brier: 0.014, evidenceCount: 8 },
  { question: "Will NVIDIA stock exceed $500 by Q2 2023?", cutoff: "7d", predicted: 0.35, actual: 0, brier: 0.123, evidenceCount: 4 },
  { question: "Will EU approve AI Act by end of 2023?", cutoff: "90d", predicted: 0.62, actual: 1, brier: 0.144, evidenceCount: 6 },
  { question: "Will global avg temperature anomaly exceed 1.5C in 2023?", cutoff: "30d", predicted: 0.55, actual: 1, brier: 0.203, evidenceCount: 3 },
  { question: "Will China GDP growth exceed 5% in 2023?", cutoff: "90d", predicted: 0.48, actual: 1, brier: 0.270, evidenceCount: 7 },
  { question: "Will Bitcoin exceed $40k by Dec 2023?", cutoff: "30d", predicted: 0.30, actual: 1, brier: 0.490, evidenceCount: 5 },
  { question: "Will WHO declare mpox emergency over by mid-2023?", cutoff: "7d", predicted: 0.78, actual: 1, brier: 0.048, evidenceCount: 4 },
];

function statusBadge(status: string) {
  const colors: Record<string, string> = {
    completed: "bg-accent-positive/15 text-accent-positive",
    running: "bg-blue-500/15 text-blue-400",
    failed: "bg-accent-negative/15 text-accent-negative",
  };
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wider ${colors[status] ?? "bg-gray-500/15 text-gray-400"}`}
    >
      {status}
    </span>
  );
}

export default function EvalDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const run = evalRunsMeta[id] ?? evalRunsMeta["run-001"];

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
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold text-gray-100">{run.name}</h1>
          {statusBadge(run.status)}
        </div>
        <p className="mt-1 text-sm text-gray-500">
          Run on {run.date} &middot; {run.questions} questions evaluated
        </p>
      </div>

      {/* Summary metrics */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <MetricCard label="Brier Score" value={run.brier.toFixed(3)} subtitle="0 = perfect" icon={Target} />
        <MetricCard label="Log Score" value={run.logScore.toFixed(2)} subtitle="Lower is better" icon={TrendingUp} />
        <MetricCard label="Cal Error" value={run.calError.toFixed(3)} subtitle="Mean abs deviation" icon={Crosshair} />
        <MetricCard label="Sharpness" value={run.sharpness.toFixed(2)} subtitle="Avg dist from 50%" icon={Gauge} />
        <MetricCard label="Cost" value={`$${run.cost.toFixed(2)}`} subtitle="Total API cost" icon={DollarSign} />
      </div>

      {/* Charts row 1 */}
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
        <section>
          <h2 className="section-heading">Domain Breakdown</h2>
          <div className="card">
            <p className="mb-4 text-xs text-gray-500">
              Brier score by question domain. Green &lt; 0.2, yellow 0.2-0.3, red &gt; 0.3. Dashed line = always-0.5 baseline.
            </p>
            <DomainBreakdownChart data={domainData} />
          </div>
        </section>

        <section>
          <h2 className="section-heading">Horizon Breakdown</h2>
          <div className="card">
            <p className="mb-4 text-xs text-gray-500">
              Brier score improves as the prediction horizon shortens and more evidence becomes available.
            </p>
            <HorizonChart data={horizonData} />
          </div>
        </section>
      </div>

      {/* Baseline comparison */}
      <section>
        <h2 className="section-heading">Baseline Comparison</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {baselineComparison.map((b) => {
            const isModel = b.name === "Model";
            const brierDelta = isModel ? 0 : b.brier - baselineComparison[0].brier;
            return (
              <div
                key={b.name}
                className={`card ${isModel ? "border-brand-500/40" : ""}`}
              >
                <div className="flex items-center justify-between mb-3">
                  <span className={`text-sm font-semibold ${isModel ? "text-brand-400" : "text-gray-300"}`}>
                    {b.name}
                  </span>
                  {!isModel && (
                    <span
                      className={`text-xs font-semibold ${
                        brierDelta > 0
                          ? "text-accent-positive"
                          : "text-accent-negative"
                      }`}
                    >
                      Model is {(brierDelta * 100).toFixed(1)}pp better
                    </span>
                  )}
                </div>
                <div className="grid grid-cols-3 gap-2 text-xs">
                  <div>
                    <span className="text-gray-500">Brier</span>
                    <p className="text-gray-200 font-mono tabular-nums">
                      {b.brier.toFixed(3)}
                    </p>
                  </div>
                  <div>
                    <span className="text-gray-500">Log</span>
                    <p className="text-gray-200 font-mono tabular-nums">
                      {b.logScore.toFixed(3)}
                    </p>
                  </div>
                  <div>
                    <span className="text-gray-500">Cal Err</span>
                    <p className="text-gray-200 font-mono tabular-nums">
                      {b.calError.toFixed(3)}
                    </p>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* Charts row 2 */}
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
        {/* Calibration curve */}
        <section>
          <h2 className="section-heading">Calibration Curve</h2>
          <div className="card">
            <p className="mb-4 text-xs text-gray-500">
              Points on the diagonal indicate perfect calibration. Above = underconfident, below = overconfident.
            </p>
            <div className="h-80">
              <ResponsiveContainer width="100%" height="100%">
                <ScatterChart margin={{ top: 10, right: 10, left: 0, bottom: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#2d3f5e" />
                  <XAxis
                    type="number"
                    dataKey="predicted"
                    domain={[0, 1]}
                    tickFormatter={(v: number) => `${Math.round(v * 100)}%`}
                    tick={{ fontSize: 11, fill: "#94a3b8" }}
                    tickLine={false}
                    axisLine={{ stroke: "#2d3f5e" }}
                    name="Predicted"
                    label={{ value: "Predicted", position: "insideBottom", offset: -5, style: { fill: "#64748b", fontSize: 12 } }}
                  />
                  <YAxis
                    type="number"
                    dataKey="observed"
                    domain={[0, 1]}
                    tickFormatter={(v: number) => `${Math.round(v * 100)}%`}
                    tick={{ fontSize: 11, fill: "#94a3b8" }}
                    tickLine={false}
                    axisLine={{ stroke: "#2d3f5e" }}
                    name="Observed"
                    label={{ value: "Observed", angle: -90, position: "insideLeft", offset: 10, style: { fill: "#64748b", fontSize: 12 } }}
                  />
                  <Tooltip
                    contentStyle={{ backgroundColor: "#1e293b", border: "1px solid #2d3f5e", borderRadius: 8, fontSize: 12 }}
                    formatter={(value: number, name: string) => [`${(value * 100).toFixed(1)}%`, name]}
                  />
                  <ReferenceLine
                    segment={[{ x: 0, y: 0 }, { x: 1, y: 1 }]}
                    stroke="#64748b"
                    strokeDasharray="6 4"
                    strokeWidth={1}
                  />
                  <Scatter data={calibrationData} fill="#3b82f6" stroke="#1e40af" strokeWidth={1} r={6} />
                </ScatterChart>
              </ResponsiveContainer>
            </div>
          </div>
        </section>

        {/* Prediction histogram */}
        <section>
          <h2 className="section-heading">Prediction Distribution</h2>
          <div className="card">
            <p className="mb-4 text-xs text-gray-500">
              Distribution of predicted probabilities. Sharp forecasters push predictions away from 50%.
            </p>
            <PredictionHistogram data={histogramData} />
          </div>
        </section>
      </div>

      {/* Individual predictions table */}
      <section>
        <h2 className="section-heading">Individual Predictions</h2>
        <div className="overflow-hidden rounded-xl border border-surface-border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-surface-border bg-surface">
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Question</th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Cutoff</th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Predicted</th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Actual</th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Brier</th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Evidence</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-border">
              {predictions.map((p, idx) => (
                <tr key={idx} className="bg-surface-raised hover:bg-surface-overlay transition-colors">
                  <td className="px-4 py-3 text-gray-300 max-w-xs truncate" title={p.question}>
                    {p.question.length > 55 ? p.question.slice(0, 55) + "..." : p.question}
                  </td>
                  <td className="px-4 py-3">
                    <span className="rounded bg-surface-overlay px-1.5 py-0.5 text-xs text-gray-400">
                      {p.cutoff}
                    </span>
                  </td>
                  <td className="px-4 py-3 font-mono text-gray-300 tabular-nums">
                    {(p.predicted * 100).toFixed(0)}%
                  </td>
                  <td className="px-4 py-3">
                    <span className={`font-mono text-xs font-semibold ${p.actual === 1 ? "text-accent-positive" : "text-accent-negative"}`}>
                      {p.actual === 1 ? "YES" : "NO"}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`font-mono tabular-nums text-xs font-semibold ${p.brier < 0.1 ? "text-accent-positive" : p.brier < 0.25 ? "text-accent-warning" : "text-accent-negative"}`}>
                      {p.brier.toFixed(3)}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-400 tabular-nums">
                    {p.evidenceCount}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
