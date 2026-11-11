import { ApiError, describeDetail, request, retryMessage, setAuthHooks, setSessionToken } from "./client"

type FetchMock = jest.Mock<Promise<Response>, [string, RequestInit]>

function respond(status: number, body?: unknown, headers: Record<string, string> = {}): Response {
  return new Response(body === undefined ? null : JSON.stringify(body), { status, headers })
}

let fetchMock: FetchMock

beforeEach(() => {
  fetchMock = jest.fn()
  global.fetch = fetchMock as unknown as typeof fetch
  setSessionToken(null)
  setAuthHooks(null)
})

describe("request", () => {
  it("identifies as a mobile client and sends the bearer token", async () => {
    setSessionToken("tok-123")
    fetchMock.mockResolvedValue(respond(200, [{ id: 1 }]))
    await request("/opportunities", { params: { q: "acme", priority: undefined } })
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toMatch(/\/opportunities\?q=acme$/)
    const headers = init.headers as Record<string, string>
    expect(headers.Authorization).toBe("Bearer tok-123")
    expect(headers["X-Client-Type"]).toBe("mobile")
  })

  it("sends no Authorization header when signed out", async () => {
    fetchMock.mockResolvedValue(respond(200, {}))
    await request("/auth/google/nonce")
    const headers = (fetchMock.mock.calls[0]?.[1] as RequestInit).headers as Record<string, string>
    expect(headers.Authorization).toBeUndefined()
  })

  it("serialises a JSON body", async () => {
    fetchMock.mockResolvedValue(respond(201, { id: 1 }))
    await request("/opportunities", { method: "POST", body: { company: "Acme" } })
    const init = fetchMock.mock.calls[0]?.[1] as RequestInit
    expect(init.method).toBe("POST")
    expect(init.body).toBe('{"company":"Acme"}')
    expect((init.headers as Record<string, string>)["Content-Type"]).toBe("application/json")
  })

  it("returns undefined for 204", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }))
    await expect(request("/auth/logout", { method: "POST" })).resolves.toBeUndefined()
  })

  it("turns an API error into ApiError with the stable code", async () => {
    fetchMock.mockResolvedValue(respond(403, { detail: "Verify your email.", code: "email_not_verified" }))
    await expect(request("/auth/login", { method: "POST", body: {} })).rejects.toMatchObject({
      status: 403,
      code: "email_not_verified",
      message: "Verify your email.",
    })
  })

  it("reports a network failure as status 0 with a friendly message", async () => {
    fetchMock.mockRejectedValue(new TypeError("Network request failed"))
    const error = await request("/opportunities").catch((e: unknown) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(0)
    expect((error as ApiError).message).toMatch(/can't reach the server/i)
  })

  it("signals session expiry on 401 from a normal endpoint", async () => {
    const onSessionExpired = jest.fn()
    setAuthHooks({ onSessionExpired })
    fetchMock.mockResolvedValue(respond(401, { detail: "Please sign in.", code: "not_authenticated" }))
    await expect(request("/opportunities")).rejects.toBeInstanceOf(ApiError)
    expect(onSessionExpired).toHaveBeenCalledTimes(1)
  })

  it.each(["/auth/login", "/auth/google", "/auth/me", "/auth/register"])(
    "does not treat a 401 from %s as an expired session",
    async (path) => {
      const onSessionExpired = jest.fn()
      setAuthHooks({ onSessionExpired })
      fetchMock.mockResolvedValue(respond(401, { detail: "Wrong.", code: "invalid_credentials" }))
      await expect(request(path, { method: "POST", body: {} })).rejects.toBeInstanceOf(ApiError)
      expect(onSessionExpired).not.toHaveBeenCalled()
    },
  )

  it("reads Retry-After on rate limiting", async () => {
    fetchMock.mockResolvedValue(respond(429, { detail: "Too many attempts." }, { "Retry-After": "600" }))
    const error = (await request("/auth/login", { method: "POST", body: {} }).catch((e: unknown) => e)) as ApiError
    expect(error.retryAfterSeconds).toBe(600)
    expect(retryMessage(error)).toBe("Too many attempts. Try again in about 10 minutes.")
  })
})

describe("describeDetail", () => {
  it("joins validation errors and strips pydantic prefixes", () => {
    expect(
      describeDetail([
        { loc: ["body", "company"], msg: "Field required" },
        { loc: ["body", "fit_score"], msg: "Value error, Must be 0-100" },
      ]),
    ).toBe("company: Field required; fit_score: Must be 0-100")
  })
  it("passes strings through", () => expect(describeDetail("Nope")).toBe("Nope"))
})
