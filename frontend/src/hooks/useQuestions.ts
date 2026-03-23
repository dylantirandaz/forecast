import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getQuestions,
  getQuestion,
  createQuestion,
  updateQuestion,
  getScenarios,
} from "@/lib/api";
import type { Question } from "@/types";

export function useQuestions() {
  return useQuery({
    queryKey: ["questions"],
    queryFn: getQuestions,
  });
}

export function useQuestion(id: string) {
  return useQuery({
    queryKey: ["questions", id],
    queryFn: () => getQuestion(id),
    enabled: !!id,
  });
}

export function useScenarios(questionId: string) {
  return useQuery({
    queryKey: ["questions", questionId, "scenarios"],
    queryFn: () => getScenarios(questionId),
    enabled: !!questionId,
  });
}

export function useCreateQuestion() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createQuestion,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["questions"] });
    },
  });
}

export function useUpdateQuestion() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<Question> }) =>
      updateQuestion(id, data),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["questions"] });
      queryClient.invalidateQueries({
        queryKey: ["questions", variables.id],
      });
    },
  });
}
