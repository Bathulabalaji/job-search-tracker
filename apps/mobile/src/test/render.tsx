import { render } from "@testing-library/react-native"

import { ThemeProvider } from "@/theme/theme"

/** Renders with the real theme so components get their colours. */
export async function renderWithTheme(ui: React.ReactElement) {
  return await render(<ThemeProvider>{ui}</ThemeProvider>)
}
