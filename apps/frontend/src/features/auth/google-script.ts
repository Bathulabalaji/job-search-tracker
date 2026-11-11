const SRC = "https://accounts.google.com/gsi/client"

let loading: Promise<void> | null = null

/** Loads Google's script once. Rejects (and allows a retry) if it cannot be fetched. */
export function loadGoogleScript(): Promise<void> {
  if (window.google?.accounts.id) return Promise.resolve()
  if (loading) return loading
  loading = new Promise<void>((resolve, reject) => {
    const script = document.createElement("script")
    script.src = SRC
    script.async = true
    script.defer = true
    script.onload = () => resolve()
    script.onerror = () => {
      loading = null
      script.remove()
      reject(new Error("Could not load Google sign-in."))
    }
    document.head.appendChild(script)
  })
  return loading
}
