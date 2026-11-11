import { Pressable, TextInput, View } from "react-native"

import { MIN_TOUCH, radius } from "@/theme/tokens"
import { useTheme } from "@/theme/theme"
import { Icon } from "./icon"

interface Props {
  value: string
  onChangeText: (value: string) => void
  placeholder?: string
}

export function SearchBar({ value, onChangeText, placeholder = "Search" }: Props) {
  const { colors } = useTheme()
  return (
    <View
      style={{
        flexDirection: "row",
        alignItems: "center",
        gap: 8,
        minHeight: MIN_TOUCH,
        borderRadius: radius.md,
        backgroundColor: colors.surface,
        borderWidth: 1,
        borderColor: colors.border,
        paddingHorizontal: 12,
      }}
    >
      <Icon name="search" size={18} color="muted" />
      <TextInput
        accessibilityLabel={placeholder}
        value={value}
        onChangeText={onChangeText}
        placeholder={placeholder}
        placeholderTextColor={colors.muted}
        returnKeyType="search"
        autoCapitalize="none"
        autoCorrect={false}
        clearButtonMode="never"
        style={{ flex: 1, color: colors.text, fontSize: 16, paddingVertical: 8 }}
      />
      {value ? (
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Clear search"
          hitSlop={10}
          onPress={() => onChangeText("")}
        >
          <Icon name="close-circle" size={18} color="muted" />
        </Pressable>
      ) : null}
    </View>
  )
}
