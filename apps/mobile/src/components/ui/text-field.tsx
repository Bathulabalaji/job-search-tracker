import { useState } from "react"
import { Pressable, StyleSheet, TextInput, View, type TextInputProps } from "react-native"

import { MIN_TOUCH, radius } from "@/theme/tokens"
import { useTheme } from "@/theme/theme"
import { Icon } from "./icon"
import { Text } from "./text"

export interface TextFieldProps extends Omit<TextInputProps, "style"> {
  label: string
  error?: string
  hint?: string
  /** Show a reveal/hide button. Use for passwords. */
  secureToggle?: boolean
  multiline?: boolean
}

export function TextField({
  label,
  error,
  hint,
  secureToggle = false,
  multiline = false,
  ...input
}: TextFieldProps) {
  const { colors } = useTheme()
  const [focused, setFocused] = useState(false)
  const [revealed, setRevealed] = useState(false)

  return (
    <View style={{ gap: 6 }}>
      <Text variant="small" style={{ fontWeight: "600" }}>
        {label}
      </Text>
      <View
        style={[
          styles.box,
          {
            backgroundColor: colors.surface,
            borderColor: error ? colors.danger : focused ? colors.primary : colors.border,
            minHeight: multiline ? 96 : MIN_TOUCH + 4,
            borderWidth: focused || error ? 1.5 : StyleSheet.hairlineWidth,
          },
        ]}
      >
        <TextInput
          accessibilityLabel={label}
          placeholderTextColor={colors.muted}
          selectionColor={colors.primary}
          {...input}
          multiline={multiline}
          secureTextEntry={secureToggle ? !revealed : input.secureTextEntry}
          onFocus={(e) => {
            setFocused(true)
            input.onFocus?.(e)
          }}
          onBlur={(e) => {
            setFocused(false)
            input.onBlur?.(e)
          }}
          style={[
            styles.input,
            { color: colors.text },
            multiline && { textAlignVertical: "top", paddingTop: 12, minHeight: 96 },
          ]}
        />
        {secureToggle ? (
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={revealed ? "Hide password" : "Show password"}
            onPress={() => setRevealed((v) => !v)}
            hitSlop={10}
            style={styles.toggle}
          >
            <Icon name={revealed ? "eye-off-outline" : "eye-outline"} color="muted" />
          </Pressable>
        ) : null}
      </View>
      {error ? (
        <Text variant="caption" tone="danger" accessibilityRole="alert">
          {error}
        </Text>
      ) : hint ? (
        <Text variant="caption" tone="muted">
          {hint}
        </Text>
      ) : null}
    </View>
  )
}

const styles = StyleSheet.create({
  box: { borderRadius: radius.md, flexDirection: "row", alignItems: "center" },
  input: { flex: 1, fontSize: 16, paddingHorizontal: 14, paddingVertical: 10 },
  toggle: { paddingRight: 14 },
})
