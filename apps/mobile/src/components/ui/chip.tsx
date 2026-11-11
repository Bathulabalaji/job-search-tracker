import { Pressable, ScrollView, StyleSheet, View } from "react-native"

import { haptics } from "@/lib/haptics"
import { MIN_TOUCH, radius, space } from "@/theme/tokens"
import { useTheme } from "@/theme/theme"
import { Text } from "./text"

interface ChipProps {
  label: string
  selected?: boolean
  onPress: () => void
  count?: number
}

export function Chip({ label, selected = false, onPress, count }: ChipProps) {
  const { colors } = useTheme()
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ selected }}
      accessibilityLabel={count === undefined ? label : `${label}, ${count}`}
      onPress={() => {
        haptics.tap()
        onPress()
      }}
      hitSlop={{ top: 4, bottom: 4 }}
      style={[
        styles.chip,
        {
          backgroundColor: selected ? colors.primary : colors.surface,
          borderColor: selected ? colors.primary : colors.border,
        },
      ]}
    >
      <Text
        variant="small"
        style={{ color: selected ? colors.onPrimary : colors.text, fontWeight: "600" }}
      >
        {label}
      </Text>
      {count !== undefined ? (
        <View
          style={[
            styles.count,
            { backgroundColor: selected ? "rgba(255,255,255,0.22)" : colors.surfaceRaised },
          ]}
        >
          <Text
            variant="caption"
            style={{ color: selected ? colors.onPrimary : colors.muted, fontWeight: "700" }}
          >
            {count}
          </Text>
        </View>
      ) : null}
    </Pressable>
  )
}

/** A horizontally scrolling row of chips that bleeds to the screen edges. */
export function ChipRow({ children }: { children: React.ReactNode }) {
  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      keyboardShouldPersistTaps="handled"
      contentContainerStyle={{ paddingHorizontal: space.lg, gap: space.sm }}
      style={{ flexGrow: 0 }}
    >
      {children}
    </ScrollView>
  )
}

const styles = StyleSheet.create({
  chip: {
    minHeight: MIN_TOUCH - 6,
    borderRadius: radius.pill,
    borderWidth: StyleSheet.hairlineWidth,
    paddingHorizontal: 14,
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  count: { borderRadius: radius.pill, paddingHorizontal: 6, minWidth: 20, alignItems: "center" },
})
