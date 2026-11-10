import {
  ArrowRightLeft,
  Bell,
  CalendarClock,
  Mail,
  MessageCircle,
  MessageSquarePlus,
  Phone,
  Users,
  type LucideIcon,
} from "lucide-react"

import { useContacts } from "@/api/contacts"
import { useInteractions } from "@/api/interactions"
import type { Interaction, InteractionType } from "@/api/types"
import { EmptyState } from "@/components/common/empty-state"
import { ErrorState } from "@/components/common/error-state"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { formatDateTime, titleCase } from "@/lib/format"
import { cn } from "@/lib/utils"

const ICONS: Record<InteractionType, LucideIcon> = {
  call: Phone,
  email: Mail,
  linkedin: Users,
  whatsapp: MessageCircle,
  interview: CalendarClock,
  nudge: Bell,
  stage_change: ArrowRightLeft,
}

function TimelineItem({ item, contactName }: { item: Interaction; contactName: string | undefined }) {
  const Icon = ICONS[item.type]
  const system = item.type === "stage_change"
  return (
    <li className="relative flex gap-3 pb-6 last:pb-0 motion-safe:animate-in motion-safe:fade-in motion-safe:duration-300">
      <span
        aria-hidden
        className="absolute top-8 bottom-0 left-4 w-px -translate-x-1/2 bg-border last:hidden"
      />
      <div
        className={cn(
          "z-10 flex size-8 shrink-0 items-center justify-center rounded-full border bg-card",
          system ? "text-muted-foreground" : "text-primary",
        )}
      >
        <Icon className="size-4" aria-hidden />
      </div>
      <div className="min-w-0 flex-1 pt-0.5">
        <div className="flex flex-wrap items-baseline gap-x-2">
          <span className="font-medium">
            {system ? "Stage change" : titleCase(item.type)}
          </span>
          {!system ? (
            <span className="text-xs text-muted-foreground">
              {item.direction === "in" ? "Incoming" : "Outgoing"}
              {contactName ? ` · ${contactName}` : ""}
            </span>
          ) : null}
          <time dateTime={item.occurred_at} className="ml-auto font-mono text-xs text-muted-foreground">
            {formatDateTime(item.occurred_at)}
          </time>
        </div>
        {item.summary ? (
          <p className={cn("mt-1 text-sm", system && "text-muted-foreground")}>{item.summary}</p>
        ) : null}
      </div>
    </li>
  )
}

interface TimelineProps {
  opportunityId: number
  onLog: () => void
}

export function Timeline({ opportunityId, onLog }: TimelineProps) {
  const interactions = useInteractions(opportunityId)
  const contacts = useContacts(opportunityId)
  const names = new Map((contacts.data ?? []).map((c) => [c.id, c.name]))

  if (interactions.isPending) {
    return (
      <div className="space-y-4" aria-busy="true" aria-label="Loading timeline">
        <Skeleton className="h-12" />
        <Skeleton className="h-12" />
        <Skeleton className="h-12" />
      </div>
    )
  }
  if (interactions.isError) {
    return <ErrorState message={interactions.error.message} onRetry={() => void interactions.refetch()} />
  }
  if (interactions.data.length === 0) {
    return (
      <EmptyState
        icon={MessageSquarePlus}
        title="No interactions yet"
        description="Log calls, emails and messages to keep the days-since-contact clock honest."
        action={<Button onClick={onLog}>Log interaction</Button>}
      />
    )
  }
  return (
    <ol>
      {interactions.data.map((item) => (
        <TimelineItem
          key={item.id}
          item={item}
          contactName={item.contact_id === null ? undefined : names.get(item.contact_id)}
        />
      ))}
    </ol>
  )
}
