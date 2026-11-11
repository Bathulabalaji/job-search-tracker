import { useEffect, useState } from "react"

import { clearHash, readHashToken } from "./hash-token"

interface HashToken {
  token: string | null
  /** Changes every time a link is opened, so pages can restart even for the same token. */
  attempt: number
}

/**
 * The one-time token from the URL fragment (`#token=...`).
 *
 * It is read on load and whenever a new link is opened in the same tab (a fragment-only change
 * does not reload the page), then scrubbed from the address bar and history.
 */
export function useHashToken(): HashToken {
  const [state, setState] = useState<HashToken>(() => ({
    token: readHashToken(window.location.hash),
    attempt: 0,
  }))

  useEffect(() => {
    const onHashChange = () => {
      const token = readHashToken(window.location.hash)
      if (token) setState((previous) => ({ token, attempt: previous.attempt + 1 }))
    }
    window.addEventListener("hashchange", onHashChange)
    return () => window.removeEventListener("hashchange", onHashChange)
  }, [])

  useEffect(() => {
    if (window.location.hash) clearHash()
  }, [state])

  return state
}
