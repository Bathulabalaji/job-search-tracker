import { ChevronLeft, ChevronRight, Flame, Target } from "lucide-react"
import { useState } from "react"

import { useWeeklyAnalytics } from "@/api/analytics"
import type { Metric, Scorecard } from "@/api/types"
import { EmptyState } from "@/components/common/empty-state"
import { ErrorState } from "@/components/common/error-state"
import { PageHeader } from "@/components/common/page-header"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import {
  ApplicationsPerDayChart,
  FunnelChart,
  ResponseBySourceChart,
  TrendChart,
} from "@/features/analytics/charts"
import { ProgressRing } from "@/features/analytics/progress-ring"
import { TREND_METRICS } from "@/features/analytics/trend-metrics"
import { TargetsDialog } from "@/features/analytics/targets-dialog"
import { addDays, formatPercent, formatShortDate } from "@/lib/format"

function ScoreTile({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-xl border bg-card p-4">
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className="mt-1 font-mono text-2xl font-semibold">{value}</p>
      {hint ? <p className="mt-1 text-xs text-muted-foreground">{hint}</p> : null}
    </div>
  )
}

function ScorecardRow({ card }: { card: Scorecard }) {
  return (
    <section
      aria-label="Scorecard"
      className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-6"
    >
      <ScoreTile
        label="Applications"
        value={String(card.applications_total)}
        hint="Reached Applied"
      />
      <ScoreTile
        label="Response rate"
        value={formatPercent(card.response_rate)}
        hint="Applied that replied"
      />
      <ScoreTile
        label="Interview rate"
        value={formatPercent(card.interview_rate)}
        hint="Applied to interview"
      />
      <ScoreTile label="Offers" value={String(card.offers)} />
      <ScoreTile
        label="Active"
        value={String(card.active_opportunities)}
        hint="Open opportunities"
      />
      <ScoreTile
        label="Streak"
        value={`${card.current_streak}d`}
        hint={card.current_streak > 0 ? "Keep it going" : "Log today to start"}
      />
    </section>
  )
}

function AnalyticsSkeleton() {
  return (
    <div className="space-y-6" aria-busy="true" aria-label="Loading analytics">
      <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-6">
        {Array.from({ length: 6 }, (_, i) => (
          <Skeleton key={i} className="h-24" />
        ))}
      </div>
      <Skeleton className="h-52" />
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Skeleton className="h-80" />
        <Skeleton className="h-80" />
      </div>
    </div>
  )
}

export function AnalyticsPage() {
  const [weekOf, setWeekOf] = useState<string | undefined>(undefined)
  const [metric, setMetric] = useState<Metric>("applications")
  const [targetsOpen, setTargetsOpen] = useState(false)
  const { data, isPending, isError, error, refetch, isPlaceholderData } = useWeeklyAnalytics(weekOf)

  const weekLabel = data
    ? `${formatShortDate(data.week_start)} – ${formatShortDate(data.week_end)}`
    : "Loading…"

  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader
        title="Analytics"
        description="Weekly activity against your targets, and how opportunities move through the funnel."
        actions={
          <>
            <div className="flex items-center gap-1" role="group" aria-label="Choose week">
              <Button
                variant="outline"
                size="icon"
                aria-label="Previous week"
                disabled={!data}
                onClick={() => data && setWeekOf(addDays(data.week_start, -7))}
              >
                <ChevronLeft />
              </Button>
              <span
                className="min-w-32 px-1 text-center font-mono text-sm sm:min-w-36 sm:px-2"
                aria-live="polite"
              >
                {weekLabel}
              </span>
              <Button
                variant="outline"
                size="icon"
                aria-label="Next week"
                disabled={!data}
                onClick={() => data && setWeekOf(addDays(data.week_start, 7))}
              >
                <ChevronRight />
              </Button>
            </div>
            <Button
              variant="ghost"
              disabled={!data || data.is_current_week}
              onClick={() => setWeekOf(undefined)}
            >
              This week
            </Button>
            <Button onClick={() => setTargetsOpen(true)} disabled={!data}>
              <Target />
              Set targets
            </Button>
          </>
        }
      />

      {isPending ? <AnalyticsSkeleton /> : null}
      {isError ? <ErrorState message={error.message} onRetry={() => void refetch()} /> : null}

      {data ? (
        <div
          className={isPlaceholderData ? "space-y-6 opacity-60 transition-opacity" : "space-y-6"}
        >
          <ScorecardRow card={data.scorecard} />

          <Card>
            <CardHeader>
              <CardTitle>Targets vs actual</CardTitle>
              <CardDescription>
                {data.target === null
                  ? "No targets yet. Set them to see progress rings fill."
                  : data.target_carried_over
                    ? `Using targets from the week of ${formatShortDate(data.target.week_start)}.`
                    : "Totals come from your daily logs; interviews come from logged interviews."}
              </CardDescription>
              <CardAction>
                <span className="font-mono text-sm text-muted-foreground">
                  {data.totals.hours_prep}h prep
                </span>
              </CardAction>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-6 sm:grid-cols-3 lg:grid-cols-6">
                {data.progress.map((p) => (
                  <ProgressRing key={p.metric} progress={p} />
                ))}
              </div>
              {data.target === null ? (
                <div className="mt-6">
                  <EmptyState
                    icon={Target}
                    title="Set your first weekly targets"
                    description="Pick realistic weekly numbers for applications, messages and prep. They carry forward until you change them."
                    action={<Button onClick={() => setTargetsOpen(true)}>Set targets</Button>}
                  />
                </div>
              ) : null}
            </CardContent>
          </Card>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Applications per day</CardTitle>
                <CardDescription>{weekLabel}</CardDescription>
              </CardHeader>
              <CardContent>
                {data.totals.applications === 0 && data.daily.every((d) => d.applications === 0) ? (
                  <EmptyState
                    icon={Flame}
                    title="No applications logged this week"
                    description="Use the Daily log page to record what you sent."
                  />
                ) : (
                  <ApplicationsPerDayChart daily={data.daily} />
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Weekly trend</CardTitle>
                <CardDescription>Last {data.trend.length} weeks</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="mb-3 flex flex-wrap gap-1" role="group" aria-label="Trend metric">
                  {TREND_METRICS.map((m) => (
                    <Button
                      key={m.metric}
                      size="sm"
                      variant={metric === m.metric ? "secondary" : "ghost"}
                      aria-pressed={metric === m.metric}
                      onClick={() => setMetric(m.metric)}
                    >
                      {m.label}
                    </Button>
                  ))}
                </div>
                <TrendChart trend={data.trend} metric={metric} />
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Funnel</CardTitle>
                <CardDescription>
                  Opportunities that reached each step, and the share that moved on
                </CardDescription>
              </CardHeader>
              <CardContent>
                {data.funnel[0]?.count === 0 ? (
                  <EmptyState
                    icon={Target}
                    title="No opportunities yet"
                    description="Add one to start the funnel."
                  />
                ) : (
                  <FunnelChart funnel={data.funnel} />
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Response rate by source</CardTitle>
                <CardDescription>Share of applications that got any reply</CardDescription>
              </CardHeader>
              <CardContent>
                {data.response_by_source.every((s) => s.applied === 0) ? (
                  <EmptyState
                    icon={Target}
                    title="Nothing to compare yet"
                    description="Once you apply to roles from a source, replies show up here."
                  />
                ) : (
                  <ResponseBySourceChart sources={data.response_by_source} />
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      ) : null}

      {data ? (
        <TargetsDialog
          open={targetsOpen}
          onOpenChange={setTargetsOpen}
          weekStart={data.week_start}
          target={data.target}
          carriedOver={data.target_carried_over}
        />
      ) : null}
    </div>
  )
}
