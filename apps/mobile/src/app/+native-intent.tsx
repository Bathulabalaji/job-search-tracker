/**
 * Google sign-in returns to the app through a deep link (com.jobstracker.app:/oauthredirect…).
 * expo-auth-session reads that link itself, so the router must not treat it as a screen:
 * without this it shows "Unmatched Route" and the sign-in never completes.
 * Returning null tells the router to stay on the current screen.
 */
export function redirectSystemPath({ path }: { path: string; initial: boolean }): string | null {
  try {
    if (path.includes("oauthredirect")) return null
  } catch {
    // Fall through to normal routing.
  }
  return path
}
