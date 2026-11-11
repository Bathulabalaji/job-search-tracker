import { useEffect, useRef, useState } from "react"

import { authApi, type AuthResponse } from "@/api/auth"
import { ApiError, retryMessage } from "@/api/client"
import { FormAlert } from "@/components/auth/form-alert"
import { useTheme } from "@/components/theme/theme-context"
import { GOOGLE_CLIENT_ID } from "@/lib/env"
import { loadGoogleScript } from "./google-script"

interface GoogleSignInButtonProps {
  text: "signin_with" | "signup_with" | "continue_with"
  onSuccess: (response: AuthResponse) => void
}

/**
 * Google's own button. The ID token it returns goes straight to our API, which verifies the
 * signature, issuer, audience, expiry and nonce. Nothing about the user is read from the browser.
 */
export function GoogleSignInButton({ text, onSuccess }: GoogleSignInButtonProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const onSuccessRef = useRef(onSuccess)
  useEffect(() => {
    onSuccessRef.current = onSuccess
  }, [onSuccess])
  const { theme } = useTheme()
  const [error, setError] = useState<string | null>(null)
  // Bumping this re-initialises the button with a fresh nonce after a failed attempt.
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    if (!GOOGLE_CLIENT_ID) return
    let cancelled = false

    async function setup() {
      try {
        const [{ nonce }] = await Promise.all([authApi.googleNonce(), loadGoogleScript()])
        const google = window.google?.accounts.id
        const container = containerRef.current
        if (cancelled || !google || !container) return

        google.initialize({
          client_id: GOOGLE_CLIENT_ID,
          nonce,
          ux_mode: "popup",
          auto_select: false,
          callback: (response) => {
            setError(null)
            authApi
              .google({ credential: response.credential, nonce })
              .then((result) => onSuccessRef.current(result))
              .catch((e: unknown) => {
                setError(
                  e instanceof ApiError
                    ? retryMessage(e)
                    : "Google sign-in failed. Please try again.",
                )
                setAttempt((n) => n + 1) // the nonce is spent; get a new one
              })
          },
        })
        container.replaceChildren()
        google.renderButton(container, {
          type: "standard",
          theme: theme === "dark" ? "filled_black" : "outline",
          size: "large",
          text,
          shape: "rectangular",
          logo_alignment: "left",
          width: Math.min(Math.max(container.clientWidth, 200), 400),
        })
      } catch {
        if (!cancelled) setError("Google sign-in is unavailable right now.")
      }
    }
    void setup()
    return () => {
      cancelled = true
    }
  }, [text, theme, attempt])

  if (!GOOGLE_CLIENT_ID) return null
  return (
    <div className="space-y-3">
      <div
        ref={containerRef}
        className="flex min-h-10 w-full justify-center"
        data-testid="google-button"
      />
      {error ? <FormAlert tone="error">{error}</FormAlert> : null}
    </div>
  )
}
