import { createBrowserRouter } from "react-router-dom"

import { AppLayout } from "@/components/layout/app-layout"
import { ContactsPage } from "@/pages/contacts-page"
import { DailyLogPage } from "@/pages/daily-log-page"
import { OpportunityDetailPage } from "@/pages/opportunity-detail-page"
import { PipelinePage } from "@/pages/pipeline-page"
import { PlaceholderPage } from "@/pages/placeholder-page"
import { PrepPage } from "@/pages/prep-page"
import { TodayPage } from "@/pages/today-page"

export const router = createBrowserRouter([
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
      { path: "*", element: <PlaceholderPage title="Not found" /> },
    ],
  },
])
