import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { request } from "./client"
import { queryKeys } from "./keys"
import type { Contact, ContactCreate, ContactUpdate } from "./types"

/** Contacts linked to one opportunity (detail page). */
export function useContacts(opportunityId: number) {
  return useQuery({
    queryKey: queryKeys.contacts(opportunityId),
    queryFn: () =>
      request<Contact[]>("/contacts", { params: { opportunity_id: opportunityId, limit: 200 } }),
  })
}

/** All contacts, with optional search and role filter (Contacts page). */
export function useContactsList(filters: { q?: string; role?: string }) {
  return useQuery({
    queryKey: queryKeys.contactsList(filters),
    queryFn: () => request<Contact[]>("/contacts", { params: { ...filters, limit: 200 } }),
    placeholderData: keepPreviousData,
  })
}

function useInvalidateContacts() {
  const queryClient = useQueryClient()
  // Prefix match: covers the per-opportunity lists and the filtered page lists.
  return () => void queryClient.invalidateQueries({ queryKey: queryKeys.contactsAll })
}

export function useCreateContact() {
  const invalidate = useInvalidateContacts()
  return useMutation({
    mutationFn: (body: ContactCreate) => request<Contact>("/contacts", { method: "POST", body }),
    onSuccess: invalidate,
  })
}

export function useUpdateContact() {
  const invalidate = useInvalidateContacts()
  return useMutation({
    mutationFn: ({ id, patch }: { id: number; patch: ContactUpdate }) =>
      request<Contact>(`/contacts/${id}`, { method: "PATCH", body: patch }),
    onSuccess: invalidate,
  })
}

export function useDeleteContact() {
  const invalidate = useInvalidateContacts()
  return useMutation({
    mutationFn: (id: number) => request<void>(`/contacts/${id}`, { method: "DELETE" }),
    onSuccess: invalidate,
  })
}
