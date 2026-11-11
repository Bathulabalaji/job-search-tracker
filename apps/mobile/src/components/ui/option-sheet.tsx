import { Pressable, View } from "react-native"

import { haptics } from "@/lib/haptics"
import { MIN_TOUCH } from "@/theme/tokens"
import { useTheme } from "@/theme/theme"
import { Icon, type IconName } from "./icon"
import { Sheet } from "./sheet"
import { Text } from "./text"

export interface Option<T extends string | number> {
  value: T
  label: string
  description?: string
  icon?: IconName
}

interface Props<T extends string | number> {
  visible: boolean
  title: string
  options: readonly Option<T>[]
  value?: T | null
  onSelect: (value: T) => void
  onClose: () => void
}

/** A tappable list in a sheet: the mobile replacement for a <select>. */
export function OptionSheet<T extends string | number>({
  visible,
  title,
  options,
  value,
  onSelect,
  onClose,
}: Props<T>) {
  const { colors } = useTheme()
  return (
    <Sheet visible={visible} onClose={onClose} title={title}>
      <View style={{ marginHorizontal: -16 }}>
        {options.map((option) => {
          const selected = option.value === value
          return (
            <Pressable
              key={String(option.value)}
              accessibilityRole="button"
              accessibilityState={{ selected }}
              onPress={() => {
                haptics.tap()
                onSelect(option.value)
                onClose()
              }}
              style={({ pressed }) => ({
                minHeight: MIN_TOUCH + 6,
                paddingHorizontal: 16,
                paddingVertical: 8,
                flexDirection: "row",
                alignItems: "center",
                gap: 12,
                backgroundColor: pressed ? colors.surfaceRaised : "transparent",
              })}
            >
              {option.icon ? <Icon name={option.icon} color={selected ? "primary" : "muted"} /> : null}
              <View style={{ flex: 1 }}>
                <Text style={{ fontWeight: selected ? "700" : "500" }}>{option.label}</Text>
                {option.description ? (
                  <Text variant="caption" tone="muted">
                    {option.description}
                  </Text>
                ) : null}
              </View>
              {selected ? <Icon name="checkmark" color="primary" /> : null}
            </Pressable>
          )
        })}
      </View>
    </Sheet>
  )
}
