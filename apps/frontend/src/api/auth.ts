import { request } from "./client"

export interface AuthUser {
  id: number
  email: string
  full_name: string
  status: "active" | "suspended"
  email_verified: boolean
  has_password: boolean
  google_linked: boolean
  created_at: string
  last_login_at: string | null
}

export interface AuthResponse {
  user: AuthUser
  csrf_token: string
  is_new_user: boolean
}

export interface MessageResponse {
  message: string
}

export const authApi = {
  me: () => request<AuthResponse>("/auth/me"),
  login: (body: { email: string; password: string }) =>
    request<AuthResponse>("/auth/login", { method: "POST", body }),
  register: (body: { full_name: string; email: string; password: string; accept_terms: boolean }) =>
    request<MessageResponse>("/auth/register", { method: "POST", body }),
  logout: () => request<void>("/auth/logout", { method: "POST" }),
  logoutEverywhere: () => request<void>("/auth/logout-all", { method: "POST" }),
  verifyEmail: (token: string) =>
    request<MessageResponse>("/auth/verify-email", { method: "POST", body: { token } }),
  resendVerification: (email: string) =>
    request<MessageResponse>("/auth/resend-verification", { method: "POST", body: { email } }),
  forgotPassword: (email: string) =>
    request<MessageResponse>("/auth/forgot-password", { method: "POST", body: { email } }),
  checkResetToken: (token: string) =>
    request<MessageResponse>("/auth/reset-password/check", { method: "POST", body: { token } }),
  resetPassword: (body: { token: string; password: string }) =>
    request<MessageResponse>("/auth/reset-password", { method: "POST", body }),
  changePassword: (body: { current_password: string; new_password: string }) =>
    request<MessageResponse>("/auth/change-password", { method: "POST", body }),
  updateProfile: (body: { full_name: string }) =>
    request<AuthUser>("/auth/me", { method: "PATCH", body }),
  googleNonce: () => request<{ nonce: string }>("/auth/google/nonce"),
  google: (body: { credential: string; nonce: string }) =>
    request<AuthResponse>("/auth/google", { method: "POST", body }),
}
