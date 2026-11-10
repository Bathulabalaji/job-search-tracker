import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { request } from "./client"
import { queryKeys } from "./keys"
import type { Resume, ResumeCreate, ResumeUpdate } from "./types"

export function useResumes(q: string) {
  return useQuery({
    queryKey: queryKeys.resumes(q),
    queryFn: () => request<Resume[]>("/resumes", { params: { q, limit: 200 } }),
    placeholderData: keepPreviousData,
  })
}

function useInvalidateResumes() {
  const queryClient = useQueryClient()
  return () => void queryClient.invalidateQueries({ queryKey: queryKeys.resumesAll })
}

export function useCreateResume() {
  const invalidate = useInvalidateResumes()
  return useMutation({
    mutationFn: (body: ResumeCreate) => request<Resume>("/resumes", { method: "POST", body }),
    onSuccess: invalidate,
  })
}

export function useUpdateResume() {
  const invalidate = useInvalidateResumes()
  return useMutation({
    mutationFn: ({ id, patch }: { id: number; patch: ResumeUpdate }) =>
      request<Resume>(`/resumes/${id}`, { method: "PATCH", body: patch }),
    onSuccess: invalidate,
  })
}

export function useDeleteResume() {
  const invalidate = useInvalidateResumes()
  return useMutation({
    mutationFn: (id: number) => request<void>(`/resumes/${id}`, { method: "DELETE" }),
    onSuccess: invalidate,
  })
}
