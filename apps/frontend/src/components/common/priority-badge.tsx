import { Flag } from "lucide-react"

import { PRIORITY_LABELS } from "@/lib/format"
import { cn } from "@/lib/utils"

const TONES: Record<number, string> = {
  1: "text-red-700 dark:text-red-300",
  2: "text-amber-700 dark:text-amber-300",
  3: "text-muted-foreground",
}

export function PriorityBadge({ priority, className }: { priority: number; className?: string }) {
  const label = PRIORITY_LABELS[priority] ?? `P${priority}`
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 text-xs font-medium",
        TONES[priority],
        className,
      )}
      title={`${label} priority`}
    >
      <Flag className="size-3" aria-hidden />
      <span className="sr-only">{label} priority</span>
      <span aria-hidden>P{priority}</span>
    </span>
  )
}
