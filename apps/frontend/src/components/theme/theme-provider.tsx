import { useCallback, useMemo, useState, type ReactNode } from "react"

import { ThemeContext, type Theme } from "./theme-context"

const STORAGE_KEY = "theme"

function readInitialTheme(): Theme {
  // index.html already applied the saved theme; mirror it into state.
  return document.documentElement.classList.contains("dark") ? "dark" : "light"
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(readInitialTheme)

  const setTheme = useCallback((next: Theme) => {
    setThemeState(next)
    document.documentElement.classList.toggle("dark", next === "dark")
    document.documentElement.style.colorScheme = next
    try {
      localStorage.setItem(STORAGE_KEY, next)
    } catch {
      // Storage can be blocked (private mode); the theme still applies for this session.
    }
  }, [])

  const value = useMemo(() => ({ theme, setTheme }), [theme, setTheme])
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}
