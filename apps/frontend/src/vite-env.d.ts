/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string
  readonly VITE_GOOGLE_CLIENT_ID?: string
  readonly VITE_TERMS_URL?: string
  readonly VITE_PRIVACY_URL?: string
  readonly VITE_CONTACT_NAME?: string
  readonly VITE_CONTACT_EMAIL?: string
  readonly VITE_CONTACT_PHONE?: string
  readonly VITE_CONTACT_LINKEDIN_URL?: string
  readonly VITE_CONTACT_GITHUB_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
