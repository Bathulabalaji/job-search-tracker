import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "@/lib/toast-bus"

import { request } from "./client"
import { queryKeys } from "./keys"
import type { PrepItem, PrepItemCreate, PrepItemUpdate } from "./types"

export function usePrepItems() {
  return useQuery({
    queryKey: queryKeys.prepItems,
    queryFn: () => request<PrepItem[]>("/prep-items", { params: { limit: 500 } }),
  })
}

export function useCreatePrepItem() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: PrepItemCreate) =>
      request<PrepItem>("/prep-items", { method: "POST", body }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: queryKeys.prepItems }),
  })
}

interface UpdateVariables {
  id: number
  patch: PrepItemUpdate
}

/** Optimistic: ticking a box or rating confidence feels instant, and rolls back on error. */
export function useUpdatePrepItem() {
  const queryClient = useQueryClient()
  return useMutation<PrepItem, Error, UpdateVariables, { previous: PrepItem[] | undefined }>({
    mutationFn: ({ id, patch }) =>
      request<PrepItem>(`/prep-items/${id}`, { method: "PATCH", body: patch }),
    onMutate: async ({ id, patch }) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.prepItems })
      const previous = queryClient.getQueryData<PrepItem[]>(queryKeys.prepItems)
      queryClient.setQueryData<PrepItem[]>(queryKeys.prepItems, (old) =>
        old?.map((item) => (item.id === id ? { ...item, ...patch } : item)),
      )
      return { previous }
    },
    onError: (error, _vars, context) => {
      if (context?.previous) queryClient.setQueryData(queryKeys.prepItems, context.previous)
      toast.error("Could not update prep item", { description: error.message })
    },
    onSettled: () => void queryClient.invalidateQueries({ queryKey: queryKeys.prepItems }),
  })
}

export function useDeletePrepItem() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => request<void>(`/prep-items/${id}`, { method: "DELETE" }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: queryKeys.prepItems }),
  })
}
