import { View } from "react-native"

import { radius } from "@/theme/tokens"
import { useTheme } from "@/theme/theme"
import { Text } from "./text"

type Tone = "neutral" | "primary" | "success" | "warning" | "danger" | "info"

export function Badge({ label, tone = "neutral" }: { label: string; tone?: Tone }) {
  const { colors } = useTheme()
  const { bg, fg } = {
    neutral: { bg: colors.surfaceRaised, fg: colors.muted },
    primary: { bg: colors.primarySoft, fg: colors.primary },
    success: { bg: colors.successSoft, fg: colors.success },
    warning: { bg: colors.warningSoft, fg: colors.warning },
    danger: { bg: colors.dangerSoft, fg: colors.danger },
    info: { bg: colors.primarySoft, fg: colors.info },
  }[tone]
  return (
    <View
      style={{
        backgroundColor: bg,
        borderRadius: radius.pill,
        paddingHorizontal: 9,
        paddingVertical: 3,
        alignSelf: "flex-start",
      }}
    >
      <Text variant="caption" style={{ color: fg, fontWeight: "600" }}>
        {label}
      </Text>
    </View>
  )
}
