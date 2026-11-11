export const API_BASE_URL: string =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1"

/** Public Google OAuth client ID. Empty hides the "Continue with Google" buttons. */
export const GOOGLE_CLIENT_ID: string = import.meta.env.VITE_GOOGLE_CLIENT_ID ?? ""

/** Optional links shown next to the terms checkbox. */
export const TERMS_URL: string = import.meta.env.VITE_TERMS_URL ?? ""
export const PRIVACY_URL: string = import.meta.env.VITE_PRIVACY_URL ?? ""
