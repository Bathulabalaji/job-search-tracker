import { ArrowRight, CalendarCheck, CalendarClock, CheckCircle2, Target } from "lucide-react"
import { Link } from "react-router-dom"

import { useToday } from "@/api/dashboard"
import type { NextAction, TodayInterview } from "@/api/types"
import { EmptyState } from "@/components/common/empty-state"
import { ErrorState } from "@/components/common/error-state"
import { PageHeader } from "@/components/common/page-header"
import { PriorityBadge } from "@/components/common/priority-badge"
import { StageBadge } from "@/components/common/stage-badge"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { FollowupRow } from "@/features/today/followup-row"
import { useQuickActions } from "@/features/quick-actions/quick-actions-context"
import { formatDate, formatTime } from "@/lib/format"
import { cn } from "@/lib/utils"

function CountBadge({ count }: { count: number }) {
  return (
    <Badge variant="secondary" className="font-mono">
      {count}
    </Badge>
  )
}

function InterviewItem({ interview }: { interview: TodayInterview }) {
  return (
    <li className="flex items-start gap-3 py-3">
      <span className="mt-0.5 w-14 shrink-0 font-mono text-sm text-primary">
        {formatTime(interview.occurred_at)}
      </span>
      <div className="min-w-0">
        <Link
          to={`/opportunities/${interview.opportunity_id}`}
          className="rounded-sm font-medium hover:underline"
        >
          {interview.company}
        </Link>
        <p className="text-sm text-muted-foreground">{interview.role}</p>
        {interview.summary ? <p className="mt-1 text-sm">{interview.summary}</p> : null}
      </div>
    </li>
  )
}

function NextActionItem({ action, index }: { action: NextAction; index: number }) {
  return (
    <li>
      <Link
        to={`/opportunities/${action.opportunity_id}`}
        className="group flex items-start gap-3 rounded-md py-3 outline-offset-4 focus-visible:outline-2 focus-visible:outline-ring"
      >
        <span className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full bg-primary/15 font-mono text-xs text-primary">
          {index + 1}
        </span>
        <div className="min-w-0 flex-1 space-y-1">
          <p className="font-medium group-hover:underline">{action.next_action}</p>
          <p className="truncate text-sm text-muted-foreground">
            {action.company} · {action.role}
          </p>
          <div className="flex flex-wrap items-center gap-2">
            <StageBadge stage={action.stage} />
            <PriorityBadge priority={action.priority} />
            {action.next_action_due ? (
              <span
                className={cn(
                  "font-mono text-xs",
                  action.overdue ? "text-red-700 dark:text-red-300" : "text-muted-foreground",
                )}
              >
                {action.overdue ? "Overdue · " : ""}
                {formatDate(action.next_action_due)}
              </span>
            ) : null}
          </div>
        </div>
        <ArrowRight
          className="mt-1 size-4 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100"
          aria-hidden
        />
      </Link>
    </li>
  )
}

function TodaySkeleton() {
  return (
    <div
      className="grid grid-cols-1 gap-6 lg:grid-cols-3"
      aria-busy="true"
      aria-label="Loading today"
    >
      <Skeleton className="h-96 lg:col-span-2" />
      <div className="space-y-6">
        <Skeleton className="h-40" />
        <Skeleton className="h-56" />
      </div>
    </div>
  )
}

export function TodayPage() {
  const { data, isPending, isError, error, refetch } = useToday()
  const { openAddOpportunity } = useQuickActions()

  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader
        title="Today"
        description={
          data ? (
            <span className="font-mono">{formatDate(data.today)}</span>
          ) : (
            "Your day at a glance"
          )
        }
      />

      {isPending ? <TodaySkeleton /> : null}
      {isError ? <ErrorState message={error.message} onRetry={() => void refetch()} /> : null}

      {data ? (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <Card className="min-w-0 lg:col-span-2">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <CalendarCheck className="size-4 text-primary" aria-hidden />
                Follow-ups
                <CountBadge count={data.followups.length} />
              </CardTitle>
            </CardHeader>
            <CardContent>
              {data.followups.length === 0 ? (
                <EmptyState
                  icon={CheckCircle2}
                  title="All caught up"
                  description="No follow-ups are due or overdue. Moving an opportunity to Applied schedules one automatically."
                />
              ) : (
                <ul className="divide-y">
                  {data.followups.map((followup) => (
                    <FollowupRow key={followup.id} followup={followup} today={data.today} />
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>

          <div className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <CalendarClock className="size-4 text-primary" aria-hidden />
                  Interviews today
                  <CountBadge count={data.interviews.length} />
                </CardTitle>
              </CardHeader>
              <CardContent>
                {data.interviews.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    No interviews today. Log one on an opportunity to see it here.
                  </p>
                ) : (
                  <ul className="divide-y">
                    {data.interviews.map((interview) => (
                      <InterviewItem key={interview.interaction_id} interview={interview} />
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Target className="size-4 text-primary" aria-hidden />
                  Top next actions
                </CardTitle>
              </CardHeader>
              <CardContent>
                {data.next_actions.length === 0 ? (
                  <EmptyState
                    icon={Target}
                    title="No next actions set"
                    description="Add a next action on an opportunity and the most urgent three show up here."
                    action={
                      <Button size="sm" variant="outline" onClick={openAddOpportunity}>
                        Add opportunity
                      </Button>
                    }
                  />
                ) : (
                  <ol className="divide-y">
                    {data.next_actions.map((action, index) => (
                      <NextActionItem key={action.opportunity_id} action={action} index={index} />
                    ))}
                  </ol>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      ) : null}
    </div>
  )
}
