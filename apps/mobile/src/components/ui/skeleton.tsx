import { useEffect, useRef } from "react"
import { Animated, View, type DimensionValue, type StyleProp, type ViewStyle } from "react-native"

import { radius } from "@/theme/tokens"
import { useTheme } from "@/theme/theme"

interface Props {
  width?: DimensionValue
  height?: number
  style?: StyleProp<ViewStyle>
}

/** A softly pulsing placeholder shown while data loads. */
export function Skeleton({ width = "100%", height = 16, style }: Props) {
  const { colors } = useTheme()
  const opacity = useRef(new Animated.Value(0.5)).current
  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(opacity, { toValue: 1, duration: 800, useNativeDriver: true }),
        Animated.timing(opacity, { toValue: 0.5, duration: 800, useNativeDriver: true }),
      ]),
    )
    loop.start()
    return () => loop.stop()
  }, [opacity])
  return (
    <Animated.View
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
      style={[
        { width, height, borderRadius: radius.sm, backgroundColor: colors.surfaceRaised, opacity },
        style,
      ]}
    />
  )
}

/** A card-shaped skeleton for list screens. */
export function SkeletonCard() {
  const { colors } = useTheme()
  return (
    <View
      style={{
        backgroundColor: colors.surface,
        borderColor: colors.border,
        borderWidth: 1,
        borderRadius: radius.lg,
        padding: 16,
        gap: 10,
      }}
    >
      <Skeleton width="55%" height={16} />
      <Skeleton width="35%" height={12} />
      <Skeleton width="80%" height={12} />
    </View>
  )
}

export function SkeletonList({ count = 4 }: { count?: number }) {
  return (
    <View
      style={{ gap: 12 }}
      accessibilityRole="progressbar"
      accessibilityLabel="Loading"
      accessible
    >
      {Array.from({ length: count }, (_, i) => (
        <SkeletonCard key={i} />
      ))}
    </View>
  )
}
