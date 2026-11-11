// Mirrors apps/backend/app/core/security.py. The server is the authority; this gives instant
// feedback so people are not surprised by a rejection after submitting.
export const MIN_PASSWORD_LENGTH = 10
export const MAX_PASSWORD_LENGTH = 128

export interface PasswordCheck {
  label: string
  met: boolean
}

export function passwordChecks(password: string): PasswordCheck[] {
  return [
    {
      label: `At least ${MIN_PASSWORD_LENGTH} characters`,
      met: password.length >= MIN_PASSWORD_LENGTH,
    },
    { label: "A letter", met: /[A-Za-z]/.test(password) },
    { label: "A number", met: /\d/.test(password) },
  ]
}

/** First problem with a password, or null when it passes every client-side rule. */
export function passwordProblem(
  password: string,
  context: { email?: string; fullName?: string } = {},
): string | null {
  if (password.length < MIN_PASSWORD_LENGTH) {
    return `Use at least ${MIN_PASSWORD_LENGTH} characters.`
  }
  if (password.length > MAX_PASSWORD_LENGTH) return `Use at most ${MAX_PASSWORD_LENGTH} characters.`
  if (!/[A-Za-z]/.test(password)) return "Include at least one letter."
  if (!/\d/.test(password)) return "Include at least one number."
  const lowered = password.toLowerCase()
  const local = (context.email ?? "").split("@")[0]?.toLowerCase() ?? ""
  if (local.length >= 4 && lowered.includes(local))
    return "Do not include your email name in the password."
  for (const part of (context.fullName ?? "").toLowerCase().split(/\s+/)) {
    if (part.length >= 4 && lowered.includes(part))
      return "Do not include your name in the password."
  }
  return null
}

/** Open redirect protection: only same-site absolute paths are accepted after sign-in. */
