import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it } from "vitest"

import { PublicOnlyRoute } from "@/features/auth/route-guards"
import { apiError, mockApi } from "@/test/mock-api"
import { renderRoutes } from "@/test/render"
import { RegisterPage } from "./register-page"

const routes = [
  { element: <PublicOnlyRoute />, children: [{ path: "/register", element: <RegisterPage /> }] },
  { path: "/login", element: <p>Login page</p> },
]
const signedOut = { "GET /auth/me": apiError(401, "not_authenticated", "Please sign in.") }

interface Fill {
  name?: string
  email?: string
  password?: string
  confirm?: string
  terms?: boolean
}

async function fillForm({
  name = "Alice Walker",
  email = "alice@example.com",
  password = "Correct-Horse-9",
  confirm = password,
  terms = true,
}: Fill = {}) {
  const user = userEvent.setup()
  await user.type(await screen.findByLabelText(/full name/i), name)
  await user.type(screen.getByLabelText(/^email/i), email)
  await user.type(screen.getByLabelText("Password"), password)
  await user.type(screen.getByLabelText(/confirm password/i), confirm)
  if (terms) await user.click(screen.getByRole("checkbox"))
  await user.click(screen.getByRole("button", { name: /create account/i }))
  return user
}

describe("RegisterPage", () => {
  it("validates every field on the client", async () => {
    const api = mockApi(signedOut)
    renderRoutes(routes, { route: "/register" })
    const user = userEvent.setup()
    await user.click(await screen.findByRole("button", { name: /create account/i }))

    expect(await screen.findByText("Enter your full name")).toBeInTheDocument()
    expect(screen.getByText("Enter your email address")).toBeInTheDocument()
    expect(screen.getByText("Choose a password")).toBeInTheDocument()
    expect(screen.getByText("Confirm your password")).toBeInTheDocument()
    expect(screen.getByText(/must accept the terms/i)).toBeInTheDocument()
    expect(api.called("POST", "/auth/register")).toHaveLength(0)
  })

  it("rejects weak passwords with a reason", async () => {
    const api = mockApi(signedOut)
    renderRoutes(routes, { route: "/register" })
    await fillForm({ password: "short1" })
    expect(await screen.findByText("Use at least 10 characters.")).toBeInTheDocument()
    expect(api.called("POST", "/auth/register")).toHaveLength(0)
  })

  it("rejects a password that contains the person's name", async () => {
    mockApi(signedOut)
    renderRoutes(routes, { route: "/register" })
    await fillForm({ password: "Walker-secret-99" })
    expect(await screen.findByText(/do not include your name/i)).toBeInTheDocument()
  })

  it("requires the two passwords to match", async () => {
    const api = mockApi(signedOut)
    renderRoutes(routes, { route: "/register" })
    await fillForm({ confirm: "Different-Pass-1" })
    expect(await screen.findByText("Passwords do not match")).toBeInTheDocument()
    expect(api.called("POST", "/auth/register")).toHaveLength(0)
  })

  it("requires accepting the terms", async () => {
    const api = mockApi(signedOut)
    renderRoutes(routes, { route: "/register" })
    await fillForm({ terms: false })
    expect(await screen.findByText(/must accept the terms/i)).toBeInTheDocument()
    expect(api.called("POST", "/auth/register")).toHaveLength(0)
  })

  it("shows a live checklist while typing a password", async () => {
    mockApi(signedOut)
    renderRoutes(routes, { route: "/register" })
    const user = userEvent.setup()
    await user.type(await screen.findByLabelText(/^password/i), "abc")
    const list = screen.getByRole("list", { name: /password requirements/i })
    expect(list).toHaveTextContent("At least 10 characters")
    expect(list).toHaveTextContent("not met yet")
    await user.type(screen.getByLabelText("Password"), "defghij1")
    expect(list).not.toHaveTextContent("not met yet")
  })

  it("creates the account and tells the user to check their email", async () => {
    const api = mockApi({
      ...signedOut,
      "POST /auth/register": { status: 201, body: { message: "Account created." } },
    })
    renderRoutes(routes, { route: "/register" })
    await fillForm()

    expect(await screen.findByRole("heading", { name: /check your email/i })).toBeInTheDocument()
    expect(screen.getByText("alice@example.com")).toBeInTheDocument()
    expect(api.called("POST", "/auth/register")[0]?.body).toEqual({
      full_name: "Alice Walker",
      email: "alice@example.com",
      password: "Correct-Horse-9",
      accept_terms: true,
    })
    // The page must not pretend the user is signed in.
    expect(screen.queryByText(/welcome back/i)).not.toBeInTheDocument()
  })

  it("makes the user wait before asking for another email, then sends it", async () => {
    const api = mockApi({
      ...signedOut,
      "POST /auth/register": { status: 201, body: { message: "ok" } },
      "POST /auth/resend-verification": { status: 202, body: { message: "ok" } },
    })
    renderRoutes(routes, { route: "/register" })
    await fillForm()
    const button = await screen.findByRole("button", { name: /resend email in \d+s/i })
    expect(button).toBeDisabled()
    expect(api.called("POST", "/auth/resend-verification")).toHaveLength(0)
  })

  it("points an existing user to sign in when the email is taken", async () => {
    mockApi({
      ...signedOut,
      "POST /auth/register": apiError(
        409,
        "email_taken",
        "An account with this email already exists.",
      ),
    })
    renderRoutes(routes, { route: "/register" })
    await fillForm()
    expect(await screen.findByText(/already exists/i)).toBeInTheDocument()
    expect(screen.queryByRole("heading", { name: /check your email/i })).not.toBeInTheDocument()
  })

  it("shows the server's password rule when it disagrees with the client", async () => {
    mockApi({
      ...signedOut,
      "POST /auth/register": apiError(422, "weak_password", "That password is too common."),
    })
    renderRoutes(routes, { route: "/register" })
    await fillForm()
    expect(await screen.findByText("That password is too common.")).toBeInTheDocument()
  })

  it("shows rate limiting and generic failures as an alert", async () => {
    mockApi({
      ...signedOut,
      "POST /auth/register": apiError(429, "rate_limited", "Too many attempts.", {
        "Retry-After": "3000",
      }),
    })
    renderRoutes(routes, { route: "/register" })
    await fillForm()
    expect(await screen.findByRole("alert")).toHaveTextContent(/about 50 minutes/i)
  })

  it("keeps the submit button disabled while the request runs", async () => {
    let release: () => void = () => {}
    mockApi({
      ...signedOut,
      "POST /auth/register": () =>
        new Promise((resolve) => {
          release = () => resolve({ status: 201, body: { message: "ok" } })
        }),
    })
    renderRoutes(routes, { route: "/register" })
    await fillForm()
    expect(await screen.findByRole("button", { name: /creating account/i })).toBeDisabled()
    release()
    await waitFor(() =>
      expect(screen.getByRole("heading", { name: /check your email/i })).toBeInTheDocument(),
    )
  })
})
