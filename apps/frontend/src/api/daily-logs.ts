import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { request } from "./client"
import { queryKeys } from "./keys"
import type { DailyLog, DailyLogCreate, DailyLogUpdate, Streak } from "./types"

export function useDailyLogs(from: string, to: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.dailyLogs.range(from, to),
    queryFn: () =>
      request<DailyLog[]>("/daily-logs", { params: { date_from: from, date_to: to, limit: 366 } }),
    enabled,
  })
}

export function useStreak() {
  return useQuery({
    queryKey: queryKeys.dailyLogs.streak,
    queryFn: () => request<Streak>("/daily-logs/streak"),
  })
}

function useInvalidateActivity() {
  const queryClient = useQueryClient()
  return () => {
    void queryClient.invalidateQueries({ queryKey: queryKeys.dailyLogs.all })
    // Weekly totals, trend and the scorecard streak all derive from daily logs.
    void queryClient.invalidateQueries({ queryKey: queryKeys.analytics })
  }
}

export function useCreateDailyLog() {
  const invalidate = useInvalidateActivity()
  return useMutation({
    mutationFn: (body: DailyLogCreate) =>
      request<DailyLog>("/daily-logs", { method: "POST", body }),
    onSuccess: invalidate,
  })
}

export function useUpdateDailyLog() {
  const invalidate = useInvalidateActivity()
  return useMutation({
    mutationFn: ({ id, patch }: { id: number; patch: DailyLogUpdate }) =>
      request<DailyLog>(`/daily-logs/${id}`, { method: "PATCH", body: patch }),
    onSuccess: invalidate,
  })
}
