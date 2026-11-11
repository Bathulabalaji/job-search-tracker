import type { Stage } from "@/api/types"
import { Badge } from "@/components/ui/badge"
import { PRIORITY_LABELS, STAGE_LABELS } from "@/lib/format"

type Tone = "neutral" | "primary" | "success" | "warning" | "danger" | "info"

export const STAGE_TONES: Record<Stage, Tone> = {
  found: "neutral",
  applied: "info",
  screening: "warning",
  interview_scheduled: "primary",
  interviewing: "primary",
  offer: "success",
  accepted: "success",
  rejected: "danger",
  ghosted: "neutral",
  parked: "neutral",
}

export function StageBadge({ stage }: { stage: Stage }) {
  return <Badge label={STAGE_LABELS[stage]} tone={STAGE_TONES[stage]} />
}

export function PriorityBadge({ priority }: { priority: number }) {
  const tone = priority === 1 ? "danger" : priority === 2 ? "warning" : "neutral"
  return <Badge label={`${PRIORITY_LABELS[priority] ?? "Medium"} priority`} tone={tone} />
}
