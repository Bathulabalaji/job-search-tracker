import { API_BASE_URL } from "@/lib/env"

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = "ApiError"
    this.status = status
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
        const msg = typeof item.msg === "string" ? item.msg : "Invalid value"
        return where ? `${where}: ${msg}` : msg
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

export async function request<T>(
  path: string,
  options: { method?: string; body?: unknown; params?: QueryParams } = {},
): Promise<T> {
  const { method = "GET", body, params } = options
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}${toQueryString(params)}`, {
      method,
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new ApiError(0, "Cannot reach the API. Is the backend running?")
  }

  if (!response.ok) {
    let detail: unknown
    try {
      detail = ((await response.json()) as { detail?: unknown }).detail
    } catch {
      detail = undefined
    }
    throw new ApiError(response.status, describeDetail(detail))
  }
  if (response.status === 204) return undefined as T
  // The backend's OpenAPI contract is the source of truth for T (see api/types.ts).
  return (await response.json()) as T
}
