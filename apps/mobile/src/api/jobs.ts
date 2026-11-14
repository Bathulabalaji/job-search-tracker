import { useMutation, useQueryClient } from "@tanstack/react-query";

import { request } from "./client";
import type { Opportunity } from "./types";

/** Add a job search result to the pipeline as a new opportunity. */
export function useTrackJob() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      request<Opportunity>(`/jobs/${id}/track`, { method: "POST", body: {} }),
    onSuccess: () => {
      for (const family of ["opportunities", "dashboard", "analytics"]) {
        void queryClient.invalidateQueries({ queryKey: [family] });
      }
    },
  });
}
