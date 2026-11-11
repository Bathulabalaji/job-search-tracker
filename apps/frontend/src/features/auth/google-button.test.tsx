import { render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { apiError, authResponse, mockApi } from "@/test/mock-api"

// The client ID is read once at import time, so these tests load the module per scenario.
async function loadButton(clientId: string) {
  vi.resetModules()
  vi.doMock("@/lib/env", () => ({
    API_BASE_URL: "http://localhost:8000/api/v1",
    GOOGLE_CLIENT_ID: clientId,
    TERMS_URL: "",
    PRIVACY_URL: "",
  }))
  vi.doMock("./google-script", () => ({ loadGoogleScript: () => Promise.resolve() }))
  // Import both from the same fresh module graph so they share one theme context.
  const { GoogleSignInButton } = await import("./google-button")
  const { ThemeProvider } = await import("@/components/theme/theme-provider")
  return { Button: GoogleSignInButton, ThemeProvider }
}

interface FakeGoogle {
  initialize: ReturnType<typeof vi.fn>
  renderButton: ReturnType<typeof vi.fn>
  cancel: ReturnType<typeof vi.fn>
}

function installGoogle(): FakeGoogle {
  const fake: FakeGoogle = { initialize: vi.fn(), renderButton: vi.fn(), cancel: vi.fn() }
  Object.defineProperty(window, "google", { value: { accounts: { id: fake } }, configurable: true })
  return fake
}

beforeEach(() => {
  Reflect.deleteProperty(window, "google")
})

function renderButton(parts: Awaited<ReturnType<typeof loadButton>>, onSuccess = vi.fn()) {
  const { Button, ThemeProvider } = parts
  render(
    <ThemeProvider>
      <Button text="signin_with" onSuccess={onSuccess} />
    </ThemeProvider>,
  )
  return onSuccess
}

describe("GoogleSignInButton", () => {
  it("renders nothing and makes no requests when Google is not configured", async () => {
    const api = mockApi({})
    const parts = await loadButton("")
    renderButton(parts)
    expect(screen.queryByTestId("google-button")).not.toBeInTheDocument()
    expect(api.calls).toHaveLength(0)
  })

  it("asks our server for a nonce, then hands it to Google", async () => {
    const google = installGoogle()
    mockApi({ "GET /auth/google/nonce": { body: { nonce: "server-nonce-123456" } } })
    const parts = await loadButton("client-id.apps.googleusercontent.com")
    renderButton(parts)

    await waitFor(() => expect(google.initialize).toHaveBeenCalledTimes(1))
    const config = google.initialize.mock.calls[0]?.[0] as { client_id: string; nonce: string }
    expect(config.client_id).toBe("client-id.apps.googleusercontent.com")
    expect(config.nonce).toBe("server-nonce-123456")
    expect(google.renderButton).toHaveBeenCalledTimes(1)
  })

  it("sends only the credential and nonce to our API, and signs the user in", async () => {
    const google = installGoogle()
    const api = mockApi({
      "GET /auth/google/nonce": { body: { nonce: "server-nonce-123456" } },
      "POST /auth/google": { body: authResponse({ is_new_user: true }) },
    })
    const parts = await loadButton("client-id.apps.googleusercontent.com")
    const onSuccess = renderButton(parts)
    await waitFor(() => expect(google.initialize).toHaveBeenCalled())

    const config = google.initialize.mock.calls[0]?.[0] as {
      callback: (r: { credential: string }) => void
    }
    config.callback({ credential: "google-id-token-xyz" })

    await waitFor(() => expect(onSuccess).toHaveBeenCalledTimes(1))
    const call = api.called("POST", "/auth/google")[0]
    // No name/email/picture from the browser: the server reads them from the verified token.
    expect(call?.body).toEqual({ credential: "google-id-token-xyz", nonce: "server-nonce-123456" })
    expect(onSuccess.mock.calls[0]?.[0]).toMatchObject({ is_new_user: true })
  })

  it("shows the server's refusal and gets a fresh nonce for the next try", async () => {
    const google = installGoogle()
    let nonces = 0
    mockApi({
      "GET /auth/google/nonce": () => ({ body: { nonce: `nonce-number-${++nonces}-abcdef` } }),
      "POST /auth/google": apiError(
        401,
        "google_auth_failed",
        "Google sign-in failed. Please try again.",
      ),
    })
    const parts = await loadButton("client-id.apps.googleusercontent.com")
    const onSuccess = renderButton(parts)
    await waitFor(() => expect(google.initialize).toHaveBeenCalledTimes(1))

    const config = google.initialize.mock.calls[0]?.[0] as {
      callback: (r: { credential: string }) => void
    }
    config.callback({ credential: "bad-token" })

    expect(await screen.findByRole("alert")).toHaveTextContent(/google sign-in failed/i)
    expect(onSuccess).not.toHaveBeenCalled()
    await waitFor(() => expect(google.initialize).toHaveBeenCalledTimes(2))
    const secondConfig = google.initialize.mock.calls[1]?.[0] as { nonce: string }
    expect(secondConfig.nonce).toBe("nonce-number-2-abcdef")
  })

  it("tells the user when Google cannot be loaded", async () => {
    installGoogle()
    mockApi({ "GET /auth/google/nonce": apiError(500, "internal_error", "Something went wrong.") })
    const parts = await loadButton("client-id.apps.googleusercontent.com")
    renderButton(parts)
    expect(await screen.findByRole("alert")).toHaveTextContent(/unavailable/i)
  })

  it("never puts an email, name or any profile data in the request", async () => {
    const google = installGoogle()
    const api = mockApi({
      "GET /auth/google/nonce": { body: { nonce: "server-nonce-123456" } },
      "POST /auth/google": { body: authResponse() },
    })
    const parts = await loadButton("client-id.apps.googleusercontent.com")
    renderButton(parts)
    await waitFor(() => expect(google.initialize).toHaveBeenCalled())
    const config = google.initialize.mock.calls[0]?.[0] as {
      callback: (r: { credential: string }) => void
    }
    config.callback({ credential: "token" })
    await waitFor(() => expect(api.called("POST", "/auth/google")).toHaveLength(1))
    expect(Object.keys(api.called("POST", "/auth/google")[0]?.body as object).sort()).toEqual([
      "credential",
      "nonce",
    ])
  })
})
