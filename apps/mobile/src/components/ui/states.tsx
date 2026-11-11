import { View } from "react-native"

import { ApiError } from "@/api/client"
import { Button } from "./button"
import { Icon, type IconName } from "./icon"
import { Text } from "./text"
import { useTheme } from "@/theme/theme"

interface EmptyProps {
  icon: IconName
  title: string
  description?: string
  actionLabel?: string
  onAction?: () => void
}

export function EmptyState({ icon, title, description, actionLabel, onAction }: EmptyProps) {
  const { colors } = useTheme()
  return (
    <View style={{ alignItems: "center", gap: 10, paddingVertical: 40, paddingHorizontal: 24 }}>
      <View
        style={{
          width: 64,
          height: 64,
          borderRadius: 32,
          backgroundColor: colors.primarySoft,
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <Icon name={icon} size={28} color="primary" />
      </View>
      <Text variant="heading" style={{ textAlign: "center" }}>
        {title}
      </Text>
      {description ? (
        <Text tone="muted" style={{ textAlign: "center" }}>
          {description}
        </Text>
      ) : null}
      {actionLabel && onAction ? (
        <View style={{ marginTop: 8, alignSelf: "stretch" }}>
          <Button label={actionLabel} onPress={onAction} fullWidth={false} style={{ alignSelf: "center" }} />
        </View>
      ) : null}
    </View>
  )
}

interface ErrorProps {
  error: unknown
  onRetry: () => void
  title?: string
}

export function ErrorState({ error, onRetry, title = "Something went wrong" }: ErrorProps) {
  const message = error instanceof ApiError || error instanceof Error ? error.message : undefined
  return (
    <View
      accessibilityRole="alert"
      style={{ alignItems: "center", gap: 10, paddingVertical: 40, paddingHorizontal: 24 }}
    >
      <Icon name="cloud-offline-outline" size={36} color="danger" />
      <Text variant="heading" style={{ textAlign: "center" }}>
        {title}
      </Text>
      {message ? (
        <Text tone="muted" style={{ textAlign: "center" }}>
          {message}
        </Text>
      ) : null}
      <Button
        label="Try again"
        icon="refresh"
        variant="secondary"
        onPress={onRetry}
        fullWidth={false}
        style={{ alignSelf: "center", marginTop: 8 }}
      />
    </View>
  )
}
