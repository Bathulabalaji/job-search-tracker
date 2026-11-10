import { CalendarDays, Check, Flame } from "lucide-react"
import { useState } from "react"

import { useDailyLogs, useStreak } from "@/api/daily-logs"
import { EmptyState } from "@/components/common/empty-state"
import { ErrorState } from "@/components/common/error-state"
import { PageHeader } from "@/components/common/page-header"
import { Field } from "@/components/form/field"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { LogForm } from "@/features/daily-log/log-form"
import { addDays, formatDate } from "@/lib/format"

const HISTORY_DAYS = 14

function StreakCard() {
  const { data, isPending, isError } = useStreak()
  if (isPending) return <Skeleton className="h-40" />
  if (isError) return null

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Flame className="size-4 text-primary" aria-hidden />
          Streak
        </CardTitle>
        <CardDescription>Days in a row with any activity logged</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <p
          className="font-mono text-5xl font-semibold tracking-tight"
          aria-label={`${data.current} day streak`}
        >
          {data.current}
          <span className="ml-1 text-lg font-normal text-muted-foreground">
            {data.current === 1 ? "day" : "days"}
          </span>
        </p>
        <p className="text-sm text-muted-foreground">
          Longest: <span className="font-mono">{data.longest}</span>
        </p>
        {data.logged_today ? (
          <p className="inline-flex items-center gap-1 text-sm text-emerald-700 dark:text-emerald-300">
            <Check className="size-4" aria-hidden />
            Today is logged
          </p>
        ) : (
          <p className="text-sm">
            {data.current > 0 ? "Log today to keep it going." : "Log today to start a streak."}
          </p>
        )}
      </CardContent>
    </Card>
  )
}

export function DailyLogPage() {
  const streak = useStreak()
  const [picked, setPicked] = useState<string | null>(null)
  const today = streak.data?.today
  const date = picked ?? today

  const day = useDailyLogs(date ?? "", date ?? "", date !== undefined)
  const history = useDailyLogs(
    addDays(today ?? "1970-01-01", -(HISTORY_DAYS - 1)),
    today ?? "",
    today !== undefined,
  )

  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader
        title="Daily log"
        description="Numbers only, under a minute. These feed the weekly targets on the Analytics page."
      />

      {streak.isError ? (
        <ErrorState message={streak.error.message} onRetry={() => void streak.refetch()} />
      ) : (
        <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-3">
          <Card className="min-w-0 lg:col-span-2">
            <CardHeader>
              <CardTitle>{date ? formatDate(date) : "Loading…"}</CardTitle>
              <CardDescription>
                <div className="mt-2 max-w-48">
                  <Field label="Date">
                    {(a11y) => (
                      <Input
                        {...a11y}
                        type="date"
                        value={date ?? ""}
                        max={today}
                        className="font-mono"
                        onChange={(event) => setPicked(event.target.value || null)}
                      />
                    )}
                  </Field>
                </div>
              </CardDescription>
            </CardHeader>
            <CardContent>
              {date === undefined || day.isPending ? (
                <div className="space-y-4" aria-busy="true" aria-label="Loading log">
                  <Skeleton className="h-24" />
                  <Skeleton className="h-10 w-32" />
                </div>
              ) : day.isError ? (
                <ErrorState message={day.error.message} onRetry={() => void day.refetch()} />
              ) : (
                <LogForm
                  key={`${date}-${day.data[0]?.id ?? "new"}`}
                  date={date}
                  existing={day.data[0]}
                />
              )}
            </CardContent>
          </Card>

          <StreakCard />
        </div>
      )}

      <Card className="mt-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <CalendarDays className="size-4 text-primary" aria-hidden />
            Last {HISTORY_DAYS} days
          </CardTitle>
          <CardDescription>Select a date to edit it.</CardDescription>
        </CardHeader>
        <CardContent>
          {history.isPending ? <Skeleton className="h-40" /> : null}
          {history.isError ? (
            <ErrorState message={history.error.message} onRetry={() => void history.refetch()} />
          ) : null}
          {history.data?.length === 0 ? (
            <EmptyState
              icon={CalendarDays}
              title="No logs yet"
              description="Save today's numbers above and they will show up here."
            />
          ) : null}
          {history.data && history.data.length > 0 ? (
            <>
              {/* Phones: one tappable row per day instead of a seven-column table. */}
              <ul className="-mx-2 divide-y md:hidden">
                {history.data.map((log) => (
                  <li key={log.id}>
                    <button
                      type="button"
                      onClick={() => setPicked(log.log_date)}
                      aria-label={`Edit log for ${formatDate(log.log_date)}`}
                      aria-current={log.log_date === date ? "date" : undefined}
                      className="flex min-h-12 w-full flex-col items-start gap-0.5 rounded-md px-2 py-2.5 text-left hover:bg-muted/50 focus-visible:outline-2 focus-visible:outline-ring aria-[current=date]:bg-muted"
                    >
                      <span className="font-mono text-sm font-medium text-primary">
                        {formatDate(log.log_date)}
                      </span>
                      <span className="font-mono text-xs text-muted-foreground">
                        {log.applications_sent} apps · {log.messages_sent} msgs ·{" "}
                        {log.referrals_requested} refs · {log.problems_solved} problems ·{" "}
                        {log.mocks_done} mocks · {log.hours_prep}h
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
              <div className="hidden md:block">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Date</TableHead>
                      <TableHead className="text-right">Apps</TableHead>
                      <TableHead className="text-right">Msgs</TableHead>
                      <TableHead className="text-right">Refs</TableHead>
                      <TableHead className="text-right">Problems</TableHead>
                      <TableHead className="text-right">Mocks</TableHead>
                      <TableHead className="text-right">Hours</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {history.data.map((log) => (
                      <TableRow
                        key={log.id}
                        data-state={log.log_date === date ? "selected" : undefined}
                      >
                        <TableCell>
                          <Button
                            variant="link"
                            className="h-auto min-h-8 p-0 font-mono"
                            onClick={() => setPicked(log.log_date)}
                            aria-label={`Edit log for ${formatDate(log.log_date)}`}
                          >
                            {formatDate(log.log_date)}
                          </Button>
                        </TableCell>
                        {[
                          log.applications_sent,
                          log.messages_sent,
                          log.referrals_requested,
                          log.problems_solved,
                          log.mocks_done,
                          log.hours_prep,
                        ].map((value, index) => (
                          <TableCell key={index} className="text-right font-mono">
                            {value}
                          </TableCell>
                        ))}
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </>
          ) : null}
        </CardContent>
      </Card>
    </div>
  )
}
