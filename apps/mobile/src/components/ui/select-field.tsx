import { useState } from "react"
import { Pressable, StyleSheet, View } from "react-native"

import { MIN_TOUCH, radius } from "@/theme/tokens"
import { useTheme } from "@/theme/theme"
import { Icon } from "./icon"
import { OptionSheet, type Option } from "./option-sheet"
import { Text } from "./text"

interface Props<T extends string | number> {
  label: string
  value: T | null | undefined
  options: readonly Option<T>[]
  onChange: (value: T) => void
  placeholder?: string
  error?: string
}

export function SelectField<T extends string | number>({
  label,
  value,
  options,
  onChange,
  placeholder = "Select…",
  error,
}: Props<T>) {
  const { colors } = useTheme()
  const [open, setOpen] = useState(false)
  const current = options.find((o) => o.value === value)
  return (
    <View style={{ gap: 6 }}>
      <Text variant="small" style={{ fontWeight: "600" }}>
        {label}
      </Text>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={`${label}: ${current?.label ?? "none"}`}
        onPress={() => setOpen(true)}
        style={[
          styles.box,
          {
            backgroundColor: colors.surface,
            borderColor: error ? colors.danger : colors.border,
          },
        ]}
      >
        <Text tone={current ? "default" : "muted"} style={{ flex: 1 }} numberOfLines={1}>
          {current?.label ?? placeholder}
        </Text>
        <Icon name="chevron-down" size={18} color="muted" />
      </Pressable>
      {error ? (
        <Text variant="caption" tone="danger">
          {error}
        </Text>
      ) : null}
      <OptionSheet
        visible={open}
        title={label}
        options={options}
        value={value}
        onSelect={onChange}
        onClose={() => setOpen(false)}
      />
    </View>
  )
}

const styles = StyleSheet.create({
  box: {
    minHeight: MIN_TOUCH + 4,
    borderRadius: radius.md,
    borderWidth: StyleSheet.hairlineWidth,
    paddingHorizontal: 14,
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
})
