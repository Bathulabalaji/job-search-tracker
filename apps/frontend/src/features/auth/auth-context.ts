import { createContext, useContext } from "react"

import type { AuthResponse, AuthUser } from "@/api/auth"

export type AuthState =
  | { status: "loading"; user: null }
  | { status: "unauthenticated"; user: null; expired: boolean }
  | { status: "error"; user: null; message: string }
  | { status: "authenticated"; user: AuthUser }

export interface AuthContextValue {
  state: AuthState
  /** Adopt a successful sign-in/sign-up response (stores the CSRF token, resets cached data). */
  signIn: (response: AuthResponse) => void
  signOut: () => Promise<void>
  /** Re-read the current user from the server (after a profile change, for example). */
  refresh: () => Promise<void>
  setUser: (user: AuthUser) => void
}

export const AuthContext = createContext<AuthContextValue | null>(null)

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext)
  if (!value) throw new Error("useAuth must be used inside <AuthProvider>")
  return value
}

/** The signed-in user. Only call inside protected routes, where one always exists. */
export function useCurrentUser(): AuthUser {
  const { state } = useAuth()
  if (state.status !== "authenticated") throw new Error("useCurrentUser needs a signed-in user")
  return state.user
}
