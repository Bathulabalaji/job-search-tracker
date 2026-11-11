import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it } from "vitest"

import { ProtectedRoute } from "@/features/auth/route-guards"
import { apiError, authResponse, makeUser, mockApi } from "@/test/mock-api"
import { renderRoutes } from "@/test/render"
import { AccountPage } from "./account-page"

const routes = [
  { path: "/login", element: <p>Login page</p> },
  { element: <ProtectedRoute />, children: [{ path: "/account", element: <AccountPage /> }] },
]

describe("AccountPage profile", () => {
  it("shows the signed-in user's details", async () => {
    mockApi({ "GET /auth/me": { body: authResponse() } })
    renderRoutes(routes, { route: "/account" })
    expect(await screen.findByDisplayValue("Alice Walker")).toBeInTheDocument()
    expect(screen.getByDisplayValue("alice@example.com")).toHaveAttribute("readonly")
    expect(screen.getByText("Email verified")).toBeInTheDocument()
  })

  it("only enables saving after a change, validates, and updates the name", async () => {
    const api = mockApi({
      "GET /auth/me": { body: authResponse() },
      "PATCH /auth/me": (call) => ({
        body: makeUser({ full_name: (call.body as { full_name: string }).full_name }),
      }),
    })
    renderRoutes(routes, { route: "/account" })
    const user = userEvent.setup()
    const save = await screen.findByRole("button", { name: /save changes/i })
    expect(save).toBeDisabled()

    const name = screen.getByLabelText("Full name")
    await user.clear(name)
    await user.click(save)
    expect(await screen.findByText("Enter your full name")).toBeInTheDocument()

    await user.type(name, "Alice B. Walker")
    await user.click(save)
    await waitFor(() => expect(api.called("PATCH", "/auth/me")).toHaveLength(1))
    expect(api.called("PATCH", "/auth/me")[0]?.body).toEqual({ full_name: "Alice B. Walker" })
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /save changes/i })).toBeDisabled(),
    )
  })

  it("sends the CSRF token on profile updates", async () => {
    const api = mockApi({
      "GET /auth/me": { body: authResponse({ csrf_token: "csrf-xyz" }) },
      "PATCH /auth/me": { body: makeUser({ full_name: "New Name" }) },
    })
    renderRoutes(routes, { route: "/account" })
    const user = userEvent.setup()
    const name = await screen.findByLabelText("Full name")
    await user.clear(name)
    await user.type(name, "New Name")
    await user.click(screen.getByRole("button", { name: /save changes/i }))
    await waitFor(() => expect(api.called("PATCH", "/auth/me")).toHaveLength(1))
    expect(api.called("PATCH", "/auth/me")[0]?.headers["X-CSRF-Token"]).toBe("csrf-xyz")
  })
})

describe("AccountPage password", () => {
  async function fill(current: string, next: string, confirm = next) {
    const user = userEvent.setup()
    await user.type(await screen.findByLabelText("Current password"), current)
    await user.type(screen.getByLabelText("New password"), next)
    await user.type(screen.getByLabelText("Confirm new password"), confirm)
    await user.click(screen.getByRole("button", { name: /change password/i }))
  }

  it("validates the new password", async () => {
    const api = mockApi({ "GET /auth/me": { body: authResponse() } })
    renderRoutes(routes, { route: "/account" })
    await fill("Correct-Horse-9", "short1")
    expect(await screen.findByText("Use at least 10 characters.")).toBeInTheDocument()
    expect(api.called("POST", "/auth/change-password")).toHaveLength(0)
  })

  it("changes the password", async () => {
    const api = mockApi({
      "GET /auth/me": { body: authResponse() },
      "POST /auth/change-password": { body: { message: "Password changed." } },
    })
    renderRoutes(routes, { route: "/account" })
    await fill("Correct-Horse-9", "Another-Secret-77")
    await waitFor(() => expect(api.called("POST", "/auth/change-password")).toHaveLength(1))
    expect(api.called("POST", "/auth/change-password")[0]?.body).toEqual({
      current_password: "Correct-Horse-9",
      new_password: "Another-Secret-77",
    })
    // The form is cleared afterwards so nothing sensitive lingers on screen.
    await waitFor(() => expect(screen.getByLabelText("Current password")).toHaveValue(""))
  })

  it("a wrong current password is a field error and does NOT sign the user out", async () => {
    mockApi({
      "GET /auth/me": { body: authResponse() },
      "POST /auth/change-password": apiError(
        400,
        "incorrect_password",
        "Your current password is incorrect.",
      ),
    })
    renderRoutes(routes, { route: "/account" })
    await fill("Wrong-Password-1", "Another-Secret-77")
    expect(await screen.findByText("Your current password is incorrect.")).toBeInTheDocument()
    expect(screen.queryByText("Login page")).not.toBeInTheDocument()
  })

  it("offers a set-password email to accounts that only use Google", async () => {
    const api = mockApi({
      "GET /auth/me": {
        body: authResponse({ user: makeUser({ has_password: false, google_linked: true }) }),
      },
      "POST /auth/forgot-password": { status: 202, body: { message: "ok" } },
    })
    renderRoutes(routes, { route: "/account" })
    const user = userEvent.setup()
    expect(await screen.findByText(/you sign in with google/i)).toBeInTheDocument()
    expect(screen.queryByLabelText("Current password")).not.toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: /email me a link to set a password/i }))
    await waitFor(() => expect(api.called("POST", "/auth/forgot-password")).toHaveLength(1))
    expect(api.called("POST", "/auth/forgot-password")[0]?.body).toEqual({
      email: "alice@example.com",
    })
  })
})

describe("AccountPage sessions", () => {
  it("signs out of every device and returns to the login page", async () => {
    const api = mockApi({
      "GET /auth/me": { body: authResponse() },
      "POST /auth/logout-all": { status: 204 },
      "POST /auth/logout": { status: 204 },
    })
    renderRoutes(routes, { route: "/account" })
    const user = userEvent.setup()
    await user.click(await screen.findByRole("button", { name: /sign out of all devices/i }))
    expect(await screen.findByText("Login page")).toBeInTheDocument()
    expect(api.called("POST", "/auth/logout-all")).toHaveLength(1)
  })
})
