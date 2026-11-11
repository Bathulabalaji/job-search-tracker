import { describe, expect, it, vi } from "vitest"

import { ApiError, request, retryMessage, setAuthHooks } from "@/api/client"
import { setCsrfToken } from "@/lib/csrf"
import { apiError, mockApi } from "@/test/mock-api"

describe("request", () => {
  it("always sends the session cookie", async () => {
    const api = mockApi({ "GET /things": { body: [] } })
    await request("/things")
    expect(api.calls[0]?.credentials).toBe("include")
  })

  it("adds the CSRF header to state-changing requests only", async () => {
    setCsrfToken("csrf-123")
    const api = mockApi({
      "GET /things": { body: [] },
      "POST /things": { body: {} },
      "DELETE /things/1": { status: 204 },
    })
    await request("/things")
    await request("/things", { method: "POST", body: { a: 1 } })
    await request("/things/1", { method: "DELETE" })

    expect(api.calls[0]?.headers["X-CSRF-Token"]).toBeUndefined()
    expect(api.calls[1]?.headers["X-CSRF-Token"]).toBe("csrf-123")
    expect(api.calls[2]?.headers["X-CSRF-Token"]).toBe("csrf-123")
  })

  it("sends JSON bodies and parses JSON replies", async () => {
    const api = mockApi({ "POST /things": { body: { id: 7 } } })
    const result = await request<{ id: number }>("/things", { method: "POST", body: { name: "x" } })
    expect(result.id).toBe(7)
    expect(api.calls[0]?.body).toEqual({ name: "x" })
    expect(api.calls[0]?.headers["Content-Type"]).toBe("application/json")
  })

  it("turns an API error into an ApiError with its code and Retry-After", async () => {
    mockApi({
      "POST /auth/login": apiError(429, "rate_limited", "Too many attempts.", {
        "Retry-After": "120",
      }),
    })
    const error = await request("/auth/login", { method: "POST", body: {} }).catch(
      (e: unknown) => e,
    )
    expect(error).toBeInstanceOf(ApiError)
    const api = error as ApiError
    expect(api.status).toBe(429)
    expect(api.code).toBe("rate_limited")
    expect(api.retryAfterSeconds).toBe(120)
    expect(retryMessage(api)).toContain("about 2 minutes")
  })

  it("flattens validation errors into readable text", async () => {
    mockApi({
      "POST /auth/register": {
        status: 422,
        body: {
          detail: [{ loc: ["body", "email"], msg: "Value error, Enter a valid email address" }],
        },
      },
    })
    const error = (await request("/auth/register", { method: "POST", body: {} }).catch(
      (e: unknown) => e,
    )) as ApiError
    expect(error.message).toBe("email: Enter a valid email address")
  })

  it("reports an unreachable server clearly", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")))
    await expect(request("/things")).rejects.toMatchObject({ status: 0 })
  })

  it("never puts the CSRF token in the URL or body", async () => {
    setCsrfToken("csrf-secret")
    const api = mockApi({ "POST /things": { body: {} } })
    await request("/things", { method: "POST", body: { a: 1 } })
    expect(JSON.stringify(api.calls[0]?.body)).not.toContain("csrf-secret")
    expect(api.calls[0]?.path).not.toContain("csrf-secret")
  })
})

describe("session handling", () => {
  it("tells the app when a signed-in request finds the session gone", async () => {
    const onSessionExpired = vi.fn()
    setAuthHooks({ onSessionExpired, refreshCsrf: vi.fn() })
    mockApi({ "GET /opportunities": apiError(401, "not_authenticated", "Please sign in.") })

    await expect(request("/opportunities")).rejects.toBeInstanceOf(ApiError)
    expect(onSessionExpired).toHaveBeenCalledTimes(1)
  })

  it("does not treat a wrong password as an expired session", async () => {
    const onSessionExpired = vi.fn()
    setAuthHooks({ onSessionExpired, refreshCsrf: vi.fn() })
    mockApi({
      "POST /auth/login": apiError(401, "invalid_credentials", "Invalid email or password."),
    })

    await expect(request("/auth/login", { method: "POST", body: {} })).rejects.toBeInstanceOf(
      ApiError,
    )
    expect(onSessionExpired).not.toHaveBeenCalled()
  })

  it("refreshes a stale CSRF token and retries once", async () => {
    setCsrfToken("stale")
    const refreshCsrf = vi.fn(async () => {
      setCsrfToken("fresh")
      return true
    })
    setAuthHooks({ onSessionExpired: vi.fn(), refreshCsrf })
    let attempts = 0
    const api = mockApi({
      "POST /opportunities": () => {
        attempts += 1
        return attempts === 1
          ? apiError(403, "csrf_failed", "Security check failed.")
          : { status: 201, body: { id: 1 } }
      },
    })

    const result = await request<{ id: number }>("/opportunities", { method: "POST", body: {} })

    expect(result.id).toBe(1)
    expect(refreshCsrf).toHaveBeenCalledTimes(1)
    expect(api.calls.map((c) => c.headers["X-CSRF-Token"])).toEqual(["stale", "fresh"])
  })

  it("does not retry forever when the token stays wrong", async () => {
    setAuthHooks({ onSessionExpired: vi.fn(), refreshCsrf: vi.fn(async () => true) })
    const api = mockApi({ "POST /x": apiError(403, "csrf_failed", "Security check failed.") })
    await expect(request("/x", { method: "POST", body: {} })).rejects.toMatchObject({
      code: "csrf_failed",
    })
    expect(api.calls).toHaveLength(2) // the original plus exactly one retry
  })
})
