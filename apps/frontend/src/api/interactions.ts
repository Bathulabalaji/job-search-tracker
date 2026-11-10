import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { request } from "./client"
import { queryKeys } from "./keys"
import type { Interaction, InteractionCreate } from "./types"

export function useInteractions(opportunityId: number) {
  return useQuery({
    queryKey: queryKeys.interactions(opportunityId),
    queryFn: () =>
      request<Interaction[]>("/interactions", {
        params: { opportunity_id: opportunityId, limit: 200 },
      }),
  })
}

export function useCreateInteraction() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: InteractionCreate) =>
      request<Interaction>("/interactions", { method: "POST", body }),
    onSuccess: (created) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.interactions(created.opportunity_id) })
      // days_since_contact changes on cards and the detail header.
      void queryClient.invalidateQueries({ queryKey: queryKeys.opportunities.all })
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] })
    },
  })
}
