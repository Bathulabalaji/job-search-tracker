import { createContext, useContext } from "react"

export interface QuickActions {
  openAddOpportunity: () => void
  /** Pass an id to log against a known opportunity; omit to pick one in the dialog. */
  openLogInteraction: (opportunityId?: number) => void
  openPalette: () => void
}

export const QuickActionsContext = createContext<QuickActions | null>(null)

export function useQuickActions(): QuickActions {
  const value = useContext(QuickActionsContext)
  if (!value) throw new Error("useQuickActions must be used inside <QuickActionsProvider>")
  return value
}
