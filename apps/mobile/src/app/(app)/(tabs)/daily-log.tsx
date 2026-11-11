import { useMemo, useState } from "react"
import { Pressable, View } from "react-native"

import { useDailyLogs, useStreak } from "@/api/daily-logs"
import { Card } from "@/components/ui/card"
import { Icon } from "@/components/ui/icon"
import { Screen, ScreenHeader, SectionHeader } from "@/components/ui/screen"
import { ErrorState } from "@/components/ui/states"
import { Text } from "@/components/ui/text"
import { LogEditor } from "@/features/daily-log/log-editor"
import { todayIso } from "@/lib/dates"
import { addDays, formatDate, formatShortDate } from "@/lib/format"
import { haptics } from "@/lib/haptics"

export default function DailyLogScreen() {
  const today = todayIso()
  const [date, setDate] = useState(today)
  const from = addDays(today, -13)
  const logs = useDailyLogs(from, today)
  const streak = useStreak()

  const existing = useMemo(() => logs.data?.find((l) => l.log_date === date), [logs.data, date])
  const isToday = date === today

  const step = (days: number) => {
    const next = addDays(date, days)
    if (next > today || next < from) return
    haptics.tap()
    setDate(next)
  }

  return (
    <Screen
      refreshing={logs.isRefetching}
      onRefresh={() => {
        void logs.refetch()
        void streak.refetch()
      }}
    >
      <ScreenHeader title="Daily log" subtitle="Numbers only. Takes ten seconds." />

      <Card style={{ flexDirection: "row", alignItems: "center", gap: 14 }}>
        <Icon name="flame" size={30} color={streak.data && streak.data.current > 0 ? "warning" : "muted"} />
        <View style={{ flex: 1 }}>
          <Text variant="heading">{streak.data?.current ?? 0}-day streak</Text>
          <Text variant="small" tone="muted">
            Longest: {streak.data?.longest ?? 0} days
            {streak.data && !streak.data.logged_today ? " · log today to keep it" : ""}
          </Text>
        </View>
      </Card>

      <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between" }}>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Previous day"
          disabled={date <= from}
          onPress={() => step(-1)}
          hitSlop={12}
          style={{ padding: 8, opacity: date <= from ? 0.3 : 1 }}
        >
          <Icon name="chevron-back" size={24} color="primary" />
        </Pressable>
        <View style={{ alignItems: "center" }}>
          <Text variant="heading">{isToday ? "Today" : formatDate(date)}</Text>
          {isToday ? (
            <Text variant="caption" tone="muted">
              {formatDate(date)}
            </Text>
          ) : null}
        </View>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Next day"
          disabled={isToday}
          onPress={() => step(1)}
          hitSlop={12}
          style={{ padding: 8, opacity: isToday ? 0.3 : 1 }}
        >
          <Icon name="chevron-forward" size={24} color="primary" />
        </Pressable>
      </View>

      {logs.isError ? (
        <ErrorState error={logs.error} onRetry={() => void logs.refetch()} />
      ) : logs.isPending ? null : (
        <LogEditor key={`${date}-${existing?.id ?? "new"}`} date={date} existing={existing} />
      )}

      {logs.data && logs.data.length ? (
        <View style={{ gap: 8 }}>
          <SectionHeader title="Recent days" />
          {[...logs.data]
            .sort((a, b) => b.log_date.localeCompare(a.log_date))
            .slice(0, 10)
            .map((l) => (
              <Card key={l.id} onPress={() => setDate(l.log_date)}>
                <View style={{ flexDirection: "row", alignItems: "center", gap: 10 }}>
                  <Text style={{ fontWeight: "600", width: 64 }}>{formatShortDate(l.log_date)}</Text>
                  <Text variant="small" tone="muted" style={{ flex: 1 }}>
                    {l.applications_sent} apps · {l.messages_sent} msgs · {l.problems_solved} problems ·{" "}
                    {l.hours_prep}h
                  </Text>
                  <Icon name="chevron-forward" size={16} color="muted" />
                </View>
              </Card>
            ))}
        </View>
      ) : null}
    </Screen>
  )
}
