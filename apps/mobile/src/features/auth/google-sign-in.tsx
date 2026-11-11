import { useMutation, useQuery } from "@tanstack/react-query"
import * as Google from "expo-auth-session/providers/google"
import * as WebBrowser from "expo-web-browser"
import { useEffect } from "react"
import { Platform } from "react-native"

import { authApi, type AuthResponse } from "@/api/auth"
import { ApiError } from "@/api/client"
import { Button } from "@/components/ui/button"
import { GOOGLE_ANDROID_CLIENT_ID, GOOGLE_IOS_CLIENT_ID } from "@/config/env"
import { googleRedirectUri } from "@/config/google"

WebBrowser.maybeCompleteAuthSession()

interface Props {
  onSuccess: (response: AuthResponse) => void
  onError: (message: string) => void
  label: string
}

const CLIENT_ID = Platform.OS === "ios" ? GOOGLE_IOS_CLIENT_ID : GOOGLE_ANDROID_CLIENT_ID

/** True when a Google client ID exists for this platform. Otherwise the button is hidden. */
export const googleSignInAvailable = Platform.OS !== "web" && CLIENT_ID !== ""

export function GoogleSignInButton(props: Props) {
  // A server-issued nonce must be inside the ID token we get back: it proves the token
  // was requested for this sign-in attempt and cannot be replayed.
  const nonce = useQuery({
    queryKey: ["google-nonce"],
    queryFn: authApi.googleNonce,
    enabled: googleSignInAvailable,
    gcTime: 0,
    staleTime: 8 * 60_000,
    refetchInterval: 8 * 60_000, // server nonces live 10 minutes
  })
  if (!googleSignInAvailable) return null
  if (!nonce.data) {
    return (
      <Button
        label="Continue with Google"
        icon="logo-google"
        variant="secondary"
        loading={nonce.isLoading}
        disabled
        onPress={() => undefined}
      />
    )
  }
  return (
    <GoogleRequest
      key={nonce.data.nonce}
      nonce={nonce.data.nonce}
      onUsed={() => void nonce.refetch()}
      {...props}
    />
  )
}

function GoogleRequest({
  nonce,
  onUsed,
  onSuccess,
  onError,
  label,
}: Props & { nonce: string; onUsed: () => void }) {
  const [request, response, prompt] = Google.useAuthRequest({
    iosClientId: GOOGLE_IOS_CLIENT_ID || undefined,
    androidClientId: GOOGLE_ANDROID_CLIENT_ID || undefined,
    redirectUri: googleRedirectUri(),
    selectAccount: true,
    extraParams: { nonce },
  })

  const exchange = useMutation({
    mutationFn: (credential: string) => authApi.google({ credential, nonce }),
    onSuccess,
    onError: (error: Error) => {
      onError(
        error instanceof ApiError && error.status !== 0
          ? error.message
          : "Google sign-in failed. Please try again.",
      )
      onUsed() // a nonce is single use: fetch a fresh one for the next attempt
    },
  })

  useEffect(() => {
    if (!response) return
    if (response.type === "success") {
      const idToken = response.authentication?.idToken ?? response.params.id_token
      if (idToken) exchange.mutate(idToken)
      else onError("Google did not return an ID token. Please try again.")
    } else if (response.type === "error") {
      onError("Google sign-in failed. Please try again.")
      onUsed()
    }
    // Only react to a new response, not to every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [response])

  return (
    <Button
      label={label}
      icon="logo-google"
      variant="secondary"
      loading={exchange.isPending}
      disabled={!request}
      onPress={() => void prompt()}
    />
  )
}
