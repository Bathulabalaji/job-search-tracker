export interface Palette {
  bg: string
  surface: string
  surfaceRaised: string
  border: string
  text: string
  muted: string
  primary: string
  primarySoft: string
  onPrimary: string
  danger: string
  dangerSoft: string
  success: string
  successSoft: string
  warning: string
  warningSoft: string
  info: string
  overlay: string
}

/** Same look as the website: deep navy, one electric-indigo accent. */
export const darkPalette: Palette = {
  bg: "#060A18",
  surface: "#0E1424",
  surfaceRaised: "#161E35",
  border: "#222B45",
  text: "#F2F4FA",
  muted: "#98A1BC",
  primary: "#6D70F5",
  primarySoft: "rgba(109,112,245,0.16)",
  onPrimary: "#FFFFFF",
  danger: "#F87171",
  dangerSoft: "rgba(248,113,113,0.15)",
  success: "#34D399",
  successSoft: "rgba(52,211,153,0.15)",
  warning: "#FBBF24",
  warningSoft: "rgba(251,191,36,0.15)",
  info: "#38BDF8",
  overlay: "rgba(0,0,0,0.6)",
}

export const lightPalette: Palette = {
  bg: "#F5F6FB",
  surface: "#FFFFFF",
  surfaceRaised: "#EDEFF7",
  border: "#DFE3F0",
  text: "#0B1020",
  muted: "#57617C",
  primary: "#4F46E5",
  primarySoft: "rgba(79,70,229,0.10)",
  onPrimary: "#FFFFFF",
  danger: "#DC2626",
  dangerSoft: "rgba(220,38,38,0.10)",
  success: "#059669",
  successSoft: "rgba(5,150,105,0.10)",
  warning: "#B45309",
  warningSoft: "rgba(180,83,9,0.10)",
  info: "#0284C7",
  overlay: "rgba(10,14,30,0.45)",
}

export const space = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32 } as const
export const radius = { sm: 8, md: 12, lg: 16, xl: 22, pill: 999 } as const

/** Never smaller than 44pt, the platform guideline for a comfortable touch target. */
export const MIN_TOUCH = 44

export const fontSize = { xs: 12, sm: 14, md: 16, lg: 18, xl: 22, xxl: 28, hero: 34 } as const
