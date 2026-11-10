import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { request } from "./client"
import { queryKeys } from "./keys"
import type { Contact, ContactCreate } from "./types"

export function useContacts(opportunityId: number) {
  return useQuery({
    queryKey: queryKeys.contacts(opportunityId),
    queryFn: () =>
      request<Contact[]>("/contacts", { params: { opportunity_id: opportunityId, limit: 200 } }),
  })
}

export function useCreateContact() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: ContactCreate) => request<Contact>("/contacts", { method: "POST", body }),
    onSuccess: (created) => {
      if (created.opportunity_id !== null) {
        void queryClient.invalidateQueries({ queryKey: queryKeys.contacts(created.opportunity_id) })
      }
    },
  })
}
