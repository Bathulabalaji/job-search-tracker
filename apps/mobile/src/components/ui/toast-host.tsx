import { useEffect, useRef, useState } from "react"
import { Animated, View } from "react-native"
import { useSafeAreaInsets } from "react-native-safe-area-context"

import { subscribeToToasts, type ToastMessage } from "@/lib/toast-bus"
import { haptics } from "@/lib/haptics"
import { radius } from "@/theme/tokens"
import { useTheme } from "@/theme/theme"
import { Icon } from "./icon"
import { Text } from "./text"

const VISIBLE_MS = 3200

/** Mount once near the root. Shows one toast at a time, above everything else. */
export function ToastHost() {
  const { colors } = useTheme()
  const insets = useSafeAreaInsets()
  const [current, setCurrent] = useState<ToastMessage | null>(null)
  const opacity = useRef(new Animated.Value(0)).current
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    return subscribeToToasts((message) => {
      setCurrent(message)
      if (message.kind === "error") haptics.error()
      else if (message.kind === "success") haptics.success()
      if (timer.current) clearTimeout(timer.current)
      Animated.timing(opacity, { toValue: 1, duration: 180, useNativeDriver: true }).start()
      timer.current = setTimeout(() => {
        Animated.timing(opacity, { toValue: 0, duration: 220, useNativeDriver: true }).start(() =>
          setCurrent(null),
        )
      }, VISIBLE_MS)
    })
  }, [opacity])

  if (!current) return null
  const accent =
    current.kind === "error" ? colors.danger : current.kind === "success" ? colors.success : colors.primary

  return (
    <Animated.View
      pointerEvents="none"
      accessibilityLiveRegion="polite"
      style={{
        position: "absolute",
        top: insets.top + 8,
        left: 16,
        right: 16,
        opacity,
        transform: [
          { translateY: opacity.interpolate({ inputRange: [0, 1], outputRange: [-12, 0] }) },
        ],
      }}
    >
      <View
        accessible
        accessibilityRole="alert"
        style={{
          flexDirection: "row",
          gap: 10,
          alignItems: "flex-start",
          backgroundColor: colors.surfaceRaised,
          borderColor: colors.border,
          borderWidth: 1,
          borderLeftColor: accent,
          borderLeftWidth: 4,
          borderRadius: radius.md,
          padding: 12,
          shadowColor: "#000",
          shadowOpacity: 0.25,
          shadowRadius: 12,
          shadowOffset: { width: 0, height: 4 },
          elevation: 6,
        }}
      >
        <Icon
          name={current.kind === "error" ? "alert-circle" : current.kind === "success" ? "checkmark-circle" : "information-circle"}
          color={accent}
        />
        <View style={{ flex: 1 }}>
          <Text style={{ fontWeight: "600" }}>{current.title}</Text>
          {current.description ? (
            <Text variant="small" tone="muted">
              {current.description}
            </Text>
          ) : null}
        </View>
      </View>
    </Animated.View>
  )
}
