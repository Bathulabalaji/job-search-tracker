import {
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type Announcements,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core"
import { Kanban, Plus, Search } from "lucide-react"
import { useMemo, useState } from "react"

import type { OpportunityFilters } from "@/api/keys"
import { useMoveOpportunity, useOpportunities } from "@/api/opportunities"
import { SOURCES, STAGES, type Opportunity, type Stage } from "@/api/types"
import { EmptyState } from "@/components/common/empty-state"
import { ErrorState } from "@/components/common/error-state"
import { PageHeader } from "@/components/common/page-header"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { useQuickActions } from "@/features/quick-actions/quick-actions-context"
import { KanbanColumn } from "@/features/pipeline/kanban-column"
import { columnCoordinateGetter } from "@/features/pipeline/keyboard-coordinates"
import { OpportunityCardView } from "@/features/pipeline/opportunity-card"
import { useDebouncedValue } from "@/lib/use-debounced-value"
import { STAGE_LABELS, titleCase } from "@/lib/format"

const ALL = "all"

function isStage(value: unknown): value is Stage {
  return typeof value === "string" && (STAGES as readonly string[]).includes(value)
}

function BoardSkeleton() {
  return (
    <div className="flex gap-4 overflow-hidden" aria-busy="true" aria-label="Loading pipeline">
      {STAGES.slice(0, 5).map((stage) => (
        <Skeleton key={stage} className="h-96 w-72 shrink-0" />
      ))}
    </div>
  )
}

export function PipelinePage() {
  const [priority, setPriority] = useState(ALL)
  const [source, setSource] = useState(ALL)
  const [search, setSearch] = useState("")
  const debouncedSearch = useDebouncedValue(search.trim(), 250)
  const [activeId, setActiveId] = useState<number | null>(null)
  const { openAddOpportunity } = useQuickActions()

  const filters = useMemo<OpportunityFilters>(() => {
    const result: OpportunityFilters = {}
    if (priority !== ALL) result.priority = Number(priority)
    if (source !== ALL) result.source = source
    if (debouncedSearch) result.q = debouncedSearch
    return result
  }, [priority, source, debouncedSearch])
  const hasFilters = Object.keys(filters).length > 0

  const { data, isPending, isError, error, refetch } = useOpportunities(filters)
  const move = useMoveOpportunity()

  const sensors = useSensors(
    // A small distance lets plain clicks (open card) through without starting a drag.
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    useSensor(KeyboardSensor, {
      coordinateGetter: columnCoordinateGetter,
      keyboardCodes: { start: ["Space"], cancel: ["Escape"], end: ["Space"] },
    }),
  )

  const byStage = useMemo(() => {
    const groups = new Map<Stage, Opportunity[]>(STAGES.map((stage) => [stage, []]))
    for (const opportunity of data ?? []) groups.get(opportunity.stage)?.push(opportunity)
    return groups
  }, [data])

  const active = data?.find((o) => o.id === activeId) ?? null

  const announcements: Announcements = {
    onDragStart: ({ active: a }) => `Picked up ${nameOf(data, a.id)}.`,
    onDragOver: ({ over }) => (over && isStage(over.id) ? `Over ${STAGE_LABELS[over.id]}.` : undefined),
    onDragEnd: ({ active: a, over }) =>
      over && isStage(over.id)
        ? `Dropped ${nameOf(data, a.id)} in ${STAGE_LABELS[over.id]}.`
        : `Dropped ${nameOf(data, a.id)}. No change.`,
    onDragCancel: ({ active: a }) => `Cancelled. ${nameOf(data, a.id)} was not moved.`,
  }

  const onDragStart = ({ active: a }: DragStartEvent) => {
    if (typeof a.id === "number") setActiveId(a.id)
  }

  const onDragEnd = ({ active: a, over }: DragEndEvent) => {
    setActiveId(null)
    if (!over || typeof a.id !== "number" || !isStage(over.id)) return
    const opportunity = data?.find((o) => o.id === a.id)
    if (!opportunity || opportunity.stage === over.id) return
    move.mutate({ id: opportunity.id, stage: over.id })
  }

  const isEmpty = data?.length === 0 && !hasFilters

  return (
    <div>
      <PageHeader
        title="Pipeline"
        description="Drag cards between stages. Moving to Applied or Screening schedules a follow-up."
        actions={
          <Button onClick={openAddOpportunity}>
            <Plus />
            Add opportunity
          </Button>
        }
      />

      <div className="mb-6 flex flex-wrap items-center gap-3">
        <div className="relative w-full max-w-xs">
          <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
          <Input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search company or role"
            aria-label="Search company or role"
            className="pl-9"
          />
        </div>
        <Select value={priority} onValueChange={setPriority}>
          <SelectTrigger className="w-40" aria-label="Filter by priority">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All priorities</SelectItem>
            <SelectItem value="1">P1 · High</SelectItem>
            <SelectItem value="2">P2 · Medium</SelectItem>
            <SelectItem value="3">P3 · Low</SelectItem>
          </SelectContent>
        </Select>
        <Select value={source} onValueChange={setSource}>
          <SelectTrigger className="w-40" aria-label="Filter by source">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All sources</SelectItem>
            {SOURCES.map((s) => (
              <SelectItem key={s} value={s}>
                {titleCase(s)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {hasFilters ? (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setPriority(ALL)
              setSource(ALL)
              setSearch("")
            }}
          >
            Clear filters
          </Button>
        ) : null}
      </div>

      {isPending ? <BoardSkeleton /> : null}
      {isError ? <ErrorState message={error.message} onRetry={() => void refetch()} /> : null}
      {isEmpty ? (
        <EmptyState
          icon={Kanban}
          title="No opportunities yet"
          description="Add the first role you are considering. It will start in Found."
          action={<Button onClick={openAddOpportunity}>Add opportunity</Button>}
        />
      ) : null}

      {data && !isEmpty ? (
        <DndContext
          sensors={sensors}
          accessibility={{ announcements }}
          onDragStart={onDragStart}
          onDragEnd={onDragEnd}
          onDragCancel={() => setActiveId(null)}
        >
          <div className="flex gap-4 overflow-x-auto pb-4">
            {STAGES.map((stage) => (
              <KanbanColumn key={stage} stage={stage} opportunities={byStage.get(stage) ?? []} />
            ))}
          </div>
          <DragOverlay dropAnimation={{ duration: 180, easing: "ease-out" }}>
            {active ? <OpportunityCardView opportunity={active} isOverlay /> : null}
          </DragOverlay>
        </DndContext>
      ) : null}
    </div>
  )
}

function nameOf(data: Opportunity[] | undefined, id: string | number): string {
  return data?.find((o) => o.id === id)?.company ?? "card"
}
