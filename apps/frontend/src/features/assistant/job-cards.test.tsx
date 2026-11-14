import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it } from "vitest"

import type { JobCardData } from "@/api/chat"
import { ProtectedRoute } from "@/features/auth/route-guards"
import { apiError, authResponse, mockApi } from "@/test/mock-api"
import { renderRoutes } from "@/test/render"
import { AttachmentList } from "./job-cards"

function job(overrides: Partial<JobCardData> = {}): JobCardData {
  return {
    type: "job",
    id: 7,
    title: "Backend Engineer",
    company: "Zepto",
    location: "Bengaluru",
    work_mode: "hybrid",
    source_site: "linkedin",
    provider: "jsearch",
    apply_url: "https://www.linkedin.com/jobs/view/42",
    posted_at: new Date(Date.now() - 2 * 86_400_000).toISOString(),
    salary_text: null,
    active_status: "active",
    active_checked_at: null,
    tracked_opportunity_id: null,
    ...overrides,
  }
}

function show(items: JobCardData[]) {
  const routes = [
    { path: "/login", element: <p>Login page</p> },
    {
      element: <ProtectedRoute />,
      children: [
        { path: "/a", element: <AttachmentList items={items} /> },
        { path: "/opportunities/:id", element: <p>Opportunity page</p> },
      ],
    },
  ]
  return renderRoutes(routes, { route: "/a" })
}

describe("Job cards", () => {
  it("shows the posting with source, freshness and link status", async () => {
    mockApi({ "GET /auth/me": { body: authResponse() } })
    show([
      job(),
      job({ id: 8, company: "CRED", active_status: "unknown", source_site: "company" }),
      job({ id: 9, company: "Old", active_status: "inactive", apply_url: "javascript:alert(1)" }),
    ])
    expect(await screen.findByText("Zepto")).toBeInTheDocument()
    expect(screen.getAllByText("LinkedIn")).toHaveLength(2)
    expect(screen.getByText("Company site")).toBeInTheDocument()
    expect(screen.getByText("Verified open")).toBeInTheDocument()
    expect(screen.getByText("Not verified")).toBeInTheDocument()
    expect(screen.getByText("Looks closed")).toBeInTheDocument()
    expect(screen.getAllByText("Posted 2 days ago")).toHaveLength(3)
    const links = screen.getAllByRole("link", { name: /open/i })
    // the javascript: link is never rendered
    expect(links.map((a) => a.getAttribute("href"))).toEqual([
      "https://www.linkedin.com/jobs/view/42",
      "https://www.linkedin.com/jobs/view/42",
    ])
    expect(links[0]).toHaveAttribute("rel", expect.stringContaining("noopener"))
  })

  it("tracks a job and then links to the new opportunity", async () => {
    const api = mockApi({
      "GET /auth/me": { body: authResponse() },
      "POST /jobs/7/track": { status: 201, body: { id: 31, company: "Zepto" } },
    })
    show([job()])
    const user = userEvent.setup()
    await user.click(await screen.findByRole("button", { name: /track/i }))
    await waitFor(() => expect(api.called("POST", "/jobs/7/track")).toHaveLength(1))
    const inPipeline = await screen.findByRole("link", { name: "In pipeline" })
    expect(inPipeline).toHaveAttribute("href", "/opportunities/31")
  })

  it("already-tracked jobs link straight to the pipeline", async () => {
    mockApi({
      "GET /auth/me": { body: authResponse() },
      "POST /jobs/7/track": apiError(409, "already_tracked", "already"),
    })
    show([job({ tracked_opportunity_id: 12 })])
    expect(await screen.findByRole("link", { name: "In pipeline" })).toHaveAttribute(
      "href",
      "/opportunities/12",
    )
    expect(screen.queryByRole("button", { name: /track/i })).not.toBeInTheDocument()
  })
})
