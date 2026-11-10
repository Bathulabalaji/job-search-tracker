import { useQuery } from "@tanstack/react-query"

import { request } from "./client"
import { queryKeys } from "./keys"
import type { TodayResponse } from "./types"

export function useToday() {
  return useQuery({
    queryKey: queryKeys.dashboardToday,
    queryFn: () => request<TodayResponse>("/dashboard/today"),
  })
}
