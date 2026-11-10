import type { Stage } from "@/api/types"
import { Badge } from "@/components/ui/badge"
import { STAGE_LABELS } from "@/lib/format"
import { cn } from "@/lib/utils"

const TONES: Record<Stage, string> = {
  found: "bg-slate-500/15 text-slate-700 dark:text-slate-300",
  applied: "bg-indigo-500/15 text-indigo-700 dark:text-indigo-300",
  screening: "bg-violet-500/15 text-violet-700 dark:text-violet-300",
  interview_scheduled: "bg-sky-500/15 text-sky-700 dark:text-sky-300",
  interviewing: "bg-cyan-500/15 text-cyan-800 dark:text-cyan-300",
  offer: "bg-emerald-500/15 text-emerald-800 dark:text-emerald-300",
  accepted: "bg-emerald-500/25 text-emerald-900 dark:text-emerald-200",
  rejected: "bg-red-500/15 text-red-800 dark:text-red-300",
  ghosted: "bg-amber-500/15 text-amber-800 dark:text-amber-300",
  parked: "bg-slate-500/10 text-slate-600 dark:text-slate-400",
}

export function StageBadge({ stage, className }: { stage: Stage; className?: string }) {
  return (
    <Badge variant="outline" className={cn("border-transparent", TONES[stage], className)}>
      {STAGE_LABELS[stage]}
    </Badge>
  )
}
