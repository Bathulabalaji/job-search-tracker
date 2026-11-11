// The CSRF token is bound to the session cookie and returned by /auth/me and the sign-in
// endpoints. It lives in memory only (never localStorage), and is sent on unsafe requests.
let token: string | null = null

export function setCsrfToken(value: string | null): void {
  token = value
}

export function getCsrfToken(): string | null {
  return token
}
