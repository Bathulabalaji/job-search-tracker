import { useQueryClient } from "@tanstack/react-query"
import { useCallback, useEffect, useMemo, useState } from "react"

import { authApi, type AuthResponse, type AuthUser } from "@/api/auth"
import { ApiError, setAuthHooks, setSessionToken } from "@/api/client"
import { secureStorage } from "@/lib/secure-storage"
import { toast } from "@/lib/toast-bus"
import { AuthContext, type AuthContextValue, type AuthState } from "./auth-context"

export const SESSION_KEY = "session-token"

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient()
  const [state, setState] = useState<AuthState>({ status: "loading" })

  const forget = useCallback(async () => {
    setSessionToken(null)
    await secureStorage.remove(SESSION_KEY)
    // Another account must never see this one's cached data.
    queryClient.clear()
  }, [queryClient])

  const restore = useCallback(async () => {
    setState({ status: "loading" })
    const token = await secureStorage.get(SESSION_KEY)
    if (!token) {
      setState({ status: "unauthenticated" })
      return
    }
    setSessionToken(token)
    try {
      const { user } = await authApi.me()
      setState({ status: "authenticated", user })
    } catch (error) {
      if (error instanceof ApiError && error.status !== 0 && error.status < 500) {
        // The server said no: the session ended (expired, revoked, suspended).
        await forget()
        setState({ status: "unauthenticated" })
      } else {
        // Offline or server down: keep the token and let the user retry.
        setState({
          status: "error",
          message: error instanceof Error ? error.message : "Something went wrong.",
        })
      }
    }
  }, [forget])

  useEffect(() => {
    void restore()
  }, [restore])

  useEffect(() => {
    setAuthHooks({
      onSessionExpired: () => {
        void forget().then(() => {
          setState((current) => {
            if (current.status === "authenticated") {
              toast.info("Session expired", "Please sign in again.")
              return { status: "unauthenticated" }
            }
            return current
          })
        })
      },
    })
    return () => setAuthHooks(null)
  }, [forget])

  const signIn = useCallback(
    async (response: AuthResponse) => {
      if (!response.session_token) throw new Error("The server did not return a session.")
      queryClient.clear()
      setSessionToken(response.session_token)
      await secureStorage.set(SESSION_KEY, response.session_token)
      setState({ status: "authenticated", user: response.user })
    },
    [queryClient],
  )

  const signOut = useCallback(async () => {
    try {
      await authApi.logout()
    } catch {
      // Even if the server cannot be reached, this device must forget the session.
    }
    await forget()
    setState({ status: "unauthenticated" })
  }, [forget])

  const signOutEverywhere = useCallback(async () => {
    await authApi.logoutEverywhere()
    await forget()
    setState({ status: "unauthenticated" })
  }, [forget])

  const setUser = useCallback((user: AuthUser) => {
    setState((current) => (current.status === "authenticated" ? { status: "authenticated", user } : current))
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({ state, signIn, signOut, signOutEverywhere, refresh: restore, setUser }),
    [state, signIn, signOut, signOutEverywhere, restore, setUser],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
