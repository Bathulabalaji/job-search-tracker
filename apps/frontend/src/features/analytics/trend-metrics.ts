import type { Metric } from "@/api/types"

export const TREND_METRICS: readonly { metric: Metric; label: string }[] = [
  { metric: "applications", label: "Applications" },
  { metric: "messages", label: "Messages" },
  { metric: "referrals", label: "Referrals" },
  { metric: "problems", label: "Problems" },
  { metric: "mocks", label: "Mocks" },
  { metric: "interviews", label: "Interviews" },
]
