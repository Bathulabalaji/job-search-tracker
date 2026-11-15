import { fireEvent, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"

import { ProtectedRoute } from "@/features/auth/route-guards"
import { authResponse, mockApi } from "@/test/mock-api"
import { renderRoutes } from "@/test/render"
import { LogInteractionDialog } from "./log-interaction-dialog"

vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn(), info: vi.fn() } }))

function show() {
  return renderRoutes(
    [
      { path: "/login", element: <p>Login page</p> },
      {
        element: <ProtectedRoute />,
        children: [
          {
            path: "/a",
            element: <LogInteractionDialog open onOpenChange={() => undefined} opportunityId={5} />,
          },
        ],
      },
    ],
    { route: "/a" },
  )
}

afterEach(() => vi.restoreAllMocks())

describe("Log interaction dialog", () => {
  it("will not save without a summary", async () => {
    const api = mockApi({ "GET /auth/me": { body: authResponse() } })
    show()
    await userEvent.click(await screen.findByRole("button", { name: "Log interaction" }))
    expect(await screen.findByText("Say what happened")).toBeInTheDocument()
    expect(api.called("POST", "/interactions")).toHaveLength(0)
  })

  it("will not save a time in the future, and asks for one when it is cleared", async () => {
    const api = mockApi({ "GET /auth/me": { body: authResponse() } })
    show()
    await userEvent.type(await screen.findByLabelText("What happened?"), "Spoke to HR")
    const when = screen.getByLabelText("When")

    fireEvent.change(when, { target: { value: "2999-01-01T09:00" } })
    await userEvent.click(screen.getByRole("button", { name: "Log interaction" }))
    expect(await screen.findByText("That time is in the future")).toBeInTheDocument()

    fireEvent.change(when, { target: { value: "" } })
    await userEvent.click(screen.getByRole("button", { name: "Log interaction" }))
    expect(await screen.findByText("Pick when it happened")).toBeInTheDocument()
    expect(api.called("POST", "/interactions")).toHaveLength(0)
  })

  it("saves a trimmed summary with the chosen time", async () => {
    const api = mockApi({
      "GET /auth/me": { body: authResponse() },
      "POST /interactions": { status: 201, body: { id: 1 } },
    })
    show()
    await userEvent.type(await screen.findByLabelText("What happened?"), "  Spoke to HR  ")
    fireEvent.change(screen.getByLabelText("When"), { target: { value: "2026-11-10T09:30" } })
    await userEvent.click(screen.getByRole("button", { name: "Log interaction" }))

    await waitFor(() => expect(api.called("POST", "/interactions")).toHaveLength(1))
    const body = api.called("POST", "/interactions")[0]?.body as Record<string, unknown>
    expect(body.summary).toBe("Spoke to HR")
    expect(body.opportunity_id).toBe(5)
    expect(new Date(String(body.occurred_at)).getTime()).toBe(
      new Date("2026-11-10T09:30").getTime(),
    )
  })
})
