import { getCsrfToken } from "@/lib/csrf"
import { API_BASE_URL } from "@/lib/env"
import { createSseParser } from "@/lib/sse"

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

function describeDetail(detail: unknown): string {
  if (typeof detail === "string") return detail
  if (Array.isArray(detail)) {
    return detail
      .map((item: ValidationItem) => {
        const where = Array.isArray(item.loc) ? item.loc.slice(1).join(".") : ""
        const raw = typeof item.msg === "string" ? item.msg : "Invalid value"
        // Pydantic prefixes custom validator messages with "Value error, ".
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

/** Hooks the auth provider registers so the client can react to session problems. */
interface AuthHooks {
  /** A signed-in request came back 401: the session is gone. */
  onSessionExpired: () => void
  /** Re-fetch /auth/me to get a fresh CSRF token. Resolves true if it worked. */
  refreshCsrf: () => Promise<boolean>
}

let hooks: AuthHooks | null = null

export function setAuthHooks(value: AuthHooks | null): void {
  hooks = value
}

const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"])
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

interface RequestOptions {
  method?: string
  body?: unknown
  params?: QueryParams
}

async function errorFrom(response: Response): Promise<ApiError> {
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
  return new ApiError(
    response.status,
    describeDetail(detail),
    typeof code === "string" ? code : undefined,
    Number.isFinite(retryHeader) && retryHeader > 0 ? retryHeader : undefined,
  )
}

function reportSessionProblems(error: ApiError, path: string): void {
  if (error.status === 401 && !PUBLIC_AUTH_PATHS.some((p) => path.startsWith(p))) {
    hooks?.onSessionExpired()
  }
}

async function send<T>(path: string, options: RequestOptions, retriedCsrf: boolean): Promise<T> {
  const { method = "GET", body, params } = options
  const headers: Record<string, string> = {}
  if (body !== undefined) headers["Content-Type"] = "application/json"
  const csrf = getCsrfToken()
  if (!SAFE_METHODS.has(method) && csrf) headers["X-CSRF-Token"] = csrf

  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}${toQueryString(params)}`, {
      method,
      headers,
      // Send and accept the HttpOnly session cookie.
      credentials: "include",
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new ApiError(0, "Cannot reach the API. Is the backend running?")
  }

  if (!response.ok) {
    const error = await errorFrom(response)
    // A stale CSRF token (after a restart or a new session): refresh it once and retry.
    if (error.code === "csrf_failed" && !retriedCsrf && hooks && (await hooks.refreshCsrf())) {
      return send<T>(path, options, true)
    }
    reportSessionProblems(error, path)
    throw error
  }
  if (response.status === 204) return undefined as T
  // The backend's OpenAPI contract is the source of truth for T (see api/types.ts).
  return (await response.json()) as T
}

export function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  return send<T>(path, options, false)
}

/** "Try again in 5 minutes" style text for a rate-limited response. */
export function retryMessage(error: ApiError): string {
  const seconds = error.retryAfterSeconds
  if (!seconds) return error.message
  const minutes = Math.ceil(seconds / 60)
  return `${error.message} Try again in about ${minutes} minute${minutes === 1 ? "" : "s"}.`
}

/**
 * POST that answers with server-sent events (the assistant's reply). Calls `onEvent` with
 * each event's name and parsed JSON data until the stream ends. Errors before the stream
 * starts (409, 429, 503...) throw an ApiError, exactly like `request`.
 */
export async function streamRequest(
  path: string,
  body: unknown,
  onEvent: (event: string, data: unknown) => void,
  signal?: AbortSignal,
  retriedCsrf = false,
): Promise<void> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: "text/event-stream",
  }
  const csrf = getCsrfToken()
  if (csrf) headers["X-CSRF-Token"] = csrf
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: "POST",
      headers,
      credentials: "include",
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
    })
  } catch (error) {
    if (signal?.aborted) throw error
    throw new ApiError(0, "Cannot reach the API. Is the backend running?")
  }
  if (!response.ok) {
    const error = await errorFrom(response)
    if (error.code === "csrf_failed" && !retriedCsrf && hooks && (await hooks.refreshCsrf())) {
      return streamRequest(path, body, onEvent, signal, true)
    }
    reportSessionProblems(error, path)
    throw error
  }
  if (!response.body) throw new ApiError(0, "The server sent an empty response.")
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader()
  const feed = createSseParser((event, data) => {
    let parsed: unknown = null
    try {
      parsed = JSON.parse(data) as unknown
    } catch {
      parsed = data
    }
    onEvent(event, parsed)
  })
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    feed(value)
  }
}

/**
 * POST a file as multipart/form-data. The browser sets the Content-Type (with its boundary);
 * the CSRF token and cookie travel exactly as for `request`.
 */
export async function upload<T>(path: string, form: FormData, retriedCsrf = false): Promise<T> {
  const headers: Record<string, string> = {}
  const csrf = getCsrfToken()
  if (csrf) headers["X-CSRF-Token"] = csrf
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: "POST",
      headers,
      credentials: "include",
      body: form,
    })
  } catch {
    throw new ApiError(0, "Cannot reach the API. Is the backend running?")
  }
  if (!response.ok) {
    const error = await errorFrom(response)
    if (error.code === "csrf_failed" && !retriedCsrf && hooks && (await hooks.refreshCsrf())) {
      return upload<T>(path, form, true)
    }
    reportSessionProblems(error, path)
    throw error
  }
  return (await response.json()) as T
}
