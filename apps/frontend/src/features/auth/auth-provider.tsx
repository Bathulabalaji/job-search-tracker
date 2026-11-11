import { useQueryClient } from "@tanstack/react-query"
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react"
import { toast } from "sonner"

import { authApi, type AuthResponse, type AuthUser } from "@/api/auth"
import { ApiError, setAuthHooks } from "@/api/client"
import { setCsrfToken } from "@/lib/csrf"
import { AuthContext, type AuthContextValue, type AuthState } from "./auth-context"

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [state, setState] = useState<AuthState>({ status: "loading", user: null })
  const stateRef = useRef(state)
  // Layout effect: the ref must already be current when the commit becomes visible, so a request
  // that fails right afterwards sees the right state.
  useLayoutEffect(() => {
    stateRef.current = state
  }, [state])

  /** Forget everything tied to the previous user so the next one never sees stale data. */
  const resetSession = useCallback(() => {
    setCsrfToken(null)
    queryClient.clear()
  }, [queryClient])

  const adopt = useCallback((response: AuthResponse) => {
    setCsrfToken(response.csrf_token)
    setState({ status: "authenticated", user: response.user })
  }, [])

  const loadSession = useCallback(async () => {
    try {
      adopt(await authApi.me())
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        setCsrfToken(null)
        setState({ status: "unauthenticated", user: null, expired: false })
      } else {
        setState({
          status: "error",
          user: null,
          message: error instanceof Error ? error.message : "Could not reach the server.",
        })
      }
    }
  }, [adopt])

  useEffect(() => {
    let active = true
    authApi
      .me()
      .then((response) => active && adopt(response))
      .catch((error: unknown) => {
        if (!active) return
        if (error instanceof ApiError && error.status === 401) {
          setCsrfToken(null)
          setState({ status: "unauthenticated", user: null, expired: false })
        } else {
          setState({
            status: "error",
            user: null,
            message: error instanceof Error ? error.message : "Could not reach the server.",
          })
        }
      })
    return () => {
      active = false
    }
  }, [adopt])

  useEffect(() => {
    setAuthHooks({
      onSessionExpired: () => {
        // Only meaningful if we thought we were signed in.
        if (stateRef.current.status !== "authenticated") return
        resetSession()
        setState({ status: "unauthenticated", user: null, expired: true })
        toast.error("Your session expired. Please sign in again.")
      },
      refreshCsrf: async () => {
        try {
          adopt(await authApi.me())
          return true
        } catch {
          return false
        }
      },
    })
    return () => setAuthHooks(null)
  }, [adopt, resetSession])

  const value = useMemo<AuthContextValue>(
    () => ({
      state,
      signIn: (response) => {
        queryClient.clear()
        adopt(response)
      },
      signOut: async () => {
        try {
          await authApi.logout()
        } catch {
          // Even if the request failed, leave this browser signed out.
        }
        resetSession()
        setState({ status: "unauthenticated", user: null, expired: false })
      },
      refresh: loadSession,
      setUser: (user: AuthUser) => setState({ status: "authenticated", user }),
    }),
    [state, queryClient, adopt, resetSession, loadSession],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
