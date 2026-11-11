import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { request } from "./client"
import { queryKeys } from "./keys"
import type { WeeklyAnalytics, WeeklyTarget, WeeklyTargetCreate, WeeklyTargetValues } from "./types"

/** `weekOf` is any date in the wanted week; omit for the current week. */
export function useWeeklyAnalytics(weekOf: string | undefined) {
  return useQuery({
    queryKey: queryKeys.analyticsWeekly(weekOf),
    queryFn: () => request<WeeklyAnalytics>("/analytics/weekly", { params: { week_of: weekOf } }),
    // Keep the old week on screen while the next one loads, so charts don't flash to skeletons.
    placeholderData: keepPreviousData,
  })
}

export function useSaveWeeklyTarget() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (args: {
      existingId: number | null
      weekStart: string
      values: WeeklyTargetValues
    }) =>
      args.existingId === null
        ? request<WeeklyTarget>("/weekly-targets", {
            method: "POST",
            body: { week_start: args.weekStart, ...args.values } satisfies WeeklyTargetCreate,
          })
        : request<WeeklyTarget>(`/weekly-targets/${args.existingId}`, {
            method: "PATCH",
            body: args.values,
          }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.analytics })
      void queryClient.invalidateQueries({ queryKey: queryKeys.weeklyTargets })
    },
  })
}
