import { Check } from "lucide-react"

import type { MetricProgress } from "@/api/types"
import { cn } from "@/lib/utils"

const SIZE = 104
const STROKE = 10
const RADIUS = (SIZE - STROKE) / 2
const CIRCUMFERENCE = 2 * Math.PI * RADIUS

export function ProgressRing({ progress }: { progress: MetricProgress }) {
  const { label, actual, target, percent } = progress
  const hasTarget = target !== null && target > 0
  const fraction = hasTarget && percent !== null ? Math.min(percent, 100) / 100 : 0
  const met = hasTarget && percent !== null && percent >= 100

  const description = hasTarget
    ? `${label}: ${actual} of ${target}, ${Math.round(percent ?? 0)} percent${met ? ", target met" : ""}`
    : `${label}: ${actual}, no target set`

  return (
    <figure className="flex flex-col items-center gap-2">
      <div className="relative" style={{ width: SIZE, height: SIZE }}>
        <svg
          role="img"
          aria-label={description}
          width={SIZE}
          height={SIZE}
          viewBox={`0 0 ${SIZE} ${SIZE}`}
          className="-rotate-90"
        >
          <circle
            cx={SIZE / 2}
            cy={SIZE / 2}
            r={RADIUS}
            fill="none"
            stroke="var(--border)"
            strokeWidth={STROKE}
            strokeDasharray={hasTarget ? undefined : "3 6"}
          />
          {fraction > 0 ? (
            <circle
              cx={SIZE / 2}
              cy={SIZE / 2}
              r={RADIUS}
              fill="none"
              stroke="var(--primary)"
              strokeWidth={STROKE}
              strokeLinecap="round"
              strokeDasharray={CIRCUMFERENCE}
              strokeDashoffset={CIRCUMFERENCE * (1 - fraction)}
              className="transition-[stroke-dashoffset] duration-700 ease-out motion-reduce:transition-none"
            />
          ) : null}
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center" aria-hidden>
          <span className="font-mono text-2xl font-semibold leading-none">{actual}</span>
          <span className="mt-1 font-mono text-xs text-muted-foreground">
            {hasTarget ? `/ ${target}` : "no target"}
          </span>
        </div>
      </div>
      <figcaption className="text-center">
        <span className="block text-sm font-medium">{label}</span>
        <span
          className={cn(
            "inline-flex items-center gap-1 font-mono text-xs",
            met ? "text-emerald-700 dark:text-emerald-300" : "text-muted-foreground",
          )}
        >
          {met ? <Check className="size-3" aria-hidden /> : null}
          {hasTarget && percent !== null ? `${Math.round(percent)}%` : "—"}
          {met ? <span className="sr-only">target met</span> : null}
        </span>
      </figcaption>
    </figure>
  )
}
