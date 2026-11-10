import { createBrowserRouter } from "react-router-dom"

import { AppLayout } from "@/components/layout/app-layout"
import { OpportunityDetailPage } from "@/pages/opportunity-detail-page"
import { PipelinePage } from "@/pages/pipeline-page"
import { PlaceholderPage } from "@/pages/placeholder-page"
import { TodayPage } from "@/pages/today-page"

export const router = createBrowserRouter([
  {
    element: <AppLayout />,
    children: [
      { index: true, element: <TodayPage /> },
      { path: "pipeline", element: <PipelinePage /> },
      { path: "opportunities/:id", element: <OpportunityDetailPage /> },
      { path: "analytics", element: <PlaceholderPage title="Analytics" /> },
      { path: "daily-log", element: <PlaceholderPage title="Daily log" /> },
      { path: "prep", element: <PlaceholderPage title="Prep" /> },
      { path: "contacts", element: <PlaceholderPage title="Contacts & Resumes" /> },
      { path: "*", element: <PlaceholderPage title="Not found" /> },
    ],
  },
])
