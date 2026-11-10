import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react"

import { LogInteractionDialog } from "@/features/detail/log-interaction-dialog"
import { QuickAddDialog } from "@/features/opportunities/quick-add-dialog"
import { CommandPalette } from "./command-palette"
import { QuickActionsContext, type QuickActions } from "./quick-actions-context"

export function QuickActionsProvider({ children }: { children: ReactNode }) {
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [addOpen, setAddOpen] = useState(false)
  const [logOpen, setLogOpen] = useState(false)
  const [logOpportunityId, setLogOpportunityId] = useState<number | undefined>(undefined)

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key.toLowerCase() === "k" && (event.metaKey || event.ctrlKey)) {
        event.preventDefault()
        setPaletteOpen((open) => !open)
      }
    }
    window.addEventListener("keydown", onKeyDown)
    return () => window.removeEventListener("keydown", onKeyDown)
  }, [])

  const openLogInteraction = useCallback((opportunityId?: number) => {
    setLogOpportunityId(opportunityId)
    setLogOpen(true)
  }, [])

  const value = useMemo<QuickActions>(
    () => ({
      openAddOpportunity: () => setAddOpen(true),
      openLogInteraction,
      openPalette: () => setPaletteOpen(true),
    }),
    [openLogInteraction],
  )

  return (
    <QuickActionsContext.Provider value={value}>
      {children}
      <CommandPalette
        open={paletteOpen}
        onOpenChange={setPaletteOpen}
        onAddOpportunity={() => setAddOpen(true)}
        onLogInteraction={() => openLogInteraction()}
      />
      <QuickAddDialog open={addOpen} onOpenChange={setAddOpen} />
      <LogInteractionDialog open={logOpen} onOpenChange={setLogOpen} opportunityId={logOpportunityId} />
    </QuickActionsContext.Provider>
  )
}
