import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "@/lib/toast-bus"

import { request } from "./client"
import { queryKeys } from "./keys"
import type { Followup, FollowupCreate, FollowupUpdate, TodayResponse } from "./types"

export function useFollowups(opportunityId: number) {
  return useQuery({
    queryKey: queryKeys.followups(opportunityId),
    queryFn: () =>
      request<Followup[]>("/followups", { params: { opportunity_id: opportunityId, limit: 200 } }),
  })
}

export function useCreateFollowup() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: FollowupCreate) => request<Followup>("/followups", { method: "POST", body }),
    onSuccess: (created) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.followups(created.opportunity_id) })
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] })
    },
  })
}

interface UpdateVariables {
  id: number
  opportunityId: number
  patch: FollowupUpdate
  /** Toast text shown after success, e.g. "Marked done". */
  message?: string
}

interface UpdateContext {
  previous: TodayResponse | undefined
}

/**
 * Done / snooze / skip. Optimistic: the row leaves the Today list at once.
 * (Done, skip and snooze-into-the-future all remove it from "due or overdue".)
 */
export function useUpdateFollowup() {
  const queryClient = useQueryClient()

  return useMutation<Followup, Error, UpdateVariables, UpdateContext>({
    mutationFn: ({ id, patch }) =>
      request<Followup>(`/followups/${id}`, { method: "PATCH", body: patch }),

    onMutate: async ({ id }) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.dashboardToday })
      const previous = queryClient.getQueryData<TodayResponse>(queryKeys.dashboardToday)
      if (previous) {
        queryClient.setQueryData<TodayResponse>(queryKeys.dashboardToday, {
          ...previous,
          followups: previous.followups.filter((f) => f.id !== id),
        })
      }
      return { previous }
    },

    onError: (error, _vars, context) => {
      if (context?.previous) queryClient.setQueryData(queryKeys.dashboardToday, context.previous)
      toast.error("Could not update follow-up", { description: error.message })
    },

    onSuccess: (_data, { message }) => {
      if (message) toast.success(message)
    },

    onSettled: (_data, _error, { opportunityId }) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.dashboardToday })
      void queryClient.invalidateQueries({ queryKey: queryKeys.followups(opportunityId) })
    },
  })
}
