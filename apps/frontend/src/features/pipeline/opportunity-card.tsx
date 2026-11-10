import { Clock, EllipsisVertical, GripVertical } from "lucide-react"
import type { HTMLAttributes, Ref } from "react"
import { Link } from "react-router-dom"

import { STAGES, type Opportunity, type Stage } from "@/api/types"
import { PriorityBadge } from "@/components/common/priority-badge"
import { Badge } from "@/components/ui/badge"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { STAGE_LABELS } from "@/lib/format"
import { cn } from "@/lib/utils"

function contactLabel(days: number): string {
  return days === 0 ? "today" : `${days}d`
}

interface CardViewProps extends HTMLAttributes<HTMLDivElement> {
  opportunity: Opportunity
  /** Drag handle props; omitted for the floating drag preview. */
  handleProps?: HTMLAttributes<HTMLButtonElement> | undefined
  handleRef?: Ref<HTMLButtonElement> | undefined
  isDragging?: boolean
  isOverlay?: boolean
  /** Tap-friendly alternative to dragging. */
  onMove?: ((stage: Stage) => void) | undefined
  ref?: Ref<HTMLDivElement> | undefined
}

/** Presentational card, shared by the in-column card and the DragOverlay preview. */
export function OpportunityCardView({
  opportunity: o,
  handleProps,
  handleRef,
  isDragging = false,
  isOverlay = false,
  onMove,
  className,
  ref,
  ...rest
}: CardViewProps) {
  const tags = o.stack_tags.slice(0, 3)
  const extraTags = o.stack_tags.length - tags.length

  return (
    <div
      ref={ref}
      {...rest}
      className={cn(
        "group relative touch-manipulation rounded-lg border bg-card p-3 text-card-foreground shadow-xs transition-[box-shadow,opacity,border-color] duration-150",
        "hover:border-primary/40 focus-within:border-primary/60",
        isDragging && "opacity-40",
        isOverlay && "rotate-1 cursor-grabbing border-primary/60 shadow-lg",
        !isOverlay && "cursor-grab",
        className,
      )}
    >
      <div className="flex items-start gap-2">
        <div className="min-w-0 flex-1">
          {isOverlay ? (
            <p className="truncate font-medium">{o.company}</p>
          ) : (
            <Link
              to={`/opportunities/${o.id}`}
              className="block truncate rounded-sm font-medium hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
            >
              {o.company}
            </Link>
          )}
          <p className="truncate text-sm text-muted-foreground">{o.role}</p>
        </div>
        {onMove ? (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                type="button"
                aria-label={`Move ${o.company} to another stage`}
                className="-my-1 rounded p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring sm:p-1"
              >
                <EllipsisVertical className="size-4" aria-hidden />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="max-h-72 overflow-y-auto">
              <DropdownMenuLabel>Move to</DropdownMenuLabel>
              {STAGES.filter((stage) => stage !== o.stage).map((stage) => (
                <DropdownMenuItem key={stage} onSelect={() => onMove(stage)}>
                  {STAGE_LABELS[stage]}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        ) : null}
        <button
          type="button"
          ref={handleRef}
          {...handleProps}
          aria-label={`Move ${o.company}. Press space to pick up, arrow keys to change column.`}
          className="-my-1 -mr-1 hidden rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring [@media(pointer:fine)]:block"
        >
          <GripVertical className="size-4" aria-hidden />
        </button>
      </div>

      {tags.length > 0 ? (
        <div className="mt-2 flex flex-wrap gap-1">
          {tags.map((tag) => (
            <Badge key={tag} variant="secondary" className="px-1.5 py-0 text-[11px] font-normal">
              {tag}
            </Badge>
          ))}
          {extraTags > 0 ? (
            <span className="self-center text-[11px] text-muted-foreground">+{extraTags}</span>
          ) : null}
        </div>
      ) : null}

      <div className="mt-3 flex items-center gap-3 text-xs">
        <PriorityBadge priority={o.priority} />
        {o.fit_score !== null ? (
          <span className="font-mono text-muted-foreground" title="Fit score">
            fit {o.fit_score}
          </span>
        ) : null}
        <span
          className="ml-auto inline-flex items-center gap-1 font-mono text-muted-foreground"
          title="Days since last contact"
        >
          <Clock className="size-3" aria-hidden />
          <span className="sr-only">Days since contact: </span>
          {contactLabel(o.days_since_contact)}
        </span>
      </div>

      {o.ghosted_suggestion ? (
        <p className="mt-2 rounded bg-amber-500/15 px-2 py-1 text-xs text-amber-800 dark:text-amber-300">
          No contact for {o.days_since_contact} days. Ghosted?
        </p>
      ) : null}
    </div>
  )
}
