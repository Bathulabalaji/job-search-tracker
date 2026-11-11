import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { act, render, screen, waitFor } from "@testing-library/react-native"
import { Text } from "react-native"

import { authApi, type AuthResponse, type AuthUser } from "@/api/auth"
import { ApiError, request, setAuthHooks } from "@/api/client"
import { secureStorage } from "@/lib/secure-storage"
import { useAuth } from "./auth-context"
import { AuthProvider, SESSION_KEY } from "./auth-provider"

jest.mock("@/lib/secure-storage", () => ({
  secureStorage: { get: jest.fn(), set: jest.fn(), remove: jest.fn() },
}))
jest.mock("@/api/auth", () => ({
  authApi: { me: jest.fn(), logout: jest.fn(), logoutEverywhere: jest.fn() },
}))

const storage = secureStorage as jest.Mocked<typeof secureStorage>
const api = authApi as jest.Mocked<typeof authApi>

const user: AuthUser = {
  id: 1,
  email: "alice@example.com",
  full_name: "Alice Walker",
  status: "active",
  email_verified: true,
  has_password: true,
  google_linked: false,
  created_at: "2026-01-01T00:00:00Z",
  last_login_at: null,
}
const loginResponse: AuthResponse = { user, csrf_token: "x", is_new_user: false, session_token: "new-token" }

let captured: ReturnType<typeof useAuth>
function Probe() {
  captured = useAuth()
  return <Text testID="status">{captured.state.status}</Text>
}

async function mount(client = new QueryClient()) {
  await render(
    <QueryClientProvider client={client}>
      <AuthProvider>
        <Probe />
      </AuthProvider>
    </QueryClientProvider>,
  )
  return client
}

beforeEach(() => {
  jest.resetAllMocks()
  storage.get.mockResolvedValue(null)
  storage.set.mockResolvedValue(undefined)
  storage.remove.mockResolvedValue(undefined)
  setAuthHooks(null)
})

describe("AuthProvider", () => {
  it("is signed out when there is no saved session, without calling the server", async () => {
    await mount()
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("unauthenticated"))
    expect(api.me).not.toHaveBeenCalled()
  })

  it("restores a saved session", async () => {
    storage.get.mockResolvedValue("saved-token")
    api.me.mockResolvedValue({ ...loginResponse, session_token: null })
    await mount()
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("authenticated"))
  })

  it("forgets a session the server rejects", async () => {
    storage.get.mockResolvedValue("stale-token")
    api.me.mockRejectedValue(new ApiError(401, "Please sign in."))
    await mount()
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("unauthenticated"))
    expect(storage.remove).toHaveBeenCalledWith(SESSION_KEY)
  })

  it("keeps the session when the server is merely unreachable", async () => {
    storage.get.mockResolvedValue("good-token")
    api.me.mockRejectedValue(new ApiError(0, "Can't reach the server."))
    await mount()
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("error"))
    expect(storage.remove).not.toHaveBeenCalled()
  })

  it("keeps the session on a server error (5xx) too", async () => {
    storage.get.mockResolvedValue("good-token")
    api.me.mockRejectedValue(new ApiError(503, "Unavailable"))
    await mount()
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("error"))
    expect(storage.remove).not.toHaveBeenCalled()
  })

  it("stores the token on sign-in and clears cached data from any previous account", async () => {
    const client = await mount()
    client.setQueryData(["opportunities"], [{ id: 1 }])
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("unauthenticated"))
    await act(async () => captured.signIn(loginResponse))
    expect(storage.set).toHaveBeenCalledWith(SESSION_KEY, "new-token")
    expect(client.getQueryData(["opportunities"])).toBeUndefined()
    expect(screen.getByTestId("status")).toHaveTextContent("authenticated")
  })

  it("refuses a login response that has no session token", async () => {
    await mount()
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("unauthenticated"))
    await expect(captured.signIn({ ...loginResponse, session_token: null })).rejects.toThrow()
  })

  it("signs out locally even if the server cannot be reached", async () => {
    storage.get.mockResolvedValue("tok")
    api.me.mockResolvedValue({ ...loginResponse, session_token: null })
    api.logout.mockRejectedValue(new ApiError(0, "offline"))
    const client = await mount()
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("authenticated"))
    client.setQueryData(["x"], 1)
    await act(async () => captured.signOut())
    expect(storage.remove).toHaveBeenCalledWith(SESSION_KEY)
    expect(client.getQueryData(["x"])).toBeUndefined()
    expect(screen.getByTestId("status")).toHaveTextContent("unauthenticated")
  })
})

// Referenced so the import stays honest if the client's public surface changes.
void request
