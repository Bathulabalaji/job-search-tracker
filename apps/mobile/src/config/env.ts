/** Public build-time settings. EXPO_PUBLIC_* values are inlined into the app bundle. */
export const API_BASE_URL: string =
  process.env.EXPO_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1"

/** The website. Email links (verify, reset password) open there. */
export const WEB_URL: string = (
  process.env.EXPO_PUBLIC_WEB_URL ?? "https://job-search-tracker-blond.vercel.app"
).replace(/\/$/, "")

/** OAuth client IDs of type iOS / Android. Empty hides "Continue with Google". */
export const GOOGLE_IOS_CLIENT_ID: string = process.env.EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID ?? ""
export const GOOGLE_ANDROID_CLIENT_ID: string = process.env.EXPO_PUBLIC_GOOGLE_ANDROID_CLIENT_ID ?? ""
