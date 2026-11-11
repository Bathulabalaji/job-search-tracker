import "@testing-library/jest-dom/vitest"
import { cleanup } from "@testing-library/react"
import { afterEach, beforeEach, vi } from "vitest"

import { setAuthHooks } from "@/api/client"
import { setCsrfToken } from "@/lib/csrf"

// jsdom lacks these browser APIs (Radix and the layout code use them).
class ResizeObserverStub {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}

beforeEach(() => {
  vi.stubGlobal("ResizeObserver", ResizeObserverStub)
  vi.stubGlobal(
    "matchMedia",
    vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
      onchange: null,
    })),
  )
})

afterEach(() => {
  cleanup()
  setCsrfToken(null)
  setAuthHooks(null)
  vi.unstubAllGlobals()
  window.history.replaceState(null, "", "/")
})
