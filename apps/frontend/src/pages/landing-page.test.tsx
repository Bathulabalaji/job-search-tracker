import { screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { HomeRoute } from "@/pages/landing-page"
import { apiError, authResponse, mockApi } from "@/test/mock-api"
import { renderRoutes } from "@/test/render"

const routes = [
  { path: "/", element: <HomeRoute /> },
  { path: "/today", element: <p>Today page</p> },
]

describe("landing page", () => {
  it("shows the pitch and sign-up and sign-in links to signed-out visitors", async () => {
    mockApi({ "GET /auth/me": apiError(401, "not_authenticated", "Not signed in.") })
    renderRoutes(routes, { route: "/" })
    expect(
      await screen.findByRole("heading", { level: 1, name: /run your job search/i }),
    ).toBeInTheDocument()
    const signUp = screen.getAllByRole("link", { name: /get started|create your account/i })
    expect(signUp.length).toBeGreaterThan(0)
    for (const link of signUp) expect(link).toHaveAttribute("href", "/register")
    expect(screen.getAllByRole("link", { name: /sign in/i })[0]).toHaveAttribute("href", "/login")
  })

  it("sends signed-in users straight to their day", async () => {
    mockApi({ "GET /auth/me": { body: authResponse() } })
    const { router } = renderRoutes(routes, { route: "/" })
    expect(await screen.findByText("Today page")).toBeInTheDocument()
    expect(router.state.location.pathname).toBe("/today")
  })
})
