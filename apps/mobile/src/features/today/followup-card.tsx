import { useState } from "react"
import { View } from "react-native"

import { useUpdateFollowup } from "@/api/followups"
import type { FollowupChannel, TodayFollowup } from "@/api/types"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Icon, type IconName } from "@/components/ui/icon"
import { OptionSheet } from "@/components/ui/option-sheet"
import { Text } from "@/components/ui/text"
import { addDays, daysUntilNextMonday, formatDate, titleCase } from "@/lib/format"

const CHANNEL_ICONS: Record<FollowupChannel, IconName> = {
  email: "mail-outline",
  call: "call-outline",
  linkedin: "logo-linkedin",
  whatsapp: "logo-whatsapp",
}

export function FollowupCard({
  followup,
  today,
  onOpen,
}: {
  followup: TodayFollowup
  today: string
  onOpen: () => void
}) {
  const update = useUpdateFollowup()
  const [snoozing, setSnoozing] = useState(false)
  const overdue = followup.days_overdue > 0

  const snoozeOptions = [
    { value: 1, label: "Tomorrow" },
    { value: 3, label: "In 3 days" },
    { value: daysUntilNextMonday(today), label: "Next Monday" },
  ]

  return (
    <Card onPress={onOpen} accessibilityLabel={`Follow up with ${followup.company}`}>
      <View style={{ flexDirection: "row", gap: 10, alignItems: "center" }}>
        <Icon name={CHANNEL_ICONS[followup.channel]} color="primary" />
        <View style={{ flex: 1 }}>
          <Text style={{ fontWeight: "600" }} numberOfLines={1}>
            {followup.company}
          </Text>
          <Text variant="small" tone="muted" numberOfLines={1}>
            {followup.role} · {titleCase(followup.channel)}
          </Text>
        </View>
        <Badge
          label={overdue ? `${followup.days_overdue}d overdue` : "Due today"}
          tone={overdue ? "danger" : "warning"}
        />
      </View>
      {followup.message_draft ? (
        <Text variant="small" tone="muted" numberOfLines={2}>
          “{followup.message_draft}”
        </Text>
      ) : null}
      <View style={{ flexDirection: "row", gap: 8, marginTop: 4 }}>
        <Button
          label="Done"
          icon="checkmark"
          size="sm"
          style={{ flex: 1 }}
          loading={update.isPending && update.variables?.patch.status === "done"}
          onPress={() =>
            update.mutate({
              id: followup.id,
              opportunityId: followup.opportunity_id,
              patch: { status: "done" },
              message: `Follow-up with ${followup.company} marked done`,
            })
          }
        />
        <Button
          label="Snooze"
          icon="time-outline"
          size="sm"
          variant="secondary"
          style={{ flex: 1 }}
          onPress={() => setSnoozing(true)}
        />
      </View>
      <OptionSheet
        visible={snoozing}
        title="Snooze until…"
        options={snoozeOptions.map((o) => ({
          ...o,
          description: formatDate(addDays(today, o.value)),
        }))}
        onSelect={(days) =>
          update.mutate({
            id: followup.id,
            opportunityId: followup.opportunity_id,
            patch: { due_date: addDays(today, days) },
            message: `Snoozed until ${formatDate(addDays(today, days))}`,
          })
        }
        onClose={() => setSnoozing(false)}
      />
    </Card>
  )
}
