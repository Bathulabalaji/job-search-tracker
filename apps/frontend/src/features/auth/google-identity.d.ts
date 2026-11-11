// The slice of Google Identity Services (https://accounts.google.com/gsi/client) we use.
interface GoogleCredentialResponse {
  credential: string
}

interface GoogleButtonOptions {
  type?: "standard" | "icon"
  theme?: "outline" | "filled_blue" | "filled_black"
  size?: "large" | "medium" | "small"
  text?: "signin_with" | "signup_with" | "continue_with" | "signin"
  shape?: "rectangular" | "pill"
  width?: number
  logo_alignment?: "left" | "center"
}

interface GoogleIdConfiguration {
  client_id: string
  callback: (response: GoogleCredentialResponse) => void
  /** Echoed back inside the signed ID token; the server checks it. */
  nonce?: string
  ux_mode?: "popup" | "redirect"
  auto_select?: boolean
  cancel_on_tap_outside?: boolean
}

interface GoogleAccountsId {
  initialize: (config: GoogleIdConfiguration) => void
  renderButton: (parent: HTMLElement, options: GoogleButtonOptions) => void
  cancel: () => void
}

interface Window {
  google?: { accounts: { id: GoogleAccountsId } }
}
