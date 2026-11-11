import { ActivityIndicator, Pressable, StyleSheet, View, type StyleProp, type ViewStyle } from "react-native"

import { haptics } from "@/lib/haptics"
import { MIN_TOUCH, radius } from "@/theme/tokens"
import { useTheme } from "@/theme/theme"
import { Icon, type IconName } from "./icon"
import { Text } from "./text"

type Variant = "primary" | "secondary" | "ghost" | "danger"

interface ButtonProps {
  label: string
  onPress: () => void
  variant?: Variant
  icon?: IconName
  loading?: boolean
  disabled?: boolean
  size?: "md" | "sm"
  fullWidth?: boolean
  style?: StyleProp<ViewStyle>
  testID?: string
}

export function Button({
  label,
  onPress,
  variant = "primary",
  icon,
  loading = false,
  disabled = false,
  size = "md",
  fullWidth = true,
  style,
  testID,
}: ButtonProps) {
  const { colors } = useTheme()
  const inactive = disabled || loading

  const palette = {
    primary: { bg: colors.primary, fg: colors.onPrimary, border: colors.primary },
    secondary: { bg: colors.surfaceRaised, fg: colors.text, border: colors.border },
    ghost: { bg: "transparent", fg: colors.primary, border: "transparent" },
    danger: { bg: colors.dangerSoft, fg: colors.danger, border: "transparent" },
  }[variant]

  return (
    <Pressable
      testID={testID}
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ disabled: inactive, busy: loading }}
      disabled={inactive}
      onPress={() => {
        haptics.light()
        onPress()
      }}
      style={({ pressed }) => [
        styles.base,
        {
          minHeight: size === "sm" ? 36 : MIN_TOUCH + 4,
          backgroundColor: palette.bg,
          borderColor: palette.border,
          opacity: inactive ? 0.55 : pressed ? 0.82 : 1,
          alignSelf: fullWidth ? "stretch" : "flex-start",
          transform: [{ scale: pressed ? 0.985 : 1 }],
        },
        style,
      ]}
    >
      <View style={styles.row}>
        {loading ? (
          <ActivityIndicator color={palette.fg} />
        ) : icon ? (
          <Icon name={icon} size={size === "sm" ? 16 : 18} color={palette.fg} />
        ) : null}
        <Text
          variant={size === "sm" ? "small" : "body"}
          style={{ color: palette.fg, fontWeight: "600" }}
        >
          {label}
        </Text>
      </View>
    </Pressable>
  )
}

const styles = StyleSheet.create({
  base: {
    borderRadius: radius.md,
    borderWidth: StyleSheet.hairlineWidth,
    paddingHorizontal: 16,
    justifyContent: "center",
    alignItems: "center",
  },
  row: { flexDirection: "row", alignItems: "center", gap: 8 },
})
