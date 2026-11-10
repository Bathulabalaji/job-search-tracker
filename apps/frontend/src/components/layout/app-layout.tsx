import { Plus, Search } from "lucide-react"
import { Outlet } from "react-router-dom"

import { Button } from "@/components/ui/button"
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar"
import { QuickActionsProvider } from "@/features/quick-actions/quick-actions-provider"
import { useQuickActions } from "@/features/quick-actions/quick-actions-context"
import { AppSidebar } from "./app-sidebar"

function TopBar() {
  const { openPalette, openAddOpportunity } = useQuickActions()
  const isMac = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform)

  return (
    <header className="flex h-14 items-center gap-2 border-b px-4">
      <SidebarTrigger />
      <Button
        variant="outline"
        onClick={openPalette}
        className="ml-2 h-9 w-full max-w-xs justify-start gap-2 text-muted-foreground"
        aria-label="Open command palette"
      >
        <Search className="size-4" />
        <span className="flex-1 text-left">Search or jump to…</span>
        <kbd className="rounded border bg-muted px-1.5 py-0.5 font-mono text-[11px]">
          {isMac ? "⌘K" : "Ctrl K"}
        </kbd>
      </Button>
      <Button onClick={openAddOpportunity} className="ml-auto">
        <Plus />
        <span className="hidden sm:inline">Add opportunity</span>
      </Button>
    </header>
  )
}

export function AppLayout() {
  return (
    <SidebarProvider>
      <QuickActionsProvider>
        <AppSidebar />
        <SidebarInset>
          <TopBar />
          <main className="flex-1 p-6 md:p-8">
            <Outlet />
          </main>
        </SidebarInset>
      </QuickActionsProvider>
    </SidebarProvider>
  )
}
