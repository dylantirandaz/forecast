import axios from "axios";
import type {
  Question,
  Scenario,
  ForecastRun,
  ForecastUpdate,
  EvidenceItem,
  EvidenceScore,
  BaseRate,
  BacktestRun,
  Resolution,
  CalibrationMetrics,
} from "@/types";

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1",
  headers: {
    "Content-Type": "application/json",
  },
});

// ── Questions ──────────────────────────────────────────────────────

export async function getQuestions(): Promise<Question[]> {
  const { data } = await api.get<Question[]>("/questions");
  return data;
}

export async function getQuestion(id: string): Promise<Question> {
  const { data } = await api.get<Question>(`/questions/${id}`);
  return data;
}

export async function createQuestion(
  question: Omit<Question, "id" | "created_at" | "updated_at">
): Promise<Question> {
  const { data } = await api.post<Question>("/questions", question);
  return data;
}

export async function updateQuestion(
  id: string,
  question: Partial<Question>
): Promise<Question> {
  const { data } = await api.patch<Question>(`/questions/${id}`, question);
  return data;
}

// ── Scenarios ──────────────────────────────────────────────────────

export async function getScenarios(questionId: string): Promise<Scenario[]> {
  const { data } = await api.get<Scenario[]>(
    `/questions/${questionId}/scenarios`
  );
  return data;
}

export async function createScenario(
  questionId: string,
  scenario: Omit<Scenario, "id" | "question_id" | "created_at" | "updated_at">
): Promise<Scenario> {
  const { data } = await api.post<Scenario>(
    `/questions/${questionId}/scenarios`,
    scenario
  );
  return data;
}

// ── Forecasts ──────────────────────────────────────────────────────

export async function getForecastRuns(
  questionId: string
): Promise<ForecastRun[]> {
  const { data } = await api.get<ForecastRun[]>(
    `/questions/${questionId}/forecasts`
  );
  return data;
}

export async function getLatestForecast(
  questionId: string
): Promise<ForecastRun> {
  const { data } = await api.get<ForecastRun>(
    `/questions/${questionId}/forecasts/latest`
  );
  return data;
}

export async function triggerForecastRun(
  questionId: string
): Promise<ForecastRun> {
  const { data } = await api.post<ForecastRun>(
    `/questions/${questionId}/forecasts/run`
  );
  return data;
}

export async function getForecastUpdates(
  questionId: string
): Promise<ForecastUpdate[]> {
  const { data } = await api.get<ForecastUpdate[]>(
    `/questions/${questionId}/updates`
  );
  return data;
}

// ── Evidence ───────────────────────────────────────────────────────

export async function getEvidence(params?: {
  question_id?: string;
  source_type?: string;
  direction?: string;
  min_date?: string;
  max_date?: string;
}): Promise<EvidenceItem[]> {
  const { data } = await api.get<EvidenceItem[]>("/evidence", { params });
  return data;
}

export async function getEvidenceItem(id: string): Promise<EvidenceItem> {
  const { data } = await api.get<EvidenceItem>(`/evidence/${id}`);
  return data;
}

export async function getEvidenceScore(id: string): Promise<EvidenceScore> {
  const { data } = await api.get<EvidenceScore>(`/evidence/${id}/score`);
  return data;
}

export async function ingestEvidence(
  evidence: Omit<EvidenceItem, "id" | "ingested_at">
): Promise<EvidenceItem> {
  const { data } = await api.post<EvidenceItem>("/evidence", evidence);
  return data;
}

// ── Base Rates ─────────────────────────────────────────────────────

export async function getBaseRates(questionId: string): Promise<BaseRate[]> {
  const { data } = await api.get<BaseRate[]>(
    `/questions/${questionId}/base-rates`
  );
  return data;
}

// ── Backtesting ────────────────────────────────────────────────────

export async function getBacktestRuns(): Promise<BacktestRun[]> {
  const { data } = await api.get<BacktestRun[]>("/backtests");
  return data;
}

export async function getBacktestRun(id: string): Promise<BacktestRun> {
  const { data } = await api.get<BacktestRun>(`/backtests/${id}`);
  return data;
}

export async function startBacktest(params: {
  name: string;
  start_date: string;
  end_date: string;
  question_ids: string[];
}): Promise<BacktestRun> {
  const { data } = await api.post<BacktestRun>("/backtests", params);
  return data;
}

// ── Resolutions ────────────────────────────────────────────────────

export async function getResolutions(): Promise<Resolution[]> {
  const { data } = await api.get<Resolution[]>("/resolutions");
  return data;
}

export async function resolveQuestion(
  questionId: string,
  resolution: { outcome: boolean; notes: string }
): Promise<Resolution> {
  const { data } = await api.post<Resolution>(
    `/questions/${questionId}/resolve`,
    resolution
  );
  return data;
}

// ── Calibration ────────────────────────────────────────────────────

export async function getCalibrationMetrics(): Promise<CalibrationMetrics> {
  const { data } = await api.get<CalibrationMetrics>("/calibration");
  return data;
}

export default api;
