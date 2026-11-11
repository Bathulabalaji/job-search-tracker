import { View } from "react-native"

import type { Opportunity } from "@/api/types"
import { PriorityBadge } from "@/components/opportunity/badges"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Icon } from "@/components/ui/icon"
import { Text } from "@/components/ui/text"
import { formatShortDate, titleCase } from "@/lib/format"

interface Props {
  opportunity: Opportunity
  onOpen: () => void
  onMove: () => void
}

export function OpportunityCard({ opportunity: o, onOpen, onMove }: Props) {
  const stale = o.days_since_contact >= 14
  return (
    <Card
      onPress={onOpen}
      onLongPress={onMove}
      accessibilityLabel={`${o.company}, ${o.role}. Double tap to open, hold to move stage.`}
      testID={`opportunity-${o.id}`}
    >
      <View style={{ flexDirection: "row", alignItems: "flex-start", gap: 8 }}>
        <View style={{ flex: 1 }}>
          <Text style={{ fontWeight: "700" }} variant="heading" numberOfLines={1}>
            {o.company}
          </Text>
          <Text tone="muted" numberOfLines={1}>
            {o.role}
          </Text>
        </View>
        {o.fit_score !== null ? (
          <Badge label={`${o.fit_score}% fit`} tone={o.fit_score >= 70 ? "success" : "neutral"} />
        ) : null}
      </View>

      <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 6, alignItems: "center" }}>
        <PriorityBadge priority={o.priority} />
        <Badge label={titleCase(o.source)} />
        {o.location ? <Badge label={o.location} /> : null}
        {o.ghosted_suggestion ? <Badge label="Maybe ghosted" tone="warning" /> : null}
      </View>

      {o.next_action ? (
        <View style={{ flexDirection: "row", gap: 6, alignItems: "center" }}>
          <Icon name="arrow-forward-circle-outline" size={16} color="primary" />
          <Text variant="small" style={{ flex: 1 }} numberOfLines={1}>
            {o.next_action}
            {o.next_action_due ? ` · ${formatShortDate(o.next_action_due)}` : ""}
          </Text>
        </View>
      ) : null}

      <View style={{ flexDirection: "row", alignItems: "center", gap: 8, marginTop: 2 }}>
        <Icon name="chatbubble-ellipses-outline" size={14} color={stale ? "warning" : "muted"} />
        <Text variant="caption" tone={stale ? "warning" : "muted"} style={{ flex: 1 }}>
          {o.days_since_contact === 0 ? "Contacted today" : `${o.days_since_contact}d since contact`}
        </Text>
        <Button
          label="Move"
          icon="swap-horizontal"
          variant="secondary"
          size="sm"
          fullWidth={false}
          onPress={onMove}
        />
      </View>
    </Card>
  )
}
