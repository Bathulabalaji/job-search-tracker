import { createBrowserRouter } from "react-router-dom"

import { AppLayout } from "@/components/layout/app-layout"
import { PlaceholderPage } from "@/pages/placeholder-page"

export const router = createBrowserRouter([
  {
    element: <AppLayout />,
    children: [
      { index: true, element: <PlaceholderPage title="Today" /> },
      { path: "pipeline", element: <PlaceholderPage title="Pipeline" /> },
      { path: "opportunities/:id", element: <PlaceholderPage title="Opportunity" /> },
      { path: "analytics", element: <PlaceholderPage title="Analytics" /> },
      { path: "daily-log", element: <PlaceholderPage title="Daily log" /> },
      { path: "prep", element: <PlaceholderPage title="Prep" /> },
      { path: "contacts", element: <PlaceholderPage title="Contacts & Resumes" /> },
      { path: "*", element: <PlaceholderPage title="Not found" /> },
    ],
  },
])
