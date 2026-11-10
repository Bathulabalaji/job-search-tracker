import { Check, Clock, Mail, MessageCircle, Phone, Users, type LucideIcon } from "lucide-react"
import { Link } from "react-router-dom"

import { useUpdateFollowup } from "@/api/followups"
import type { FollowupChannel, TodayFollowup } from "@/api/types"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { addDays, daysUntilNextMonday, formatDate, titleCase } from "@/lib/format"
import { cn } from "@/lib/utils"

const CHANNEL_ICONS: Record<FollowupChannel, LucideIcon> = {
  email: Mail,
  call: Phone,
  linkedin: Users,
  whatsapp: MessageCircle,
}

interface FollowupRowProps {
  followup: TodayFollowup
  today: string
}

export function FollowupRow({ followup, today }: FollowupRowProps) {
  const update = useUpdateFollowup()
  const ChannelIcon = CHANNEL_ICONS[followup.channel]
  const overdue = followup.days_overdue > 0

  const snoozeOptions = [
    { label: "Tomorrow", days: 1 },
    { label: "In 3 days", days: 3 },
    { label: "Next Monday", days: daysUntilNextMonday(today) },
  ]

  const done = () =>
    update.mutate({
      id: followup.id,
      opportunityId: followup.opportunity_id,
      patch: { status: "done" },
      message: `Follow-up with ${followup.company} marked done`,
    })

  const snooze = (days: number) => {
    const due = addDays(today, days)
    update.mutate({
      id: followup.id,
      opportunityId: followup.opportunity_id,
      patch: { due_date: due },
      message: `Snoozed until ${formatDate(due)}`,
    })
  }

  return (
    <li className="flex items-start gap-3 py-4 motion-safe:animate-in motion-safe:fade-in motion-safe:duration-300">
      <div className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground">
        <ChannelIcon className="size-4" aria-hidden />
        <span className="sr-only">{titleCase(followup.channel)}</span>
      </div>

      <div className="min-w-0 flex-1 space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <Link
            to={`/opportunities/${followup.opportunity_id}`}
            className="rounded-sm font-medium hover:underline focus-visible:outline-2 focus-visible:outline-ring"
          >
            {followup.company}
          </Link>
          <span className="text-sm text-muted-foreground">{followup.role}</span>
          <Badge
            variant="outline"
            className={cn(
              "border-transparent font-mono",
              overdue
                ? "bg-red-500/15 text-red-800 dark:text-red-300"
                : "bg-indigo-500/15 text-indigo-800 dark:text-indigo-300",
            )}
          >
            {overdue ? `Overdue ${followup.days_overdue}d` : "Due today"}
          </Badge>
        </div>
        {followup.message_draft ? (
          <p className="line-clamp-2 text-sm text-muted-foreground">{followup.message_draft}</p>
        ) : null}
        <p className="font-mono text-xs text-muted-foreground">Due {formatDate(followup.due_date)}</p>
      </div>

      <div className="flex shrink-0 items-center gap-1">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="sm" disabled={update.isPending}>
              <Clock />
              Snooze
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            {snoozeOptions.map((option) => (
              <DropdownMenuItem key={option.label} onSelect={() => snooze(option.days)}>
                {option.label}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
        <Button size="sm" onClick={done} disabled={update.isPending}>
          <Check />
          Done
        </Button>
      </div>
    </li>
  )
}
