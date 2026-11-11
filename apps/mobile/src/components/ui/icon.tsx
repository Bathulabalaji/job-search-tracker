import { Ionicons } from "@expo/vector-icons"
import type { ComponentProps } from "react"

import { useTheme } from "@/theme/theme"
import type { Palette } from "@/theme/tokens"

export type IconName = ComponentProps<typeof Ionicons>["name"]

interface IconProps {
  name: IconName
  size?: number
  color?: keyof Palette | (string & {})
}

export function Icon({ name, size = 20, color = "text" }: IconProps) {
  const { colors } = useTheme()
  const resolved = color in colors ? colors[color as keyof Palette] : color
  return <Ionicons name={name} size={size} color={resolved} accessible={false} />
}
