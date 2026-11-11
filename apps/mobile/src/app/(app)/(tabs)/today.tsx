import { useRouter } from "expo-router"
import { View } from "react-native"

import { useToday } from "@/api/dashboard"
import { useStreak } from "@/api/daily-logs"
import { PriorityBadge, StageBadge } from "@/components/opportunity/badges"
import { Badge } from "@/components/ui/badge"
import { Card } from "@/components/ui/card"
import { IconButton } from "@/components/ui/icon-button"
import { Icon } from "@/components/ui/icon"
import { Screen, ScreenHeader, SectionHeader } from "@/components/ui/screen"
import { SkeletonList } from "@/components/ui/skeleton"
import { EmptyState, ErrorState } from "@/components/ui/states"
import { Text } from "@/components/ui/text"
import { useUser } from "@/features/auth/auth-context"
import { FollowupCard } from "@/features/today/followup-card"
import { formatDate, formatTime } from "@/lib/format"

function greeting(name: string): string {
  const hour = new Date().getHours()
  const part = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening"
  return `${part}, ${name.split(" ")[0] ?? name}`
}

export default function TodayScreen() {
  const router = useRouter()
  const user = useUser()
  const { data, isPending, isError, error, refetch, isRefetching } = useToday()
  const streak = useStreak()

  const open = (id: number) => router.push({ pathname: "/opportunity/[id]", params: { id } })
  const empty =
    data && !data.followups.length && !data.interviews.length && !data.next_actions.length

  return (
    <Screen refreshing={isRefetching && !isPending} onRefresh={() => void refetch()}>
      <ScreenHeader
        title="Today"
        subtitle={data ? formatDate(data.today) : greeting(user.full_name)}
        right={
          <IconButton
            icon="add"
            label="Add opportunity"
            filled
            onPress={() => router.push("/opportunity/form")}
          />
        }
      />

      {streak.data && streak.data.current > 0 ? (
        <Card style={{ flexDirection: "row", alignItems: "center", gap: 12 }}>
          <Icon name="flame" size={26} color="warning" />
          <View style={{ flex: 1 }}>
            <Text style={{ fontWeight: "600" }}>{streak.data.current}-day streak</Text>
            <Text variant="small" tone="muted">
              {streak.data.logged_today ? "Today's log is in. Nice." : "Log today to keep it going."}
            </Text>
          </View>
          {!streak.data.logged_today ? (
            <Badge label="Log now" tone="warning" />
          ) : null}
        </Card>
      ) : null}

      {isPending ? <SkeletonList count={3} /> : null}
      {isError ? <ErrorState error={error} onRetry={() => void refetch()} /> : null}

      {empty ? (
        <EmptyState
          icon="checkmark-done-circle"
          title="All clear for today"
          description="No follow-ups due and no interviews. Add an opportunity to keep momentum going."
          actionLabel="Add opportunity"
          onAction={() => router.push("/opportunity/form")}
        />
      ) : null}

      {data && data.followups.length ? (
        <View style={{ gap: 10 }}>
          <SectionHeader title="Follow-ups" count={data.followups.length} />
          {data.followups.map((f) => (
            <FollowupCard
              key={f.id}
              followup={f}
              today={data.today}
              onOpen={() => open(f.opportunity_id)}
            />
          ))}
        </View>
      ) : null}

      {data && data.interviews.length ? (
        <View style={{ gap: 10 }}>
          <SectionHeader title="Interviews today" count={data.interviews.length} />
          {data.interviews.map((i) => (
            <Card key={i.interaction_id} onPress={() => open(i.opportunity_id)}>
              <View style={{ flexDirection: "row", gap: 12, alignItems: "center" }}>
                <Text variant="mono" tone="primary" style={{ width: 70 }}>
                  {formatTime(i.occurred_at)}
                </Text>
                <View style={{ flex: 1 }}>
                  <Text style={{ fontWeight: "600" }}>{i.company}</Text>
                  <Text variant="small" tone="muted">
                    {i.role}
                  </Text>
                  {i.summary ? <Text variant="small">{i.summary}</Text> : null}
                </View>
              </View>
            </Card>
          ))}
        </View>
      ) : null}

      {data && data.next_actions.length ? (
        <View style={{ gap: 10 }}>
          <SectionHeader title="Next actions" />
          {data.next_actions.map((a, index) => (
            <Card key={a.opportunity_id} onPress={() => open(a.opportunity_id)}>
              <View style={{ flexDirection: "row", gap: 12 }}>
                <View
                  style={{
                    width: 26,
                    height: 26,
                    borderRadius: 13,
                    alignItems: "center",
                    justifyContent: "center",
                    backgroundColor: "rgba(109,112,245,0.16)",
                  }}
                >
                  <Text variant="mono" tone="primary" style={{ fontSize: 12 }}>
                    {index + 1}
                  </Text>
                </View>
                <View style={{ flex: 1, gap: 6 }}>
                  <Text style={{ fontWeight: "600" }}>{a.next_action}</Text>
                  <Text variant="small" tone="muted" numberOfLines={1}>
                    {a.company} · {a.role}
                  </Text>
                  <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 6, alignItems: "center" }}>
                    <StageBadge stage={a.stage} />
                    <PriorityBadge priority={a.priority} />
                    {a.next_action_due ? (
                      <Text variant="caption" tone={a.overdue ? "danger" : "muted"}>
                        {a.overdue ? "Overdue · " : ""}
                        {formatDate(a.next_action_due)}
                      </Text>
                    ) : null}
                  </View>
                </View>
              </View>
            </Card>
          ))}
        </View>
      ) : null}
    </Screen>
  )
}
