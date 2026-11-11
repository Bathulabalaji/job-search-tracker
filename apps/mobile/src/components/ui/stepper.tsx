import { Pressable, TextInput, View } from "react-native"

import { haptics } from "@/lib/haptics"
import { MIN_TOUCH, radius } from "@/theme/tokens"
import { useTheme } from "@/theme/theme"
import { Icon } from "./icon"
import { Text } from "./text"

interface Props {
  label: string
  value: number
  onChange: (value: number) => void
  min?: number
  max?: number
  step?: number
  /** Allow decimals (hours). */
  decimal?: boolean
}

/** Big +/- buttons around a number you can also type: fast on a phone. */
export function Stepper({ label, value, onChange, min = 0, max = 999, step = 1, decimal }: Props) {
  const { colors } = useTheme()
  const clamp = (n: number) => Math.min(max, Math.max(min, Math.round(n * 100) / 100))
  const button = (icon: "add" | "remove", delta: number, name: string) => (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`${name} ${label}`}
      onPress={() => {
        haptics.tap()
        onChange(clamp(value + delta))
      }}
      style={({ pressed }) => ({
        width: MIN_TOUCH,
        height: MIN_TOUCH,
        borderRadius: radius.md,
        backgroundColor: pressed ? colors.primarySoft : colors.surfaceRaised,
        alignItems: "center",
        justifyContent: "center",
      })}
    >
      <Icon name={icon} color="primary" />
    </Pressable>
  )
  return (
    <View style={{ flexDirection: "row", alignItems: "center", gap: 12 }}>
      <Text style={{ flex: 1, fontWeight: "500" }}>{label}</Text>
      {button("remove", -step, "Decrease")}
      <TextInput
        accessibilityLabel={label}
        keyboardType={decimal ? "decimal-pad" : "number-pad"}
        selectTextOnFocus
        value={String(value)}
        onChangeText={(text) => {
          const parsed = Number(text.replace(",", "."))
          if (text === "") onChange(min)
          else if (Number.isFinite(parsed)) onChange(clamp(parsed))
        }}
        style={{
          width: 64,
          textAlign: "center",
          fontSize: 20,
          fontWeight: "700",
          color: colors.text,
          fontVariant: ["tabular-nums"],
          paddingVertical: 6,
        }}
      />
      {button("add", step, "Increase")}
    </View>
  )
}
