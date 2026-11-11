import { Pressable } from "react-native"

import { haptics } from "@/lib/haptics"
import { MIN_TOUCH, radius } from "@/theme/tokens"
import { useTheme } from "@/theme/theme"
import { Icon, type IconName } from "./icon"

interface Props {
  icon: IconName
  label: string
  onPress: () => void
  filled?: boolean
  tone?: "default" | "primary" | "danger"
}

export function IconButton({ icon, label, onPress, filled = false, tone = "default" }: Props) {
  const { colors } = useTheme()
  const fg = tone === "primary" ? "primary" : tone === "danger" ? "danger" : "text"
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      onPress={() => {
        haptics.tap()
        onPress()
      }}
      hitSlop={6}
      style={({ pressed }) => ({
        width: MIN_TOUCH,
        height: MIN_TOUCH,
        borderRadius: radius.pill,
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: filled ? colors.primary : pressed ? colors.surfaceRaised : "transparent",
      })}
    >
      <Icon name={icon} size={22} color={filled ? "onPrimary" : fg} />
    </Pressable>
  )
}
