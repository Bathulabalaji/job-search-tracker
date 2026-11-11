import { API_BASE_URL } from "@/config/env"

export class ApiError extends Error {
  readonly status: number
  /** Stable machine-readable reason from the API (for example "email_not_verified"). */
  readonly code: string | undefined
  readonly retryAfterSeconds: number | undefined

  constructor(status: number, message: string, code?: string, retryAfterSeconds?: number) {
    super(message)
    this.name = "ApiError"
    this.status = status
    this.code = code
    this.retryAfterSeconds = retryAfterSeconds
  }
}

interface ValidationItem {
  loc?: unknown
  msg?: unknown
}

export function describeDetail(detail: unknown): string {
  if (typeof detail === "string") return detail
  if (Array.isArray(detail)) {
    return detail
      .map((item: ValidationItem) => {
        const where = Array.isArray(item.loc) ? item.loc.slice(1).join(".") : ""
        const raw = typeof item.msg === "string" ? item.msg : "Invalid value"
        const msg = raw.replace(/^Value error, /, "")
        return where && !/^(body|query)$/.test(where) ? `${where}: ${msg}` : msg
      })
      .join("; ")
  }
  return "Request failed"
}

export type QueryParams = Record<string, string | number | undefined>

function toQueryString(params: QueryParams | undefined): string {
  if (!params) return ""
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") search.set(key, String(value))
  }
  const text = search.toString()
  return text ? `?${text}` : ""
}

interface AuthHooks {
  /** A signed-in request came back 401: the session is gone. */
  onSessionExpired: () => void
}

let hooks: AuthHooks | null = null
let sessionToken: string | null = null

export function setAuthHooks(value: AuthHooks | null): void {
  hooks = value
}

/** The bearer token sent with every request. Kept in memory; persisted by the auth provider. */
export function setSessionToken(token: string | null): void {
  sessionToken = token
}

/** 401 on these means "wrong credentials", not "your session expired". */
const PUBLIC_AUTH_PATHS = [
  "/auth/login",
  "/auth/register",
  "/auth/google",
  "/auth/verify-email",
  "/auth/resend-verification",
  "/auth/forgot-password",
  "/auth/reset-password",
  "/auth/me",
]

/** Free hosting can take ~50s to wake a sleeping server, so be patient before giving up. */
const TIMEOUT_MS = 60_000

interface RequestOptions {
  method?: string
  body?: unknown
  params?: QueryParams
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, params } = options
  const headers: Record<string, string> = {
    Accept: "application/json",
    // Tells the API to hand back a bearer token instead of setting a browser cookie.
    "X-Client-Type": "mobile",
  }
  if (body !== undefined) headers["Content-Type"] = "application/json"
  if (sessionToken) headers.Authorization = `Bearer ${sessionToken}`

  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS)
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}${toQueryString(params)}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal,
    })
  } catch {
    throw new ApiError(0, "Can't reach the server. Check your connection and try again.")
  } finally {
    clearTimeout(timer)
  }

  if (!response.ok) {
    let detail: unknown
    let code: unknown
    try {
      const data = (await response.json()) as { detail?: unknown; code?: unknown }
      detail = data.detail
      code = data.code
    } catch {
      detail = undefined
    }
    const retryHeader = Number(response.headers.get("Retry-After"))
    const error = new ApiError(
      response.status,
      describeDetail(detail),
      typeof code === "string" ? code : undefined,
      Number.isFinite(retryHeader) && retryHeader > 0 ? retryHeader : undefined,
    )
    if (error.status === 401 && !PUBLIC_AUTH_PATHS.some((p) => path.startsWith(p))) {
      hooks?.onSessionExpired()
    }
    throw error
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

/** "Try again in 5 minutes" style text for a rate-limited response. */
export function retryMessage(error: ApiError): string {
  const seconds = error.retryAfterSeconds
  if (!seconds) return error.message
  const minutes = Math.ceil(seconds / 60)
  return `${error.message} Try again in about ${minutes} minute${minutes === 1 ? "" : "s"}.`
}
