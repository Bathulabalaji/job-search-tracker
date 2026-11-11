/** Reads `#token=...` from the URL fragment. Fragments are never sent to servers or Referer. */
export function readHashToken(hash: string): string | null {
  const params = new URLSearchParams(hash.startsWith("#") ? hash.slice(1) : hash)
  const token = params.get("token")
  return token && token.length >= 10 ? token : null
}

/** Remove the secret from the address bar and history once it has been read. */
export function clearHash(): void {
  window.history.replaceState(null, "", window.location.pathname + window.location.search)
}
