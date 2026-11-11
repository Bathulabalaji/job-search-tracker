import {
  KeyboardAvoidingView,
  Platform,
  RefreshControl,
  ScrollView,
  View,
  type StyleProp,
  type ViewStyle,
} from "react-native"
import { SafeAreaView, type Edge } from "react-native-safe-area-context"

import { space } from "@/theme/tokens"
import { useTheme } from "@/theme/theme"
import { Text } from "./text"

interface ScreenProps {
  children: React.ReactNode
  /** Wrap in a ScrollView (default). Turn off when the screen owns a FlatList. */
  scroll?: boolean
  /** Safe-area edges to pad. Screens under a native header pass []. */
  edges?: readonly Edge[]
  refreshing?: boolean
  onRefresh?: () => void
  contentStyle?: StyleProp<ViewStyle>
  /** Lift content above the keyboard (forms). */
  keyboard?: boolean
}

export function Screen({
  children,
  scroll = true,
  edges = ["top"],
  refreshing,
  onRefresh,
  contentStyle,
  keyboard = false,
}: ScreenProps) {
  const { colors } = useTheme()
  const body = scroll ? (
    <ScrollView
      contentInsetAdjustmentBehavior="automatic"
      keyboardShouldPersistTaps="handled"
      keyboardDismissMode="on-drag"
      showsVerticalScrollIndicator={false}
      refreshControl={
        onRefresh ? (
          <RefreshControl
            refreshing={refreshing ?? false}
            onRefresh={onRefresh}
            tintColor={colors.primary}
            colors={[colors.primary]}
            progressBackgroundColor={colors.surface}
          />
        ) : undefined
      }
      contentContainerStyle={[
        { padding: space.lg, gap: space.lg, paddingBottom: space.xxl * 2 },
        contentStyle,
      ]}
    >
      {children}
    </ScrollView>
  ) : (
    <View style={[{ flex: 1 }, contentStyle]}>{children}</View>
  )

  return (
    <SafeAreaView edges={edges} style={{ flex: 1, backgroundColor: colors.bg }}>
      {keyboard ? (
        <KeyboardAvoidingView
          style={{ flex: 1 }}
          behavior={Platform.OS === "ios" ? "padding" : undefined}
        >
          {body}
        </KeyboardAvoidingView>
      ) : (
        body
      )}
    </SafeAreaView>
  )
}

interface HeaderProps {
  title: string
  subtitle?: string
  right?: React.ReactNode
}

/** The large title shown at the top of each tab screen. */
export function ScreenHeader({ title, subtitle, right }: HeaderProps) {
  return (
    <View style={{ flexDirection: "row", alignItems: "flex-end", gap: 12 }}>
      <View style={{ flex: 1, gap: 2 }}>
        <Text variant="title" accessibilityRole="header">
          {title}
        </Text>
        {subtitle ? (
          <Text tone="muted" variant="small">
            {subtitle}
          </Text>
        ) : null}
      </View>
      {right}
    </View>
  )
}

export function SectionHeader({
  title,
  count,
  right,
}: {
  title: string
  count?: number
  right?: React.ReactNode
}) {
  return (
    <View style={{ flexDirection: "row", alignItems: "center", gap: 8, marginTop: 4 }}>
      <Text variant="heading" accessibilityRole="header">
        {title}
      </Text>
      {count !== undefined ? (
        <Text variant="small" tone="muted">
          {count}
        </Text>
      ) : null}
      <View style={{ flex: 1 }} />
      {right}
    </View>
  )
}
