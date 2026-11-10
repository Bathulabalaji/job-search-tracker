import { useDraggable } from "@dnd-kit/core"

import { useMoveOpportunity } from "@/api/opportunities"
import type { Opportunity } from "@/api/types"
import { OpportunityCardView } from "./opportunity-card"

export function KanbanCard({ opportunity }: { opportunity: Opportunity }) {
  const { attributes, listeners, setNodeRef, setActivatorNodeRef, isDragging } = useDraggable({
    id: opportunity.id,
    data: { opportunity },
  })

  const move = useMoveOpportunity()

  return (
    <OpportunityCardView
      ref={setNodeRef}
      opportunity={opportunity}
      isDragging={isDragging}
      onMove={(stage) => move.mutate({ id: opportunity.id, stage })}
      handleRef={setActivatorNodeRef}
      handleProps={attributes}
      // Pointer drags can start anywhere on the card; keyboard drags only from the handle.
      {...listeners}
    />
  )
}
