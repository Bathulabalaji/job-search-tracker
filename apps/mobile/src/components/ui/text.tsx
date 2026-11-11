import { Text as RNText, type TextProps as RNTextProps, type TextStyle } from "react-native"

import { fontSize } from "@/theme/tokens"
import { useTheme } from "@/theme/theme"

type Variant = "hero" | "title" | "heading" | "body" | "small" | "caption" | "mono"
type Tone = "default" | "muted" | "primary" | "danger" | "success" | "warning" | "onPrimary"

const VARIANTS: Record<Variant, TextStyle> = {
  hero: { fontSize: fontSize.hero, fontWeight: "700", letterSpacing: -0.8, lineHeight: 40 },
  title: { fontSize: fontSize.xxl, fontWeight: "700", letterSpacing: -0.5, lineHeight: 34 },
  heading: { fontSize: fontSize.lg, fontWeight: "600", letterSpacing: -0.2, lineHeight: 24 },
  body: { fontSize: fontSize.md, lineHeight: 22 },
  small: { fontSize: fontSize.sm, lineHeight: 20 },
  caption: { fontSize: fontSize.xs, lineHeight: 16, letterSpacing: 0.2 },
  mono: { fontSize: fontSize.sm, fontVariant: ["tabular-nums"], fontWeight: "600" },
}

export interface TextProps extends RNTextProps {
  variant?: Variant
  tone?: Tone
}

export function Text({ variant = "body", tone = "default", style, ...rest }: TextProps) {
  const { colors } = useTheme()
  const color = {
    default: colors.text,
    muted: colors.muted,
    primary: colors.primary,
    danger: colors.danger,
    success: colors.success,
    warning: colors.warning,
    onPrimary: colors.onPrimary,
  }[tone]
  // Honour the user's system font-size setting, but cap it so layouts do not break.
  return <RNText maxFontSizeMultiplier={1.4} style={[VARIANTS[variant], { color }, style]} {...rest} />
}
