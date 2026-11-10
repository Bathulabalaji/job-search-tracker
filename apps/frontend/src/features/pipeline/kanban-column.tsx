import { useDroppable } from "@dnd-kit/core"

import type { Opportunity, Stage } from "@/api/types"
import { StageBadge } from "@/components/common/stage-badge"
import { cn } from "@/lib/utils"
import { KanbanCard } from "./kanban-card"

interface KanbanColumnProps {
  stage: Stage
  opportunities: Opportunity[]
}

export function KanbanColumn({ stage, opportunities }: KanbanColumnProps) {
  const { setNodeRef, isOver } = useDroppable({ id: stage })

  return (
    <section
      aria-label={`${stage.replace(/_/g, " ")} column, ${opportunities.length} opportunities`}
      className={cn(
        "flex min-h-48 w-[82vw] max-w-72 shrink-0 snap-start flex-col md:max-h-[calc(100dvh-15rem)] sm:w-72 rounded-xl border bg-muted/30 transition-colors duration-150",
        isOver && "border-primary/60 bg-primary/5 ring-2 ring-primary/30",
      )}
    >
      <header className="flex items-center justify-between px-3 py-3">
        <StageBadge stage={stage} />
        <span className="font-mono text-xs text-muted-foreground">{opportunities.length}</span>
      </header>
      <div ref={setNodeRef} className="flex-1 space-y-2 overflow-y-auto px-2 pb-2">
        {opportunities.map((opportunity) => (
          <KanbanCard key={opportunity.id} opportunity={opportunity} />
        ))}
        {opportunities.length === 0 ? (
          <p className="rounded-lg border border-dashed px-3 py-6 text-center text-xs text-muted-foreground">
            Drop a card here
          </p>
        ) : null}
      </div>
    </section>
  )
}
