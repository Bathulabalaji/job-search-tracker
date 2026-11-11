import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it } from "vitest"

import { getCsrfToken } from "@/lib/csrf"
import { PublicOnlyRoute } from "@/features/auth/route-guards"
import { apiError, authResponse, mockApi } from "@/test/mock-api"
import { renderRoutes } from "@/test/render"
import { LoginPage } from "./login-page"

const routes = [
  { element: <PublicOnlyRoute />, children: [{ path: "/login", element: <LoginPage /> }] },
  { path: "/", element: <p>Today page</p> },
  { path: "/prep", element: <p>Prep page</p> },
  { path: "/forgot-password", element: <p>Forgot page</p> },
  { path: "/register", element: <p>Register page</p> },
]

const signedOut = { "GET /auth/me": apiError(401, "not_authenticated", "Please sign in.") }

async function fillAndSubmit(email = "alice@example.com", password = "Correct-Horse-9") {
  const user = userEvent.setup()
  await user.type(await screen.findByLabelText(/^email/i), email)
  await user.type(screen.getByLabelText(/^password/i), password)
  await user.click(screen.getByRole("button", { name: /^sign in$/i }))
  return user
}

describe("LoginPage", () => {
  it("validates before calling the API", async () => {
    const api = mockApi(signedOut)
    renderRoutes(routes, { route: "/login" })
    const user = userEvent.setup()

    await user.click(await screen.findByRole("button", { name: /^sign in$/i }))
    expect(await screen.findByText("Enter your email address")).toBeInTheDocument()
    expect(screen.getByText("Enter your password")).toBeInTheDocument()

    await user.type(screen.getByLabelText(/^email/i), "not-an-email")
    await user.click(screen.getByRole("button", { name: /^sign in$/i }))
    expect(await screen.findByText("Enter a valid email address")).toBeInTheDocument()
    expect(api.called("POST", "/auth/login")).toHaveLength(0)
  })

  it("signs in, keeps the CSRF token in memory and goes to the app", async () => {
    const api = mockApi({
      ...signedOut,
      "POST /auth/login": { body: authResponse({ csrf_token: "csrf-from-login" }) },
    })
    renderRoutes(routes, { route: "/login" })
    await fillAndSubmit()

    expect(await screen.findByText("Today page")).toBeInTheDocument()
    expect(api.called("POST", "/auth/login")[0]?.body).toEqual({
      email: "alice@example.com",
      password: "Correct-Horse-9",
    })
    expect(getCsrfToken()).toBe("csrf-from-login")
    // Credentials are never persisted by the app itself.
    expect(JSON.stringify(localStorage)).not.toContain("Correct-Horse-9")
    expect(JSON.stringify(sessionStorage)).not.toContain("csrf-from-login")
  })

  it("returns to the page the user was trying to open", async () => {
    mockApi({ ...signedOut, "POST /auth/login": { body: authResponse() } })
    renderRoutes(routes, { route: "/login?next=%2Fprep" })
    await fillAndSubmit()
    expect(await screen.findByText("Prep page")).toBeInTheDocument()
  })

  it("shows a generic message for wrong credentials and stays on the page", async () => {
    mockApi({
      ...signedOut,
      "POST /auth/login": apiError(401, "invalid_credentials", "Invalid email or password."),
    })
    renderRoutes(routes, { route: "/login" })
    await fillAndSubmit()

    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid email or password.")
    expect(screen.getByRole("button", { name: /^sign in$/i })).toBeEnabled()
    expect(screen.queryByText("Today page")).not.toBeInTheDocument()
  })

  it("lets an unverified user ask for a new verification email", async () => {
    const api = mockApi({
      ...signedOut,
      "POST /auth/login": apiError(
        403,
        "email_not_verified",
        "Please verify your email address before signing in.",
      ),
      "POST /auth/resend-verification": { status: 202, body: { message: "ok" } },
    })
    renderRoutes(routes, { route: "/login" })
    const user = await fillAndSubmit()

    expect(await screen.findByText(/verify your email address/i)).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: /resend verification email/i }))
    await waitFor(() => expect(api.called("POST", "/auth/resend-verification")).toHaveLength(1))
    expect(api.called("POST", "/auth/resend-verification")[0]?.body).toEqual({
      email: "alice@example.com",
    })
  })

  it("says how long to wait when rate limited", async () => {
    mockApi({
      ...signedOut,
      "POST /auth/login": apiError(
        429,
        "rate_limited",
        "Too many attempts. Please wait a while and try again.",
        {
          "Retry-After": "600",
        },
      ),
    })
    renderRoutes(routes, { route: "/login" })
    await fillAndSubmit()
    expect(await screen.findByRole("alert")).toHaveTextContent(/about 10 minutes/i)
  })

  it("explains a suspended account", async () => {
    mockApi({
      ...signedOut,
      "POST /auth/login": apiError(403, "account_suspended", "This account has been suspended."),
    })
    renderRoutes(routes, { route: "/login" })
    await fillAndSubmit()
    expect(await screen.findByRole("alert")).toHaveTextContent(/suspended/i)
  })

  it("disables the button and shows progress while signing in", async () => {
    let release: () => void = () => {}
    mockApi({
      ...signedOut,
      "POST /auth/login": () =>
        new Promise((resolve) => {
          release = () => resolve({ body: authResponse() })
        }),
    })
    renderRoutes(routes, { route: "/login" })
    await fillAndSubmit()

    const button = await screen.findByRole("button", { name: /signing in/i })
    expect(button).toBeDisabled()
    release()
    expect(await screen.findByText("Today page")).toBeInTheDocument()
  })

  it("handles a network failure without crashing", async () => {
    mockApi({
      ...signedOut,
      "POST /auth/login": () => {
        throw new TypeError("Failed to fetch")
      },
    })
    renderRoutes(routes, { route: "/login" })
    await fillAndSubmit()
    expect(await screen.findByRole("alert")).toHaveTextContent(/cannot reach the api/i)
  })

  it("can show and hide the password", async () => {
    mockApi(signedOut)
    renderRoutes(routes, { route: "/login" })
    const user = userEvent.setup()
    const field = await screen.findByLabelText(/^password/i)
    expect(field).toHaveAttribute("type", "password")
    await user.click(screen.getByRole("button", { name: /show password/i }))
    expect(field).toHaveAttribute("type", "text")
  })

  it("links to the reset and sign-up pages", async () => {
    mockApi(signedOut)
    renderRoutes(routes, { route: "/login" })
    expect(await screen.findByRole("link", { name: /forgot password/i })).toHaveAttribute(
      "href",
      "/forgot-password",
    )
    expect(screen.getByRole("link", { name: /create an account/i })).toHaveAttribute(
      "href",
      "/register",
    )
  })

  it("explains an expired session", async () => {
    mockApi({
      "GET /auth/me": { body: authResponse() },
      "GET /x": apiError(401, "not_authenticated", "Please sign in."),
    })
    const { request } = await import("@/api/client")
    const result = renderRoutes([...routes, { path: "/app", element: <p>App</p> }], {
      route: "/login",
    })
    await screen.findByText("Today page")
    await request("/x").catch(() => undefined)
    await result.router.navigate("/login")
    expect(await screen.findByText(/your session expired/i)).toBeInTheDocument()
  })
})
