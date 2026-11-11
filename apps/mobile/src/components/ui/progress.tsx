import { View } from "react-native"
import Svg, { Circle } from "react-native-svg"

import { radius } from "@/theme/tokens"
import { useTheme } from "@/theme/theme"
import { Text } from "./text"

export function ProgressBar({ value, tone = "primary" }: { value: number; tone?: "primary" | "success" }) {
  const { colors } = useTheme()
  const pct = Math.max(0, Math.min(100, value))
  return (
    <View
      accessibilityRole="progressbar"
      accessibilityValue={{ min: 0, max: 100, now: Math.round(pct) }}
      style={{
        height: 8,
        borderRadius: radius.pill,
        backgroundColor: colors.surfaceRaised,
        overflow: "hidden",
      }}
    >
      <View
        style={{
          width: `${pct}%`,
          height: "100%",
          borderRadius: radius.pill,
          backgroundColor: tone === "success" ? colors.success : colors.primary,
        }}
      />
    </View>
  )
}

interface RingProps {
  /** 0-100, or null when no target is set. */
  percent: number | null
  size?: number
  label: string
  caption: string
}

export function ProgressRing({ percent, size = 84, label, caption }: RingProps) {
  const { colors } = useTheme()
  const stroke = 8
  const r = (size - stroke) / 2
  const c = 2 * Math.PI * r
  const shown = percent === null ? 0 : Math.max(0, Math.min(100, percent))
  const done = percent !== null && percent >= 100
  return (
    <View
      accessible
      accessibilityLabel={`${label}: ${caption}${percent === null ? ", no target set" : `, ${Math.round(percent)} percent`}`}
      style={{ alignItems: "center", gap: 6 }}
    >
      <View style={{ width: size, height: size }}>
        <Svg width={size} height={size} style={{ transform: [{ rotate: "-90deg" }] }}>
          <Circle cx={size / 2} cy={size / 2} r={r} stroke={colors.surfaceRaised} strokeWidth={stroke} fill="none" />
          <Circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            stroke={done ? colors.success : colors.primary}
            strokeWidth={stroke}
            strokeLinecap="round"
            fill="none"
            strokeDasharray={`${c} ${c}`}
            strokeDashoffset={c * (1 - shown / 100)}
          />
        </Svg>
        <View style={{ position: "absolute", inset: 0, alignItems: "center", justifyContent: "center" }}>
          <Text variant="mono" style={{ fontSize: 16 }}>
            {percent === null ? "—" : `${Math.round(percent)}%`}
          </Text>
        </View>
      </View>
      <Text variant="small" style={{ fontWeight: "600" }}>
        {label}
      </Text>
      <Text variant="caption" tone="muted">
        {caption}
      </Text>
    </View>
  )
}
