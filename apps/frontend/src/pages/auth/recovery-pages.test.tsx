import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it } from "vitest"

import { apiError, mockApi } from "@/test/mock-api"
import { renderRoutes } from "@/test/render"
import { ForgotPasswordPage } from "./forgot-password-page"
import { ResetPasswordPage } from "./reset-password-page"
import { VerifyEmailPage } from "./verify-email-page"

const routes = [
  { path: "/forgot-password", element: <ForgotPasswordPage /> },
  { path: "/reset-password", element: <ResetPasswordPage /> },
  { path: "/verify-email", element: <VerifyEmailPage /> },
  { path: "/login", element: <p>Login page</p> },
]
const signedOut = { "GET /auth/me": apiError(401, "not_authenticated", "Please sign in.") }
const TOKEN = "tok_abcdefghijklmnopqrstuvwxyz0123456789"

describe("ForgotPasswordPage", () => {
  it("validates the email", async () => {
    const api = mockApi(signedOut)
    renderRoutes(routes, { route: "/forgot-password" })
    const user = userEvent.setup()
    await user.click(await screen.findByRole("button", { name: /send reset link/i }))
    expect(await screen.findByText("Enter your email address")).toBeInTheDocument()
    await user.type(screen.getByLabelText(/^email/i), "nope")
    await user.click(screen.getByRole("button", { name: /send reset link/i }))
    expect(await screen.findByText("Enter a valid email address")).toBeInTheDocument()
    expect(api.called("POST", "/auth/forgot-password")).toHaveLength(0)
  })

  it("shows the same confirmation whether or not the account exists", async () => {
    const api = mockApi({
      ...signedOut,
      "POST /auth/forgot-password": { status: 202, body: { message: "If an account exists..." } },
    })
    renderRoutes(routes, { route: "/forgot-password" })
    const user = userEvent.setup()
    await user.type(await screen.findByLabelText(/^email/i), "ghost@example.com")
    await user.click(screen.getByRole("button", { name: /send reset link/i }))

    expect(await screen.findByRole("heading", { name: /check your email/i })).toBeInTheDocument()
    // Careful wording: it never claims an email was definitely sent.
    expect(screen.getByText(/if an account exists/i)).toBeInTheDocument()
    expect(api.called("POST", "/auth/forgot-password")[0]?.body).toEqual({
      email: "ghost@example.com",
    })
  })

  it("explains rate limiting", async () => {
    mockApi({
      ...signedOut,
      "POST /auth/forgot-password": apiError(429, "rate_limited", "Too many attempts.", {
        "Retry-After": "1800",
      }),
    })
    renderRoutes(routes, { route: "/forgot-password" })
    const user = userEvent.setup()
    await user.type(await screen.findByLabelText(/^email/i), "alice@example.com")
    await user.click(screen.getByRole("button", { name: /send reset link/i }))
    expect(await screen.findByRole("alert")).toHaveTextContent(/about 30 minutes/i)
  })
})

const linkOk = { "POST /auth/reset-password/check": { body: { message: "This link is valid." } } }

describe("ResetPasswordPage", () => {
  async function fill(password: string, confirm = password) {
    const user = userEvent.setup()
    await user.type(await screen.findByLabelText("New password"), password)
    await user.type(screen.getByLabelText("Confirm new password"), confirm)
    await user.click(screen.getByRole("button", { name: /update password/i }))
    return user
  }

  it("refuses to show the form without a token in the link", async () => {
    const api = mockApi({ ...signedOut, ...linkOk })
    renderRoutes(routes, { route: "/reset-password" })
    expect(await screen.findByRole("heading", { name: /cannot be used/i })).toBeInTheDocument()
    expect(screen.getByRole("link", { name: /request a new link/i })).toHaveAttribute(
      "href",
      "/forgot-password",
    )
    expect(api.called("POST", "/auth/reset-password/check")).toHaveLength(0)
  })

  it.each([
    ["token_expired", "This link has expired. Please request a new one.", /expired/i],
    ["token_used", "This link has already been used.", /already been used/i],
  ])("warns about a %s link before the user types anything", async (code, message, expected) => {
    const api = mockApi({
      ...signedOut,
      "POST /auth/reset-password/check": apiError(400, code, message),
    })
    window.history.replaceState(null, "", `/reset-password#token=${TOKEN}`)
    renderRoutes(routes, { route: "/reset-password" })

    expect(await screen.findByRole("heading", { name: /cannot be used/i })).toBeInTheDocument()
    expect(screen.getByText(expected)).toBeInTheDocument()
    expect(screen.queryByLabelText("New password")).not.toBeInTheDocument()
    expect(api.called("POST", "/auth/reset-password/check")[0]?.body).toEqual({ token: TOKEN })
  })

  it("still shows the form if the pre-check itself cannot be completed", async () => {
    mockApi({
      ...signedOut,
      "POST /auth/reset-password/check": {
        status: 500,
        body: { detail: "boom", code: "internal_error" },
      },
    })
    window.history.replaceState(null, "", `/reset-password#token=${TOKEN}`)
    renderRoutes(routes, { route: "/reset-password" })
    expect(await screen.findByLabelText("New password")).toBeInTheDocument() // the server re-checks on submit
  })

  it("reads the token from the URL fragment and removes it from the address bar", async () => {
    mockApi({ ...signedOut, ...linkOk })
    window.history.replaceState(null, "", `/reset-password#token=${TOKEN}`)
    renderRoutes(routes, { route: "/reset-password" })
    await screen.findByLabelText("New password")
    await waitFor(() => expect(window.location.hash).toBe(""))
  })

  it("validates the new password and the confirmation", async () => {
    const api = mockApi({ ...signedOut, ...linkOk })
    window.history.replaceState(null, "", `/reset-password#token=${TOKEN}`)
    renderRoutes(routes, { route: "/reset-password" })
    await fill("short1")
    expect(await screen.findByText("Use at least 10 characters.")).toBeInTheDocument()

    const user = userEvent.setup()
    await user.clear(screen.getByLabelText("New password"))
    await user.type(screen.getByLabelText("New password"), "Another-Secret-77")
    await user.clear(screen.getByLabelText("Confirm new password"))
    await user.type(screen.getByLabelText("Confirm new password"), "Different-Pass-1")
    await user.click(screen.getByRole("button", { name: /update password/i }))
    expect(await screen.findByText("Passwords do not match")).toBeInTheDocument()
    expect(api.called("POST", "/auth/reset-password")).toHaveLength(0)
  })

  it("sets the new password and sends the user to sign in", async () => {
    const api = mockApi({
      ...signedOut,
      ...linkOk,
      "POST /auth/reset-password": { body: { message: "Password updated." } },
    })
    window.history.replaceState(null, "", `/reset-password#token=${TOKEN}`)
    renderRoutes(routes, { route: "/reset-password" })
    await fill("Another-Secret-77")

    expect(await screen.findByRole("heading", { name: /password updated/i })).toBeInTheDocument()
    expect(api.called("POST", "/auth/reset-password")[0]?.body).toEqual({
      token: TOKEN,
      password: "Another-Secret-77",
    })
    expect(screen.getByRole("link", { name: /go to sign in/i })).toHaveAttribute("href", "/login")
  })

  it.each([
    ["token_expired", "This link has expired. Please request a new one.", /expired/i],
    ["token_used", "This link has already been used.", /already been used/i],
    ["invalid_token", "This link is invalid or has expired.", /invalid or has expired/i],
  ])("handles a %s link", async (code, message, expected) => {
    mockApi({ ...signedOut, ...linkOk, "POST /auth/reset-password": apiError(400, code, message) })
    window.history.replaceState(null, "", `/reset-password#token=${TOKEN}`)
    renderRoutes(routes, { route: "/reset-password" })
    await fill("Another-Secret-77")

    expect(await screen.findByRole("heading", { name: /cannot be used/i })).toBeInTheDocument()
    expect(screen.getByText(expected)).toBeInTheDocument()
    expect(screen.getByRole("link", { name: /request a new link/i })).toBeInTheDocument()
  })

  it("keeps the form (and the link) when the server rejects only the password", async () => {
    mockApi({
      ...signedOut,
      ...linkOk,
      "POST /auth/reset-password": apiError(422, "weak_password", "That password is too common."),
    })
    window.history.replaceState(null, "", `/reset-password#token=${TOKEN}`)
    renderRoutes(routes, { route: "/reset-password" })
    await fill("Another-Secret-77")
    expect(await screen.findByText("That password is too common.")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /update password/i })).toBeEnabled()
  })
})

describe("VerifyEmailPage", () => {
  it("verifies automatically, once, and offers to sign in", async () => {
    const api = mockApi({
      ...signedOut,
      "POST /auth/verify-email": { body: { message: "verified" } },
    })
    window.history.replaceState(null, "", `/verify-email#token=${TOKEN}`)
    renderRoutes(routes, { route: "/verify-email" })

    expect(await screen.findByText(/verifying your email/i)).toBeInTheDocument()
    expect(await screen.findByRole("heading", { name: /email verified/i })).toBeInTheDocument()
    expect(api.called("POST", "/auth/verify-email")).toHaveLength(1)
    expect(api.called("POST", "/auth/verify-email")[0]?.body).toEqual({ token: TOKEN })
    expect(window.location.hash).toBe("") // the secret is gone from the address bar
    expect(screen.getByRole("link", { name: /continue to sign in/i })).toHaveAttribute(
      "href",
      "/login",
    )
  })

  it("offers a fresh link when it has expired", async () => {
    const api = mockApi({
      ...signedOut,
      "POST /auth/verify-email": apiError(
        400,
        "token_expired",
        "This link has expired. Please request a new one.",
      ),
      "POST /auth/resend-verification": { status: 202, body: { message: "ok" } },
    })
    window.history.replaceState(null, "", `/verify-email#token=${TOKEN}`)
    renderRoutes(routes, { route: "/verify-email" })

    expect(await screen.findByRole("heading", { name: /link has expired/i })).toBeInTheDocument()
    const user = userEvent.setup()
    const send = screen.getByRole("button", { name: /send a new verification link/i })
    expect(send).toBeDisabled() // needs an email first
    await user.type(screen.getByLabelText(/email address/i), "alice@example.com")
    await user.click(send)
    await waitFor(() => expect(api.called("POST", "/auth/resend-verification")).toHaveLength(1))
    expect(api.called("POST", "/auth/resend-verification")[0]?.body).toEqual({
      email: "alice@example.com",
    })
  })

  it("tells people whose link was already used to just sign in", async () => {
    mockApi({
      ...signedOut,
      "POST /auth/verify-email": apiError(400, "token_used", "This link has already been used."),
    })
    window.history.replaceState(null, "", `/verify-email#token=${TOKEN}`)
    renderRoutes(routes, { route: "/verify-email" })
    expect(
      await screen.findByText(/already verified your email, you can just sign in/i),
    ).toBeInTheDocument()
  })

  it("fails clearly when there is no token", async () => {
    const api = mockApi(signedOut)
    renderRoutes(routes, { route: "/verify-email" })
    expect(await screen.findByRole("heading", { name: /verification failed/i })).toBeInTheDocument()
    expect(api.called("POST", "/auth/verify-email")).toHaveLength(0)
  })
})

describe("opening a second link in the same tab", () => {
  it("re-verifies instead of showing the previous result", async () => {
    let calls = 0
    const api = mockApi({
      ...signedOut,
      "POST /auth/verify-email": () => {
        calls += 1
        return calls === 1
          ? { body: { message: "verified" } }
          : apiError(400, "token_used", "This link has already been used.")
      },
    })
    window.history.replaceState(null, "", `/verify-email#token=${TOKEN}`)
    renderRoutes(routes, { route: "/verify-email" })
    await screen.findByRole("heading", { name: /email verified/i })

    // The same link pasted again: only the fragment changes, so the page does not reload.
    window.history.pushState(null, "", `/verify-email#token=${TOKEN}`)
    window.dispatchEvent(new HashChangeEvent("hashchange"))

    expect(await screen.findByText(/already been used/i)).toBeInTheDocument()
    expect(api.called("POST", "/auth/verify-email")).toHaveLength(2)
  })
})
