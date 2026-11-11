import { screen, waitFor } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { apiError, authResponse, mockApi } from "@/test/mock-api"
import { renderRoutes } from "@/test/render"
import { ProtectedRoute, PublicOnlyRoute } from "./route-guards"

const routes = [
  {
    path: "/login",
    element: <PublicOnlyRoute />,
    children: [{ index: true, element: <p>Login screen</p> }],
  },
  {
    element: <ProtectedRoute />,
    children: [
      { path: "/", element: <p>Today page</p> },
      { path: "/prep", element: <p>Prep page</p> },
    ],
  },
]

describe("ProtectedRoute", () => {
  it("shows a loading state while the session is being checked", async () => {
    mockApi({ "GET /auth/me": () => new Promise<never>(() => {}) })
    renderRoutes(routes, { route: "/prep" })
    expect(await screen.findByText(/checking your session/i)).toBeInTheDocument()
    expect(screen.queryByText("Prep page")).not.toBeInTheDocument()
  })

  it("sends signed-out visitors to the login page and remembers where they were going", async () => {
    mockApi({ "GET /auth/me": apiError(401, "not_authenticated", "Please sign in.") })
    const { router } = renderRoutes(routes, { route: "/prep" })

    expect(await screen.findByText("Login screen")).toBeInTheDocument()
    expect(router.state.location.pathname).toBe("/login")
    expect(router.state.location.search).toBe("?next=%2Fprep")
    expect(screen.queryByText("Prep page")).not.toBeInTheDocument()
  })

  it("does not add ?next for the home page", async () => {
    mockApi({ "GET /auth/me": apiError(401, "not_authenticated", "Please sign in.") })
    const { router } = renderRoutes(routes, { route: "/" })
    await screen.findByText("Login screen")
    expect(router.state.location.search).toBe("")
  })

  it("renders the page for a signed-in user", async () => {
    mockApi({ "GET /auth/me": { body: authResponse() } })
    renderRoutes(routes, { route: "/prep" })
    expect(await screen.findByText("Prep page")).toBeInTheDocument()
  })

  it("offers a retry when the server cannot be reached, instead of signing you out", async () => {
    let up = false
    mockApi({
      "GET /auth/me": () =>
        up ? { body: authResponse() } : { status: 500, body: { detail: "boom" } },
    })
    renderRoutes(routes, { route: "/prep" })

    expect(await screen.findByText(/could not reach the server/i)).toBeInTheDocument()
    expect(screen.queryByText("Login screen")).not.toBeInTheDocument()

    up = true
    screen.getByRole("button", { name: /try again/i }).click()
    expect(await screen.findByText("Prep page")).toBeInTheDocument()
  })
})

describe("PublicOnlyRoute", () => {
  it("shows the login page to signed-out visitors", async () => {
    mockApi({ "GET /auth/me": apiError(401, "not_authenticated", "Please sign in.") })
    renderRoutes(routes, { route: "/login" })
    expect(await screen.findByText("Login screen")).toBeInTheDocument()
  })

  it("moves signed-in users on to the app", async () => {
    mockApi({ "GET /auth/me": { body: authResponse() } })
    renderRoutes(routes, { route: "/login" })
    expect(await screen.findByText("Today page")).toBeInTheDocument()
  })

  it("returns signed-in users to where they were headed, but only to local paths", async () => {
    mockApi({ "GET /auth/me": { body: authResponse() } })
    renderRoutes(routes, { route: "/login?next=%2Fprep" })
    expect(await screen.findByText("Prep page")).toBeInTheDocument()
  })

  it("ignores an off-site ?next target", async () => {
    mockApi({ "GET /auth/me": { body: authResponse() } })
    const { router } = renderRoutes(routes, { route: "/login?next=https%3A%2F%2Fevil.example" })
    await screen.findByText("Today page")
    expect(router.state.location.pathname).toBe("/")
  })
})

describe("session expiry while using the app", () => {
  it("sends the user to the login page when the API says the session is gone", async () => {
    const { request } = await import("@/api/client")
    mockApi({
      "GET /auth/me": { body: authResponse() },
      "GET /opportunities": apiError(401, "not_authenticated", "Please sign in."),
    })
    const { router } = renderRoutes(routes, { route: "/prep" })
    await screen.findByText("Prep page")

    await request("/opportunities").catch(() => undefined)

    await waitFor(() => expect(router.state.location.pathname).toBe("/login"))
    expect(router.state.location.search).toBe("?next=%2Fprep")
  })

  it("drops cached data from the previous session", async () => {
    const { request } = await import("@/api/client")
    mockApi({
      "GET /auth/me": { body: authResponse() },
      "GET /opportunities": apiError(401, "not_authenticated", "Please sign in."),
    })
    const { queryClient } = renderRoutes(routes, { route: "/prep" })
    await screen.findByText("Prep page")
    queryClient.setQueryData(["opportunities"], [{ company: "Secret Co" }])

    await request("/opportunities").catch(() => undefined)

    await waitFor(() => expect(queryClient.getQueryData(["opportunities"])).toBeUndefined())
  })
})
