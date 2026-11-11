import { Pressable, View } from "react-native"

import { haptics } from "@/lib/haptics"
import { MIN_TOUCH, radius } from "@/theme/tokens"
import { useTheme } from "@/theme/theme"
import { Text } from "./text"

interface Option<T extends string> {
  value: T
  label: string
}

interface Props<T extends string> {
  options: readonly Option<T>[]
  value: T
  onChange: (value: T) => void
}

export function SegmentedControl<T extends string>({ options, value, onChange }: Props<T>) {
  const { colors } = useTheme()
  return (
    <View
      accessibilityRole="tablist"
      style={{
        flexDirection: "row",
        backgroundColor: colors.surfaceRaised,
        borderRadius: radius.md,
        padding: 3,
      }}
    >
      {options.map((option) => {
        const selected = option.value === value
        return (
          <Pressable
            key={option.value}
            accessibilityRole="tab"
            accessibilityState={{ selected }}
            onPress={() => {
              if (!selected) {
                haptics.tap()
                onChange(option.value)
              }
            }}
            style={{
              flex: 1,
              minHeight: MIN_TOUCH - 8,
              alignItems: "center",
              justifyContent: "center",
              borderRadius: radius.md - 3,
              backgroundColor: selected ? colors.surface : "transparent",
              borderWidth: selected ? 1 : 0,
              borderColor: colors.border,
            }}
          >
            <Text
              variant="small"
              tone={selected ? "default" : "muted"}
              style={{ fontWeight: selected ? "700" : "500" }}
              numberOfLines={1}
            >
              {option.label}
            </Text>
          </Pressable>
        )
      })}
    </View>
  )
}
