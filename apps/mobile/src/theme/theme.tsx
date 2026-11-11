import * as SecureStore from "expo-secure-store"
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react"
import { Platform, useColorScheme } from "react-native"

import { darkPalette, lightPalette, type Palette } from "./tokens"

export type ThemePreference = "system" | "dark" | "light"

interface ThemeValue {
  colors: Palette
  isDark: boolean
  preference: ThemePreference
  setPreference: (value: ThemePreference) => void
}

const STORAGE_KEY = "theme-preference"
const ThemeContext = createContext<ThemeValue | null>(null)

async function readPreference(): Promise<ThemePreference> {
  try {
    const value =
      Platform.OS === "web"
        ? window.localStorage.getItem(STORAGE_KEY)
        : await SecureStore.getItemAsync(STORAGE_KEY)
    return value === "dark" || value === "light" || value === "system" ? value : "dark"
  } catch {
    return "dark"
  }
}

function writePreference(value: ThemePreference): void {
  try {
    if (Platform.OS === "web") window.localStorage.setItem(STORAGE_KEY, value)
    else void SecureStore.setItemAsync(STORAGE_KEY, value)
  } catch {
    // A preference that cannot be saved is not worth an error: it just resets next launch.
  }
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const system = useColorScheme()
  const [preference, setPreferenceState] = useState<ThemePreference>("dark")

  useEffect(() => {
    let cancelled = false
    void readPreference().then((value) => {
      if (!cancelled) setPreferenceState(value)
    })
    return () => {
      cancelled = true
    }
  }, [])

  const setPreference = useCallback((value: ThemePreference) => {
    setPreferenceState(value)
    writePreference(value)
  }, [])

  const value = useMemo<ThemeValue>(() => {
    const isDark = preference === "system" ? system !== "light" : preference === "dark"
    return { colors: isDark ? darkPalette : lightPalette, isDark, preference, setPreference }
  }, [preference, system, setPreference])

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export function useTheme(): ThemeValue {
  const value = useContext(ThemeContext)
  if (!value) throw new Error("useTheme must be used inside <ThemeProvider>")
  return value
}
