import { Loader2, ServerCrash } from "lucide-react"
import { Navigate, Outlet, useLocation, useSearchParams } from "react-router-dom"

import { Button } from "@/components/ui/button"
import { useAuth } from "./auth-context"
import { safeNextPath } from "./password-policy"

function FullPageStatus({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="flex min-h-dvh items-center justify-center p-6"
      role="status"
      aria-live="polite"
    >
      {children}
    </div>
  )
}

/** Everything inside requires a signed-in user. Others are sent to /login and brought back. */
export function ProtectedRoute() {
  const { state, refresh } = useAuth()
  const location = useLocation()

  if (state.status === "loading") {
    return (
      <FullPageStatus>
        <div className="flex items-center gap-3 text-muted-foreground">
          <Loader2 className="size-5 animate-spin" aria-hidden />
          <span>Checking your session…</span>
        </div>
      </FullPageStatus>
    )
  }
  if (state.status === "error") {
    return (
      <FullPageStatus>
        <div role="alert" className="max-w-sm space-y-3 text-center">
          <ServerCrash className="mx-auto size-8 text-destructive" aria-hidden />
          <p className="font-medium">We could not reach the server</p>
          <p className="text-sm text-muted-foreground">{state.message}</p>
          <Button onClick={() => void refresh()}>Try again</Button>
        </div>
      </FullPageStatus>
    )
  }
  if (state.status === "unauthenticated") {
    const next = `${location.pathname}${location.search}`
    const target = next === "/" ? "/login" : `/login?next=${encodeURIComponent(next)}`
    return <Navigate to={target} replace />
  }
  return <Outlet />
}

/** Sign-in and sign-up pages: signed-in users are sent on to the app instead. */
export function PublicOnlyRoute() {
  const { state } = useAuth()
  const [params] = useSearchParams()

  if (state.status === "loading") {
    return (
      <FullPageStatus>
        <Loader2 className="size-5 animate-spin text-muted-foreground" aria-hidden />
        <span className="sr-only">Loading</span>
      </FullPageStatus>
    )
  }
  if (state.status === "authenticated") {
    return <Navigate to={safeNextPath(params.get("next"))} replace />
  }
  return <Outlet />
}
