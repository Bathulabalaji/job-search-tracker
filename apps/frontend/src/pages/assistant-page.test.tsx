import { screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it } from "vitest"

import type { ChatMessage, ConversationDetail, PendingAction } from "@/api/chat"
import { ProtectedRoute } from "@/features/auth/route-guards"
import { apiError, authResponse, mockApi } from "@/test/mock-api"
import { renderRoutes } from "@/test/render"
import { AssistantPage } from "./assistant-page"

const routes = [
  { path: "/login", element: <p>Login page</p> },
  { element: <ProtectedRoute />, children: [{ path: "/assistant", element: <AssistantPage /> }] },
]

const config = {
  enabled: true,
  messages_per_day: { limit: 60, used: 3 },
  max_message_chars: 2000,
  suggestions: ["What's due today?"],
}
const conversation = {
  id: 7,
  title: "What's due today?",
  status: "active" as const,
  last_message_at: "2026-11-13T10:00:00Z",
  created_at: "2026-11-13T10:00:00Z",
}

function sse(events: [string, object][]): string {
  return events
    .map(([e, d], i) => `id: ${i + 1}\nevent: ${e}\ndata: ${JSON.stringify(d)}\n\n`)
    .join("")
}

function message(overrides: Partial<ChatMessage>): ChatMessage {
  return {
    id: 1,
    seq: 1,
    role: "user",
    content: "",
    tool_calls: null,
    status: "complete",
    error_code: null,
    model: null,
    run_id: "run-1",
    created_at: "2026-11-13T10:00:00Z",
    ...overrides,
  }
}

describe("AssistantPage", () => {
  it("starts a conversation from a suggestion and streams the reply with tool activity", async () => {
    let saved = false
    const detail = (): ConversationDetail => ({
      conversation,
      messages: saved
        ? [
            message({ id: 1, content: "What's due today?" }),
            message({
              id: 2,
              seq: 2,
              role: "assistant",
              content: "You have **2 follow-ups** due.",
              tool_calls: [{ name: "get_today", ok: true, summary: "2 follow-ups" }],
            }),
          ]
        : [],
      last_run: null,
      pending_action: null,
    })
    const api = mockApi({
      "GET /auth/me": { body: authResponse() },
      "GET /chat/config": { body: config },
      "GET /chat/conversations": { body: [] },
      "POST /chat/conversations": { status: 201, body: conversation },
      "GET /chat/conversations/7": () => ({ body: detail() }),
      "POST /chat/conversations/7/messages": () => {
        saved = true
        return {
          raw: sse([
            ["run_started", { run_id: "run-1" }],
            ["tool_start", { id: "t1", name: "get_today" }],
            ["tool_end", { id: "t1", name: "get_today", ok: true, summary: "2 follow-ups" }],
            ["token", { delta: "You have **2 follow-ups** " }],
            ["token", { delta: "due." }],
            ["done", { status: "completed" }],
          ]),
        }
      },
    })
    renderRoutes(routes, { route: "/assistant" })
    const user = userEvent.setup()

    await user.click(await screen.findByRole("button", { name: "What's due today?" }))

    const panel = await screen.findByRole("region", { name: "Assistant" })
    expect(await within(panel).findByText("Today's plan")).toBeInTheDocument()
    await waitFor(() =>
      expect(within(panel).getByText("2 follow-ups", { selector: "strong" })).toBeInTheDocument(),
    )
    expect(within(panel).getByText("What's due today?", { selector: "div" })).toBeInTheDocument()
    const [send] = api.called("POST", "/chat/conversations/7/messages")
    expect(send?.body).toMatchObject({ content: "What's due today?" })
    expect(send?.headers["X-CSRF-Token"]).toBe("csrf-abc")
    expect(send?.headers.Accept).toBe("text/event-stream")
  })

  it("shows a capacity error with Retry, and Retry resumes the same run", async () => {
    let resumed = false
    const failed: ConversationDetail = {
      conversation,
      messages: [
        message({ id: 1, content: "Summarise my pipeline" }),
        message({
          id: 2,
          seq: 2,
          role: "assistant",
          status: "failed",
          error_code: "assistant_capacity",
          content: "I'm at capacity right now (free-tier limits).",
        }),
      ],
      last_run: {
        id: "run-1",
        status: "failed",
        error_code: "assistant_capacity",
        model_switches: 3,
        started_at: "2026-11-13T10:00:00Z",
        finished_at: "2026-11-13T10:00:05Z",
        resumable: true,
      },
      pending_action: null,
    }
    const api = mockApi({
      "GET /auth/me": { body: authResponse() },
      "GET /chat/config": { body: config },
      "GET /chat/conversations": { body: [conversation] },
      "GET /chat/conversations/7": () => ({
        body: resumed
          ? {
              ...failed,
              messages: [
                failed.messages[0],
                { ...failed.messages[1], status: "complete", content: "All good now." },
              ],
              last_run: { ...failed.last_run, status: "completed", resumable: false },
            }
          : failed,
      }),
      "POST /chat/conversations/7/runs/run-1/resume": () => {
        resumed = true
        return {
          raw: sse([
            ["token", { delta: "All good now." }],
            ["done", { status: "completed" }],
          ]),
        }
      },
    })
    renderRoutes(routes, { route: "/assistant?c=7" })
    const user = userEvent.setup()

    const panel = await screen.findByRole("region", { name: "Assistant" })
    expect(await within(panel).findByText(/at capacity/)).toBeInTheDocument()
    await user.click(within(panel).getByRole("button", { name: /retry/i }))

    expect(await within(panel).findByText("All good now.")).toBeInTheDocument()
    expect(api.called("POST", "/chat/conversations/7/runs/run-1/resume")).toHaveLength(1)
    expect(within(panel).queryByText(/at capacity/)).not.toBeInTheDocument()
  })

  it("puts the text back and explains when the server refuses the message", async () => {
    mockApi({
      "GET /auth/me": { body: authResponse() },
      "GET /chat/config": { body: config },
      "GET /chat/conversations": { body: [conversation] },
      "GET /chat/conversations/7": {
        body: { conversation, messages: [], last_run: null, pending_action: null },
      },
      "POST /chat/conversations/7/messages": apiError(
        429,
        "chat_quota",
        "You're sending messages quickly.",
        {
          "Retry-After": "40",
        },
      ),
    })
    renderRoutes(routes, { route: "/assistant?c=7" })
    const user = userEvent.setup()
    const box = await screen.findByRole("textbox", { name: "Message" })
    await user.type(box, "hello there{Enter}")
    expect(await screen.findByText(/sending messages quickly/)).toBeInTheDocument()
    expect(box).toHaveValue("hello there")
  })

  it("explains when the assistant is not enabled", async () => {
    mockApi({
      "GET /auth/me": { body: authResponse() },
      "GET /chat/config": { body: { ...config, enabled: false } },
    })
    renderRoutes(routes, { route: "/assistant" })
    expect(await screen.findByText("The assistant isn't switched on")).toBeInTheDocument()
  })
})

describe("AssistantPage confirmation cards", () => {
  const pending: PendingAction = {
    id: "act-1",
    run_id: "run-1",
    tool: "move_opportunity",
    title: "Move Zepto — Backend Engineer",
    summary: "found → applied",
    fields: [
      {
        name: "stage",
        label: "New stage",
        value: "applied",
        editable: true,
        type: "select",
        options: ["found", "applied", "screening"],
      },
      { name: "note", label: "Note", value: null, editable: true, type: "text", options: null },
    ],
    status: "pending",
    expires_at: "2026-11-13T10:15:00Z",
    created_at: "2026-11-13T10:00:00Z",
    result_summary: null,
    error: null,
    warning: null,
  }
  const awaiting = (): ConversationDetail => ({
    conversation,
    messages: [
      message({ id: 1, content: "Move Zepto to applied" }),
      message({
        id: 2,
        seq: 2,
        role: "assistant",
        status: "awaiting",
        content: "Sure, moving it.",
      }),
    ],
    last_run: {
      id: "run-1",
      status: "awaiting_confirmation",
      error_code: null,
      model_switches: 0,
      started_at: "2026-11-13T10:00:00Z",
      finished_at: null,
      resumable: false,
    },
    pending_action: { ...pending, fields: [...pending.fields] },
  })

  it("shows the card and confirms with edits, then the reply continues", async () => {
    let decided = false
    const api = mockApi({
      "GET /auth/me": { body: authResponse() },
      "GET /chat/config": { body: config },
      "GET /chat/conversations": { body: [conversation] },
      "GET /chat/conversations/7": () =>
        decided
          ? {
              body: {
                ...awaiting(),
                messages: [
                  awaiting().messages[0],
                  {
                    ...awaiting().messages[1],
                    status: "complete",
                    content: "Sure, moving it.\n\nDone.",
                  },
                ],
                last_run: { ...awaiting().last_run, status: "completed" },
                pending_action: null,
              },
            }
          : { body: awaiting() },
      "POST /chat/conversations/7/actions/act-1": () => {
        decided = true
        return {
          raw: sse([
            [
              "tool_end",
              {
                id: "w1",
                name: "move_opportunity",
                ok: true,
                summary: "found → screening",
                changed: ["opportunities"],
              },
            ],
            ["token", { delta: "Done." }],
            ["done", { status: "completed", changed: ["opportunities"] }],
          ]),
        }
      },
    })
    renderRoutes(routes, { route: "/assistant?c=7" })
    const user = userEvent.setup()

    const card = await screen.findByRole("region", { name: "Confirm this change" })
    expect(within(card).getByText("Move Zepto — Backend Engineer")).toBeInTheDocument()
    expect(screen.getByRole("textbox", { name: "Message" })).toHaveAttribute(
      "placeholder",
      expect.stringMatching(/confirm or decline/i),
    )
    await user.selectOptions(within(card).getByLabelText("New stage"), "screening")
    await user.click(within(card).getByRole("button", { name: /confirm/i }))

    const panel = await screen.findByRole("region", { name: "Assistant" })
    expect(await within(panel).findByText("Done.")).toBeInTheDocument()
    const [call] = api.called("POST", "/chat/conversations/7/actions/act-1")
    expect(call?.body).toEqual({ decision: "confirm", edits: { stage: "screening" } })
    await waitFor(() =>
      expect(screen.queryByRole("region", { name: "Confirm this change" })).not.toBeInTheDocument(),
    )
  })

  it("declines without edits", async () => {
    let decided = false
    const api = mockApi({
      "GET /auth/me": { body: authResponse() },
      "GET /chat/config": { body: config },
      "GET /chat/conversations": { body: [conversation] },
      "GET /chat/conversations/7": () =>
        decided
          ? {
              body: {
                ...awaiting(),
                messages: [
                  awaiting().messages[0],
                  { ...awaiting().messages[1], status: "complete", content: "Okay, left as is." },
                ],
                last_run: { ...awaiting().last_run, status: "completed" },
                pending_action: null,
              },
            }
          : { body: awaiting() },
      "POST /chat/conversations/7/actions/act-1": () => {
        decided = true
        return {
          raw: sse([
            [
              "tool_end",
              { id: "w1", name: "move_opportunity", ok: false, summary: "declined", changed: [] },
            ],
            ["token", { delta: "Okay, left as is." }],
            ["done", { status: "completed", changed: [] }],
          ]),
        }
      },
    })
    renderRoutes(routes, { route: "/assistant?c=7" })
    const user = userEvent.setup()
    const card = await screen.findByRole("region", { name: "Confirm this change" })
    await user.click(within(card).getByRole("button", { name: /decline/i }))
    expect(await screen.findByText("Okay, left as is.")).toBeInTheDocument()
    expect(api.called("POST", "/chat/conversations/7/actions/act-1")[0]?.body).toEqual({
      decision: "reject",
    })
  })
})
