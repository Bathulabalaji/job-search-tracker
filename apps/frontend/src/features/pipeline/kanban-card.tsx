import { useDraggable } from "@dnd-kit/core"

import type { Opportunity } from "@/api/types"
import { OpportunityCardView } from "./opportunity-card"

export function KanbanCard({ opportunity }: { opportunity: Opportunity }) {
  const { attributes, listeners, setNodeRef, setActivatorNodeRef, isDragging } = useDraggable({
    id: opportunity.id,
    data: { opportunity },
  })

  return (
    <OpportunityCardView
      ref={setNodeRef}
      opportunity={opportunity}
      isDragging={isDragging}
      handleRef={setActivatorNodeRef}
      handleProps={attributes}
      // Pointer drags can start anywhere on the card; keyboard drags only from the handle.
      {...listeners}
    />
  )
}
