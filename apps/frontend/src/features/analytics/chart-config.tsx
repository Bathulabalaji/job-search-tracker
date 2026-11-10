import type { ReactNode } from "react"
import type { TooltipContentProps } from "recharts"

/** Shared look for every chart tooltip: surface card, secondary label, mono values. */
export function tooltipFor<Row>(render: (row: Row) => ReactNode) {
  return function ChartTooltip({ active, payload }: TooltipContentProps) {
    if (!active) return null
    // Recharts types the payload as any; each chart passes its own row type.
    const row = payload[0]?.payload as Row | undefined
    if (row === undefined) return null
    return (
      <div className="rounded-lg border bg-popover px-3 py-2 text-sm text-popover-foreground shadow-md">
        {render(row)}
      </div>
    )
  }
}

export const AXIS_TICK = { fill: "var(--muted-foreground)", fontSize: 12 } as const
export const GRID_STROKE = "var(--border)"
export const SERIES_COLOR = "var(--primary)"
