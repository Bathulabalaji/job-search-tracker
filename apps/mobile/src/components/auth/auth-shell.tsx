import { View } from "react-native"

import { Icon } from "@/components/ui/icon"
import { Screen } from "@/components/ui/screen"
import { Text } from "@/components/ui/text"
import { radius } from "@/theme/tokens"
import { useTheme } from "@/theme/theme"

/** Logo, title and a centred column of fields: shared by every signed-out screen. */
export function AuthShell({
  title,
  subtitle,
  children,
}: {
  title: string
  subtitle?: string
  children: React.ReactNode
}) {
  const { colors } = useTheme()
  return (
    <Screen keyboard edges={["top", "bottom"]} contentStyle={{ gap: 16, paddingTop: 24 }}>
      <View style={{ flexDirection: "row", alignItems: "center", gap: 10, marginBottom: 8 }}>
        <View
          style={{
            width: 38,
            height: 38,
            borderRadius: radius.md,
            backgroundColor: colors.primary,
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <Icon name="rocket" size={20} color="onPrimary" />
        </View>
        <Text variant="heading">Jobs Tracker</Text>
      </View>
      <View style={{ gap: 4, marginBottom: 8 }}>
        <Text variant="hero" accessibilityRole="header">
          {title}
        </Text>
        {subtitle ? <Text tone="muted">{subtitle}</Text> : null}
      </View>
      {children}
    </Screen>
  )
}

export function FormAlert({ message, tone = "danger" }: { message: string; tone?: "danger" | "success" }) {
  const { colors } = useTheme()
  const color = tone === "danger" ? colors.danger : colors.success
  return (
    <View
      accessibilityRole="alert"
      style={{
        flexDirection: "row",
        gap: 10,
        padding: 12,
        borderRadius: radius.md,
        backgroundColor: tone === "danger" ? colors.dangerSoft : colors.successSoft,
        borderWidth: 1,
        borderColor: color,
      }}
    >
      <Icon name={tone === "danger" ? "alert-circle" : "checkmark-circle"} color={color} />
      <Text style={{ flex: 1 }} variant="small">
        {message}
      </Text>
    </View>
  )
}

export function OrDivider() {
  const { colors } = useTheme()
  return (
    <View style={{ flexDirection: "row", alignItems: "center", gap: 12 }}>
      <View style={{ flex: 1, height: 1, backgroundColor: colors.border }} />
      <Text variant="caption" tone="muted">
        OR
      </Text>
      <View style={{ flex: 1, height: 1, backgroundColor: colors.border }} />
    </View>
  )
}
