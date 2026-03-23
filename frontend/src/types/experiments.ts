export interface AblationConfig {
  name: string;
  description: string;
  use_base_rates: boolean;
  use_evidence_scoring: boolean;
  use_recency_weighting: boolean;
  use_novelty_filter: boolean;
  use_calibration: boolean;
  calibration_scope: string;
  evidence_weighting: string;
  model_tier: string;
  use_disagreement_second_pass: boolean;
  use_voi_gating: boolean;
  update_strategy: string;
  max_budget_per_question: number;
}

export interface ExperimentResult {
  id: string;
  name: string;
  experiment_type: string;
  status: string;
  config: AblationConfig;
  brier_score: number;
  log_score: number;
  total_cost: number;
  total_questions: number;
  created_at: string;
  completed_at: string | null;
}

export interface CostSummary {
  total_cost: number;
  cost_per_question: number;
  cost_by_operation: Record<string, number>;
  cost_by_tier: Record<string, number>;
  budget_remaining: number | null;
}

export interface CostLogEntry {
  id: string;
  operation_type: string;
  model_tier: string;
  model_name: string;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  latency_ms: number;
  created_at: string;
}
