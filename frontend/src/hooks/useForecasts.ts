import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getForecastRuns,
  getLatestForecast,
  triggerForecastRun,
  getForecastUpdates,
  getCalibrationMetrics,
  getBacktestRuns,
  getBacktestRun,
  getEvidence,
} from "@/lib/api";

export function useForecastRuns(questionId: string) {
  return useQuery({
    queryKey: ["forecasts", questionId],
    queryFn: () => getForecastRuns(questionId),
    enabled: !!questionId,
  });
}

export function useLatestForecast(questionId: string) {
  return useQuery({
    queryKey: ["forecasts", questionId, "latest"],
    queryFn: () => getLatestForecast(questionId),
    enabled: !!questionId,
  });
}

export function useForecastUpdates(questionId: string) {
  return useQuery({
    queryKey: ["forecasts", questionId, "updates"],
    queryFn: () => getForecastUpdates(questionId),
    enabled: !!questionId,
  });
}

export function useTriggerForecastRun(questionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => triggerForecastRun(questionId),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["forecasts", questionId],
      });
    },
  });
}

export function useCalibrationMetrics() {
  return useQuery({
    queryKey: ["calibration"],
    queryFn: getCalibrationMetrics,
  });
}

export function useBacktestRuns() {
  return useQuery({
    queryKey: ["backtests"],
    queryFn: getBacktestRuns,
  });
}

export function useBacktestRun(id: string) {
  return useQuery({
    queryKey: ["backtests", id],
    queryFn: () => getBacktestRun(id),
    enabled: !!id,
  });
}

export function useEvidence(params?: {
  question_id?: string;
  source_type?: string;
  direction?: string;
  min_date?: string;
  max_date?: string;
}) {
  return useQuery({
    queryKey: ["evidence", params],
    queryFn: () => getEvidence(params),
  });
}
