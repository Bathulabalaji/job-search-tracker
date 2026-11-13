import { Plus, Search } from "lucide-react"
import { useState } from "react"
import { Outlet, useMatches } from "react-router-dom"

import { Button } from "@/components/ui/button"
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar"
import { QuickActionsProvider } from "@/features/quick-actions/quick-actions-provider"
import { useQuickActions } from "@/features/quick-actions/quick-actions-context"
import { AppSidebar } from "./app-sidebar"

function TopBar() {
  const { openPalette, openAddOpportunity } = useQuickActions()
  const isMac = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform)

  return (
    <header className="sticky top-0 z-20 flex h-14 shrink-0 items-center gap-2 border-b bg-background/95 px-3 pt-[env(safe-area-inset-top)] backdrop-blur sm:px-4">
      <SidebarTrigger aria-label="Toggle sidebar" />
      {/* min-w-0 + truncate let the search field shrink instead of pushing the page wider. */}
      <Button
        variant="outline"
        onClick={openPalette}
        className="h-9 min-w-0 flex-1 justify-start gap-2 text-muted-foreground sm:max-w-xs"
        aria-label="Open command palette"
      >
        <Search className="size-4 shrink-0" />
        <span className="min-w-0 flex-1 truncate text-left">Search or jump to…</span>
        <kbd className="hidden rounded border bg-muted px-1.5 py-0.5 font-mono text-[11px] md:inline">
          {isMac ? "⌘K" : "Ctrl K"}
        </kbd>
      </Button>
      <Button
        onClick={openAddOpportunity}
        className="ml-auto shrink-0"
        aria-label="Add opportunity"
      >
        <Plus />
        <span className="hidden sm:inline">Add opportunity</span>
      </Button>
    </header>
  )
}

export function AppLayout() {
  // Phones use the slide-over sidebar. Tablets start collapsed to icons so content gets the room;
  // wide screens start expanded. The user can still toggle at any size.
  const [defaultOpen] = useState(() => window.matchMedia("(min-width: 1024px)").matches)
  // Pages like the assistant fill the whole area below the top bar and scroll internally.
  const fullBleed = useMatches().some(
    (match) => (match.handle as { fullBleed?: boolean } | undefined)?.fullBleed === true,
  )

  return (
    <SidebarProvider defaultOpen={defaultOpen}>
      <QuickActionsProvider>
        <AppSidebar />
        {/* min-w-0: a flex child never shrinks below its content, so wide boards and tables would
            otherwise stretch the whole page instead of scrolling inside their own container. */}
        <SidebarInset className="min-w-0">
          <TopBar />
          <main
            className={
              fullBleed
                ? "min-w-0 flex-1"
                : "min-w-0 flex-1 p-4 pb-[max(1rem,env(safe-area-inset-bottom))] sm:p-6 md:p-8"
            }
          >
            <Outlet />
          </main>
        </SidebarInset>
      </QuickActionsProvider>
    </SidebarProvider>
  )
}
