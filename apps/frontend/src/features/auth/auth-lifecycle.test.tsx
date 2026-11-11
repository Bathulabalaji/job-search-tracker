import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it } from "vitest"

import { useAuth } from "@/features/auth/auth-context"
import { getCsrfToken } from "@/lib/csrf"
import { apiError, authResponse, mockApi } from "@/test/mock-api"
import { renderRoutes } from "@/test/render"
import { LoginPage } from "@/pages/auth/login-page"
import { ProtectedRoute, PublicOnlyRoute } from "./route-guards"

function Home() {
  const { state, signOut } = useAuth()
  return (
    <div>
      <p>Home for {state.user?.full_name}</p>
      <button onClick={() => void signOut()}>Sign out</button>
    </div>
  )
}

const routes = [
  { element: <PublicOnlyRoute />, children: [{ path: "/login", element: <LoginPage /> }] },
  { element: <ProtectedRoute />, children: [{ path: "/", element: <Home /> }] },
]

describe("authentication lifecycle", () => {
  it("sign in -> use the app -> sign out -> the app is locked again", async () => {
    let signedIn = false
    const api = mockApi({
      "GET /auth/me": () =>
        signedIn ? { body: authResponse() } : apiError(401, "not_authenticated", "Please sign in."),
      "POST /auth/login": () => {
        signedIn = true
        return { body: authResponse({ csrf_token: "csrf-1" }) }
      },
      "POST /auth/logout": () => {
        signedIn = false
        return { status: 204 }
      },
    })
    const { router, queryClient } = renderRoutes(routes, { route: "/" })
    const user = userEvent.setup()

    // Locked out at first.
    await screen.findByRole("button", { name: /^sign in$/i })
    expect(router.state.location.pathname).toBe("/login")

    await user.type(screen.getByLabelText(/^email/i), "alice@example.com")
    await user.type(screen.getByLabelText(/^password/i), "Correct-Horse-9")
    await user.click(screen.getByRole("button", { name: /^sign in$/i }))
    expect(await screen.findByText("Home for Alice Walker")).toBeInTheDocument()
    expect(getCsrfToken()).toBe("csrf-1")

    queryClient.setQueryData(["opportunities"], [{ company: "Private Co" }])
    await user.click(screen.getByRole("button", { name: "Sign out" }))

    await waitFor(() => expect(router.state.location.pathname).toBe("/login"))
    expect(api.called("POST", "/auth/logout")).toHaveLength(1)
    expect(getCsrfToken()).toBeNull()
    // Nothing from the previous user survives in memory for the next person on this browser.
    expect(queryClient.getQueryData(["opportunities"])).toBeUndefined()
  })

  it("signs the browser out locally even if the logout request fails", async () => {
    mockApi({
      "GET /auth/me": { body: authResponse() },
      "POST /auth/logout": () => {
        throw new TypeError("Failed to fetch")
      },
    })
    const { router } = renderRoutes(routes, { route: "/" })
    const user = userEvent.setup()
    await user.click(await screen.findByRole("button", { name: "Sign out" }))
    await waitFor(() => expect(router.state.location.pathname).toBe("/login"))
    expect(getCsrfToken()).toBeNull()
  })

  it("signing in as someone else clears the previous user's cached data", async () => {
    mockApi({
      "GET /auth/me": apiError(401, "not_authenticated", "Please sign in."),
      "POST /auth/login": { body: authResponse() },
    })
    const { queryClient } = renderRoutes(routes, { route: "/login" })
    queryClient.setQueryData(["opportunities"], [{ company: "Previous user's data" }])
    const user = userEvent.setup()
    await user.type(await screen.findByLabelText(/^email/i), "alice@example.com")
    await user.type(screen.getByLabelText(/^password/i), "Correct-Horse-9")
    await user.click(screen.getByRole("button", { name: /^sign in$/i }))
    await screen.findByText("Home for Alice Walker")
    expect(queryClient.getQueryData(["opportunities"])).toBeUndefined()
  })
})
