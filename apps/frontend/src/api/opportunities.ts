import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { request } from "./client"
import { queryKeys, type OpportunityFilters } from "./keys"
import type {
  MoveResponse,
  Opportunity,
  OpportunityCreate,
  OpportunityUpdate,
  Stage,
} from "./types"

export function useOpportunities(filters: OpportunityFilters, enabled = true) {
  return useQuery({
    queryKey: queryKeys.opportunities.list(filters),
    queryFn: () => request<Opportunity[]>("/opportunities", { params: { ...filters, limit: 200 } }),
    enabled,
  })
}

export function useOpportunity(id: number, enabled = true) {
  return useQuery({
    queryKey: queryKeys.opportunities.detail(id),
    queryFn: () => request<Opportunity>(`/opportunities/${id}`),
    enabled,
  })
}

export function useCreateOpportunity() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: OpportunityCreate) =>
      request<Opportunity>("/opportunities", { method: "POST", body }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.opportunities.all })
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] })
    },
  })
}

export function useUpdateOpportunity(id: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: OpportunityUpdate) =>
      request<Opportunity>(`/opportunities/${id}`, { method: "PATCH", body }),
    onSuccess: (updated) => {
      queryClient.setQueryData(queryKeys.opportunities.detail(id), updated)
      void queryClient.invalidateQueries({ queryKey: queryKeys.opportunities.lists })
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] })
    },
  })
}

export function useDeleteOpportunity() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => request<void>(`/opportunities/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.opportunities.all })
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] })
    },
  })
}

interface MoveVariables {
  id: number
  stage: Stage
  note?: string
}

interface MoveContext {
  snapshots: [readonly unknown[], Opportunity[] | undefined][]
  detail: Opportunity | undefined
}

/** Optimistic: the card jumps columns immediately and rolls back if the server refuses. */
export function useMoveOpportunity() {
  const queryClient = useQueryClient()

  return useMutation<MoveResponse, Error, MoveVariables, MoveContext>({
    mutationFn: ({ id, stage, note }) =>
      request<MoveResponse>(`/opportunities/${id}/move`, { method: "POST", body: { stage, note } }),

    onMutate: async ({ id, stage }) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.opportunities.all })
      const snapshots = queryClient.getQueriesData<Opportunity[]>({
        queryKey: queryKeys.opportunities.lists,
      })
      const detail = queryClient.getQueryData<Opportunity>(queryKeys.opportunities.detail(id))

      queryClient.setQueriesData<Opportunity[]>(
        { queryKey: queryKeys.opportunities.lists },
        (old) => old?.map((o) => (o.id === id ? { ...o, stage } : o)),
      )
      if (detail) {
        queryClient.setQueryData<Opportunity>(queryKeys.opportunities.detail(id), {
          ...detail,
          stage,
        })
      }
      return { snapshots, detail }
    },

    onError: (error, { id }, context) => {
      context?.snapshots.forEach(([key, data]) => queryClient.setQueryData(key, data))
      if (context?.detail) {
        queryClient.setQueryData(queryKeys.opportunities.detail(id), context.detail)
      }
      toast.error("Could not move opportunity", { description: error.message })
    },

    onSuccess: (result) => {
      if (result.followup_created) {
        toast.success(`Moved to ${result.opportunity.stage.replace(/_/g, " ")}`, {
          description: `Follow-up scheduled for ${result.followup_created.due_date}`,
        })
      }
    },

    onSettled: (_data, _error, { id }) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.opportunities.all })
      void queryClient.invalidateQueries({ queryKey: queryKeys.interactions(id) })
      void queryClient.invalidateQueries({ queryKey: queryKeys.followups(id) })
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] })
    },
  })
}
