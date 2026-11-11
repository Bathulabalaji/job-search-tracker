import { createBrowserRouter } from "react-router-dom"

import { AuthLayout } from "@/components/auth/auth-layout"
import { AppLayout } from "@/components/layout/app-layout"
import { ProtectedRoute, PublicOnlyRoute } from "@/features/auth/route-guards"
import { ForgotPasswordPage } from "@/pages/auth/forgot-password-page"
import { LoginPage } from "@/pages/auth/login-page"
import { RegisterPage } from "@/pages/auth/register-page"
import { ResetPasswordPage } from "@/pages/auth/reset-password-page"
import { VerifyEmailPage } from "@/pages/auth/verify-email-page"
import { AccountPage } from "@/pages/account-page"
import { ContactsPage } from "@/pages/contacts-page"
import { DailyLogPage } from "@/pages/daily-log-page"
import { OpportunityDetailPage } from "@/pages/opportunity-detail-page"
import { PipelinePage } from "@/pages/pipeline-page"
import { PlaceholderPage } from "@/pages/placeholder-page"
import { PrepPage } from "@/pages/prep-page"
import { TodayPage } from "@/pages/today-page"

export const router = createBrowserRouter([
  // Signed-out pages. Signed-in visitors are sent on to the app.
  {
    element: <PublicOnlyRoute />,
    children: [
      {
        element: <AuthLayout />,
        children: [
          { path: "login", element: <LoginPage /> },
          { path: "register", element: <RegisterPage /> },
          { path: "forgot-password", element: <ForgotPasswordPage /> },
        ],
      },
    ],
  },
  // Reachable whether or not you are signed in (links arrive by email).
  {
    element: <AuthLayout />,
    children: [
      { path: "verify-email", element: <VerifyEmailPage /> },
      { path: "reset-password", element: <ResetPasswordPage /> },
    ],
  },
  // The app itself: requires a signed-in user.
  {
    element: <ProtectedRoute />,
    children: [
      {
        element: <AppLayout />,
        children: [
          { index: true, element: <TodayPage /> },
          { path: "pipeline", element: <PipelinePage /> },
          { path: "opportunities/:id", element: <OpportunityDetailPage /> },
          {
            path: "analytics",
            // Recharts is heavy; load it only when this page is opened.
            lazy: async () => {
              const { AnalyticsPage } = await import("@/pages/analytics-page")
              return { Component: AnalyticsPage }
            },
          },
          { path: "daily-log", element: <DailyLogPage /> },
          { path: "prep", element: <PrepPage /> },
          { path: "contacts", element: <ContactsPage /> },
          { path: "account", element: <AccountPage /> },
          { path: "*", element: <PlaceholderPage title="Not found" /> },
        ],
      },
    ],
  },
])
