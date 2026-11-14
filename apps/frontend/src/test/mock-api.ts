import { vi } from "vitest"

import type { AuthResponse, AuthUser } from "@/api/auth"

export interface RecordedCall {
  method: string
  path: string
  body: unknown
  headers: Record<string, string>
  credentials: RequestCredentials | undefined
}

type Reply = {
  status?: number
  body?: unknown
  headers?: Record<string, string>
  /** A raw text body (for example a server-sent event stream), sent as-is. */
  raw?: string
}
type Handler = Reply | ((call: RecordedCall) => Reply | Promise<Reply>)

/**
 * A fake backend for fetch. Routes are "METHOD /path" (the API base is stripped).
 * Unmatched requests fail the test loudly instead of silently returning nothing.
 */
export function mockApi(routes: Record<string, Handler>) {
  const calls: RecordedCall[] = []
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(typeof input === "string" ? input : input.toString())
    const path = url.pathname.replace(/^\/api\/v1/, "")
    const method = (init?.method ?? "GET").toUpperCase()
    const call: RecordedCall = {
      method,
      path,
      body:
        typeof init?.body === "string"
          ? (JSON.parse(init.body) as unknown)
          : init?.body instanceof FormData
            ? Object.fromEntries(init.body.entries())
            : undefined,
      headers: (init?.headers ?? {}) as Record<string, string>,
      credentials: init?.credentials,
    }
    calls.push(call)
    const handler = routes[`${method} ${path}`]
    if (!handler) throw new Error(`Unmocked request: ${method} ${path}`)
    const reply = await (typeof handler === "function" ? handler(call) : handler)
    const status = reply.status ?? 200
    if (reply.raw !== undefined) {
      return new Response(reply.raw, {
        status,
        headers: { "Content-Type": "text/event-stream", ...reply.headers },
      })
    }
    return new Response(status === 204 ? null : JSON.stringify(reply.body ?? {}), {
      status,
      headers: { "Content-Type": "application/json", ...reply.headers },
    })
  })
  vi.stubGlobal("fetch", fetchMock)
  return {
    calls,
    fetchMock,
    called: (method: string, path: string) =>
      calls.filter((c) => c.method === method && c.path === path),
  }
}

export function makeUser(overrides: Partial<AuthUser> = {}): AuthUser {
  return {
    id: 1,
    email: "alice@example.com",
    full_name: "Alice Walker",
    status: "active",
    email_verified: true,
    has_password: true,
    google_linked: false,
    created_at: "2026-11-01T10:00:00Z",
    last_login_at: null,
    ...overrides,
  }
}

export function authResponse(overrides: Partial<AuthResponse> = {}): AuthResponse {
  return { user: makeUser(), csrf_token: "csrf-abc", is_new_user: false, ...overrides }
}

export const apiError = (
  status: number,
  code: string,
  detail: string,
  headers?: Record<string, string>,
) => ({ status, body: { detail, code }, headers }) satisfies Reply
