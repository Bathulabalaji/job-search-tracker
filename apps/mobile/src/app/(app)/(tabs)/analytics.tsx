import { useState } from "react"
import { Pressable, View } from "react-native"

import { useWeeklyAnalytics } from "@/api/analytics"
import type { Metric } from "@/api/types"
import { BarChart, HorizontalBars, LineChart } from "@/components/charts/charts"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Icon } from "@/components/ui/icon"
import { ProgressRing } from "@/components/ui/progress"
import { Screen, ScreenHeader, SectionHeader } from "@/components/ui/screen"
import { Skeleton } from "@/components/ui/skeleton"
import { ErrorState } from "@/components/ui/states"
import { Text } from "@/components/ui/text"
import { TargetsSheet } from "@/features/analytics/targets-sheet"
import { addDays, formatPercent, formatShortDate, formatWeekday, titleCase } from "@/lib/format"
import { haptics } from "@/lib/haptics"
import { useTheme } from "@/theme/theme"

export default function AnalyticsScreen() {
  const { colors } = useTheme()
  const [weekOf, setWeekOf] = useState<string | undefined>()
  const [editingTargets, setEditingTargets] = useState(false)
  const { data, isPending, isError, error, refetch, isRefetching, isPlaceholderData } =
    useWeeklyAnalytics(weekOf)

  const shift = (days: number) => {
    if (!data) return
    haptics.tap()
    setWeekOf(addDays(data.week_start, days))
  }

  return (
    <Screen refreshing={isRefetching && !isPlaceholderData} onRefresh={() => void refetch()}>
      <ScreenHeader title="Analytics" subtitle="How your search is going" />

      {isError ? <ErrorState error={error} onRetry={() => void refetch()} /> : null}
      {isPending ? (
        <View style={{ gap: 12 }}>
          <Skeleton height={44} />
          <Skeleton height={190} />
          <Skeleton height={150} />
        </View>
      ) : null}

      {data ? (
        <View style={{ gap: 18, opacity: isPlaceholderData ? 0.6 : 1 }}>
          <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between" }}>
            <Pressable accessibilityRole="button" accessibilityLabel="Previous week" onPress={() => shift(-7)} hitSlop={12} style={{ padding: 8 }}>
              <Icon name="chevron-back" size={24} color="primary" />
            </Pressable>
            <View style={{ alignItems: "center" }}>
              <Text variant="heading">
                {data.is_current_week ? "This week" : `${formatShortDate(data.week_start)} – ${formatShortDate(data.week_end)}`}
              </Text>
              {data.is_current_week ? (
                <Text variant="caption" tone="muted">
                  {formatShortDate(data.week_start)} – {formatShortDate(data.week_end)}
                </Text>
              ) : null}
            </View>
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="Next week"
              disabled={data.is_current_week}
              onPress={() => shift(7)}
              hitSlop={12}
              style={{ padding: 8, opacity: data.is_current_week ? 0.3 : 1 }}
            >
              <Icon name="chevron-forward" size={24} color="primary" />
            </Pressable>
          </View>

          <View style={{ gap: 12 }}>
            <SectionHeader
              title="Targets vs actual"
              right={<Button label={data.target ? "Edit" : "Set targets"} size="sm" variant="secondary" fullWidth={false} onPress={() => setEditingTargets(true)} />}
            />
            <Card style={{ flexDirection: "row", flexWrap: "wrap", gap: 0, rowGap: 18, paddingVertical: 18 }}>
              {data.progress.map((p) => (
                <View key={p.metric} style={{ width: "33.33%", alignItems: "center" }}>
                  <ProgressRing
                    percent={p.percent}
                    label={p.label}
                    caption={p.target === null ? `${p.actual}` : `${p.actual} / ${p.target}`}
                  />
                </View>
              ))}
            </Card>
            {!data.target ? (
              <Text variant="small" tone="muted">
                Set weekly targets to see progress rings fill up.
              </Text>
            ) : null}
          </View>

          <View style={{ gap: 12 }}>
            <SectionHeader title="Scorecard" />
            <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 10 }}>
              {[
                { label: "Applications", value: String(data.scorecard.applications_total) },
                { label: "Response rate", value: formatPercent(data.scorecard.response_rate) },
                { label: "Interview rate", value: formatPercent(data.scorecard.interview_rate) },
                { label: "Offers", value: String(data.scorecard.offers) },
                { label: "Active", value: String(data.scorecard.active_opportunities) },
                { label: "Streak", value: `${data.scorecard.current_streak}d` },
              ].map((tile) => (
                <Card key={tile.label} style={{ width: "48%", flexGrow: 1 }}>
                  <Text variant="caption" tone="muted">
                    {tile.label}
                  </Text>
                  <Text variant="title" style={{ color: colors.primary }}>
                    {tile.value}
                  </Text>
                </Card>
              ))}
            </View>
          </View>

          <View style={{ gap: 12 }}>
            <SectionHeader title="Applications per day" />
            <Card>
              <BarChart
                data={data.daily.map((d) => ({ label: formatWeekday(d.date), value: d.applications }))}
                summary={`Applications per day: ${data.daily.map((d) => `${formatWeekday(d.date)} ${d.applications}`).join(", ")}`}
              />
            </Card>
          </View>

          <View style={{ gap: 12 }}>
            <SectionHeader title="Weekly trend" />
            <Card>
              <LineChart
                labels={data.trend.map((t) => formatShortDate(t.week_start))}
                series={(["applications", "messages"] as Metric[]).map((metric, i) => ({
                  name: titleCase(metric),
                  color: i === 0 ? colors.primary : colors.info,
                  values: data.trend.map((t) => t[metric as "applications" | "messages"]),
                }))}
                summary="Applications and messages over recent weeks"
              />
            </Card>
          </View>

          <View style={{ gap: 12 }}>
            <SectionHeader title="Funnel" />
            <Card>
              <HorizontalBars
                data={data.funnel.map((f) => ({
                  label: f.label,
                  value: f.count,
                  display: String(f.count),
                  detail:
                    f.conversion_from_previous === null ? undefined : `${formatPercent(f.conversion_from_previous)} from previous`,
                }))}
              />
            </Card>
          </View>

          <View style={{ gap: 12 }}>
            <SectionHeader title="Response rate by source" />
            <Card>
              {data.response_by_source.some((s) => s.applied > 0) ? (
                <HorizontalBars
                  max={1}
                  data={data.response_by_source
                    .filter((s) => s.applied > 0)
                    .map((s) => ({
                      label: titleCase(s.source),
                      value: s.response_rate ?? 0,
                      display: formatPercent(s.response_rate),
                      detail: `${s.responded}/${s.applied}`,
                    }))}
                />
              ) : (
                <Text tone="muted" variant="small">
                  Apply to a few roles and responses will show up here.
                </Text>
              )}
            </Card>
          </View>

          <TargetsSheet
            visible={editingTargets}
            onClose={() => setEditingTargets(false)}
            weekStart={data.week_start}
            target={data.target}
            carriedOver={data.target_carried_over}
          />
        </View>
      ) : null}
    </Screen>
  )
}
