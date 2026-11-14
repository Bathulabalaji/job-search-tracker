import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import { ProtectedRoute } from "@/features/auth/route-guards"
import { authResponse, mockApi } from "@/test/mock-api"
import { renderRoutes } from "@/test/render"
import { AssistantPrivacyCard } from "./assistant-privacy-card"

const toasts = vi.hoisted(() => ({ error: vi.fn(), success: vi.fn(), info: vi.fn() }))
vi.mock("sonner", () => ({ toast: toasts }))

const routes = [
  { path: "/login", element: <p>Login page</p> },
  { element: <ProtectedRoute />, children: [{ path: "/a", element: <AssistantPrivacyCard /> }] },
]

const ON = { enabled: true, assistant_opt_out: false }
const USAGE = [
  { name: "messages", label: "Assistant messages", limit: 60, used: 12, resets_at: null },
  { name: "matches", label: "Resume comparisons", limit: 20, used: 0, resets_at: null },
]

describe("Assistant privacy card", () => {
  it("shows what is sent, today's allowances, and turns the assistant off", async () => {
    let optedOut = false
    const api = mockApi({
      "GET /auth/me": { body: authResponse() },
      "GET /chat/config": () => ({ body: { enabled: !optedOut, assistant_opt_out: optedOut } }),
      "GET /chat/usage": { body: USAGE },
      "PUT /chat/preferences": () => {
        optedOut = true
        return { body: { enabled: false, assistant_opt_out: true } }
      },
    })
    renderRoutes(routes, { route: "/a" })
    expect(await screen.findByText(/Groq and\s+Google/)).toBeInTheDocument()
    const list = await screen.findByRole("list", { name: "Today's allowances" })
    expect(list).toHaveTextContent("12/60")

    await userEvent.setup().click(screen.getByRole("button", { name: "Turn the assistant off" }))
    await waitFor(() => expect(api.called("PUT", "/chat/preferences")).toHaveLength(1))
    expect(api.called("PUT", "/chat/preferences")[0]?.body).toEqual({ assistant_opt_out: true })
    expect(await screen.findByRole("status")).toHaveTextContent("The assistant is off")
    expect(screen.getByRole("button", { name: "Turn the assistant on" })).toBeInTheDocument()
    expect(screen.queryByRole("list", { name: "Today's allowances" })).not.toBeInTheDocument()
  })

  it("is hidden when the server has no assistant", async () => {
    mockApi({
      "GET /auth/me": { body: authResponse() },
      "GET /chat/config": { body: { enabled: false } },
      "GET /chat/usage": { body: [] },
    })
    renderRoutes(routes, { route: "/a" })
    await waitFor(() => expect(screen.queryByText("AI assistant")).not.toBeInTheDocument())
  })

  it("keeps working when the config says the assistant is on", async () => {
    mockApi({
      "GET /auth/me": { body: authResponse() },
      "GET /chat/config": { body: ON },
      "GET /chat/usage": { body: [] },
    })
    renderRoutes(routes, { route: "/a" })
    expect(
      await screen.findByRole("button", { name: "Turn the assistant off" }),
    ).toBeInTheDocument()
  })
})
