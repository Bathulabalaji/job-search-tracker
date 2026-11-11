import { createContext, useContext } from "react"

import type { AuthResponse, AuthUser } from "@/api/auth"

export type AuthState =
  | { status: "loading" }
  | { status: "unauthenticated" }
  | { status: "error"; message: string }
  | { status: "authenticated"; user: AuthUser }

export interface AuthContextValue {
  state: AuthState
  /** Store a freshly issued session (after login or Google sign-in). */
  signIn: (response: AuthResponse) => Promise<void>
  /** Sign out on the server (best effort) and forget the session on this device. */
  signOut: () => Promise<void>
  /** Sign out everywhere, then forget the session here. */
  signOutEverywhere: () => Promise<void>
  /** Re-check the session, e.g. after the server was unreachable. */
  refresh: () => Promise<void>
  setUser: (user: AuthUser) => void
}

export const AuthContext = createContext<AuthContextValue | null>(null)

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext)
  if (!value) throw new Error("useAuth must be used inside <AuthProvider>")
  return value
}

/** The signed-in user. Only call inside screens that require sign-in. */
export function useUser(): AuthUser {
  const { state } = useAuth()
  if (state.status !== "authenticated") throw new Error("useUser called while signed out")
  return state.user
}
