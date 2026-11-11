import { Command } from "lucide-react"
import { Link, Outlet } from "react-router-dom"

import { ThemeToggle } from "@/components/layout/theme-toggle"

/** Centered card shell for every signed-out page. */
export function AuthLayout() {
  return (
    <div className="flex min-h-dvh flex-col bg-background px-4 pt-[max(1rem,env(safe-area-inset-top))] pb-[max(1rem,env(safe-area-inset-bottom))]">
      <header className="mx-auto flex w-full max-w-md items-center justify-between py-2">
        <Link to="/" className="flex items-center gap-2 rounded-md font-semibold tracking-tight">
          <span className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <Command className="size-4" aria-hidden />
          </span>
          Jobs Tracker
        </Link>
        <ThemeToggle />
      </header>
      <main className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center py-6">
        <Outlet />
      </main>
    </div>
  )
}
