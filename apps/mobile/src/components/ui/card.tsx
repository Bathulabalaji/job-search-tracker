import { Pressable, StyleSheet, View, type StyleProp, type ViewStyle } from "react-native"

import { haptics } from "@/lib/haptics"
import { radius } from "@/theme/tokens"
import { useTheme } from "@/theme/theme"

interface CardProps {
  children: React.ReactNode
  onPress?: () => void
  onLongPress?: () => void
  style?: StyleProp<ViewStyle>
  accessibilityLabel?: string
  testID?: string
}

export function Card({
  children,
  onPress,
  onLongPress,
  style,
  accessibilityLabel,
  testID,
}: CardProps) {
  const { colors } = useTheme()
  const base = [
    styles.card,
    { backgroundColor: colors.surface, borderColor: colors.border },
    style,
  ]
  if (!onPress && !onLongPress) {
    return (
      <View testID={testID} style={base}>
        {children}
      </View>
    )
  }
  return (
    <Pressable
      testID={testID}
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel}
      onPress={() => {
        haptics.tap()
        onPress?.()
      }}
      onLongPress={() => {
        haptics.light()
        onLongPress?.()
      }}
      style={({ pressed }) => [base, pressed && { opacity: 0.85, transform: [{ scale: 0.99 }] }]}
    >
      {children}
    </Pressable>
  )
}

const styles = StyleSheet.create({
  card: {
    borderRadius: radius.lg,
    borderWidth: StyleSheet.hairlineWidth,
    padding: 16,
    gap: 8,
  },
})
