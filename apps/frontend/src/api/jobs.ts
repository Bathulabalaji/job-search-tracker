import { useMutation, useQueryClient } from "@tanstack/react-query"

import { request } from "./client"
import type { Opportunity } from "./types"

export interface TrackJobBody {
  priority?: 1 | 2 | 3
  stage?: "found" | "applied"
}

/** Add a job search result to the pipeline as a new opportunity. */
export function useTrackJob() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, body }: { id: number; body?: TrackJobBody }) =>
      request<Opportunity>(`/jobs/${id}/track`, { method: "POST", body: body ?? {} }),
    onSuccess: () => {
      for (const family of ["opportunities", "dashboard", "analytics"]) {
        void queryClient.invalidateQueries({ queryKey: [family] })
      }
    },
  })
}
