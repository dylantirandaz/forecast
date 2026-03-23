export interface Question {
  id: string;
  title: string;
  description: string;
  category: string;
  resolution_date: string;
  created_at: string;
  updated_at: string;
  status: "active" | "resolved" | "archived";
  resolution_criteria: string;
  tags: string[];
}

export interface Scenario {
  id: string;
  question_id: string;
  name: string;
  description: string;
  probability: number;
  prior_probability: number;
  conditions: string[];
  created_at: string;
  updated_at: string;
}

export interface ForecastRun {
  id: string;
  question_id: string;
  timestamp: string;
  prior: number;
  posterior: number;
  confidence_lower: number;
  confidence_upper: number;
  evidence_ids: string[];
  model_version: string;
  notes: string;
}

export interface ForecastUpdate {
  id: string;
  forecast_run_id: string;
  question_id: string;
  timestamp: string;
  old_probability: number;
  new_probability: number;
  reason: string;
  evidence_id?: string;
}

export interface EvidenceItem {
  id: string;
  question_id: string;
  title: string;
  source: string;
  source_type: "news" | "data" | "policy" | "expert" | "market" | "academic";
  content: string;
  published_at: string;
  ingested_at: string;
  direction: "supports" | "opposes" | "neutral";
  impact_strength: number;
  relevance_score: number;
  url?: string;
}

export interface EvidenceScore {
  evidence_id: string;
  relevance: number;
  reliability: number;
  informativeness: number;
  recency_weight: number;
  composite_score: number;
}

export interface BaseRate {
  id: string;
  question_id: string;
  description: string;
  rate: number;
  sample_size: number;
  time_period: string;
  source: string;
  applicable: boolean;
}

export interface BacktestRun {
  id: string;
  name: string;
  start_date: string;
  end_date: string;
  question_ids: string[];
  status: "pending" | "running" | "completed" | "failed";
  created_at: string;
  completed_at?: string;
  results?: BacktestResult[];
}

export interface BacktestResult {
  question_id: string;
  forecast_date: string;
  predicted_probability: number;
  realized_outcome: number;
  brier_score: number;
  log_score: number;
}

export interface Resolution {
  id: string;
  question_id: string;
  outcome: boolean;
  resolved_at: string;
  notes: string;
  final_probability: number;
}

export interface CalibrationMetrics {
  total_questions: number;
  resolved_questions: number;
  brier_score: number;
  log_score: number;
  calibration_error: number;
  sharpness: number;
  resolution_score: number;
  buckets: CalibrationBucket[];
}

export interface CalibrationBucket {
  predicted_low: number;
  predicted_high: number;
  predicted_mean: number;
  observed_frequency: number;
  count: number;
}
