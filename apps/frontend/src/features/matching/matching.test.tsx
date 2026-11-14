import { screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

const toasts = vi.hoisted(() => ({ error: vi.fn(), success: vi.fn(), info: vi.fn() }))
vi.mock("sonner", () => ({ toast: toasts }))

import type { JobCardData, MatchCardData } from "@/api/chat"
import type { MatchResult, Recommendation } from "@/api/matching"
import type { Opportunity } from "@/api/types"
import { AttachmentList } from "@/features/assistant/job-cards"
import { ResumeFitCard } from "@/features/detail/resume-fit-card"
import { ProtectedRoute } from "@/features/auth/route-guards"
import { RecommendationsPage } from "@/pages/recommendations-page"
import { apiError, authResponse, mockApi } from "@/test/mock-api"
import { renderRoutes } from "@/test/render"

const RESULT: MatchResult = {
  target: "opportunity",
  target_id: 5,
  target_label: "Zepto — Backend Engineer",
  best_resume_id: 2,
  jd_source: "opportunity",
  cached: false,
  model: "gemini",
  per_resume: [
    {
      resume_id: 2,
      label: "Backend",
      vector_score: 0.71,
      score: 82,
      matched_skills: ["Python", "FastAPI"],
      missing_skills: ["Kubernetes"],
      suggestions: ["Add Kubernetes work."],
    },
    {
      resume_id: 1,
      label: "Fullstack",
      vector_score: 0.6,
      score: 61,
      matched_skills: ["Python"],
      missing_skills: [],
      suggestions: [],
    },
  ],
}

const OPP = { id: 5, company: "Zepto", role: "Backend Engineer", fit_score: null } as Opportunity

function show(element: React.ReactNode, path = "/a") {
  return renderRoutes(
    [
      { path: "/login", element: <p>Login page</p> },
      {
        element: <ProtectedRoute />,
        children: [
          { path: path, element },
          { path: "/opportunities/:id", element: <p>Opportunity page</p> },
        ],
      },
    ],
    { route: path },
  )
}

// The API answers a bare JSON null when nothing is stored.
const NOTHING_STORED = { raw: "null", headers: { "Content-Type": "application/json" } }

const config = { body: { enabled: true, matching: true, recommendations: true } }

describe("Resume fit card", () => {
  it("compares the resumes, shows the breakdown and saves the best score", async () => {
    const api = mockApi({
      "GET /auth/me": { body: authResponse() },
      "GET /chat/config": config,
      "GET /opportunities/5/match": NOTHING_STORED,
      "POST /opportunities/5/match": { body: RESULT },
      "PATCH /opportunities/5": { body: { ...OPP, fit_score: 82 } },
    })
    show(<ResumeFitCard opportunity={OPP} />)
    const user = userEvent.setup()

    await user.click(await screen.findByRole("button", { name: /compare my resumes/i }))

    const list = await screen.findByRole("list", { name: "Resume fit" })
    expect(within(list).getByText("Best fit")).toBeInTheDocument()
    expect(within(list).getByText("82/100")).toBeInTheDocument()
    expect(within(list).getByText("Kubernetes")).toBeInTheDocument()
    expect(within(list).getByText("Add Kubernetes work.")).toBeInTheDocument()
    expect(api.called("POST", "/opportunities/5/match")[0]?.body).toEqual({ force: false })

    await user.click(screen.getByRole("button", { name: /use 82 as fit score/i }))
    await waitFor(() => expect(api.called("PATCH", "/opportunities/5")).toHaveLength(1))
    expect(api.called("PATCH", "/opportunities/5")[0]?.body).toEqual({ fit_score: 82 })
  })

  it("shows a stored result without asking again, and explains a missing JD", async () => {
    mockApi({
      "GET /auth/me": { body: authResponse() },
      "GET /chat/config": config,
      "GET /opportunities/5/match": { body: { ...RESULT, cached: true } },
    })
    show(<ResumeFitCard opportunity={OPP} />)
    expect(await screen.findByText("82/100")).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /compare my resumes/i })).not.toBeInTheDocument()
  })

  it("is hidden when matching isn't available", async () => {
    mockApi({
      "GET /auth/me": { body: authResponse() },
      "GET /chat/config": { body: { enabled: true, matching: false } },
    })
    show(<ResumeFitCard opportunity={OPP} />)
    await waitFor(() => expect(screen.queryByText("Which resume fits?")).not.toBeInTheDocument())
  })

  it("tells the user when something blocks the comparison", async () => {
    mockApi({
      "GET /auth/me": { body: authResponse() },
      "GET /chat/config": config,
      "GET /opportunities/5/match": NOTHING_STORED,
      "POST /opportunities/5/match": apiError(
        422,
        "jd_missing",
        "Paste the job description first.",
      ),
    })
    show(<ResumeFitCard opportunity={OPP} />)
    const user = userEvent.setup()
    await user.click(await screen.findByRole("button", { name: /compare my resumes/i }))
    await waitFor(() =>
      expect(toasts.error).toHaveBeenCalledWith("Paste the job description first."),
    )
  })
})

describe("Match card in chat", () => {
  it("renders alongside job cards and links to the opportunity", async () => {
    mockApi({ "GET /auth/me": { body: authResponse() } })
    const match: MatchCardData = { type: "match", ...RESULT }
    show(<AttachmentList items={[match]} />)
    expect(await screen.findByText("Resume fit · Zepto — Backend Engineer")).toBeInTheDocument()
    expect(screen.getByRole("link", { name: /open opportunity/i })).toHaveAttribute(
      "href",
      "/opportunities/5",
    )
  })
})

const JOB: JobCardData = {
  type: "job",
  id: 9,
  title: "Platform Engineer",
  company: "Razorpay",
  location: "Bengaluru",
  work_mode: null,
  source_site: "company",
  provider: "serpapi",
  apply_url: "https://careers.razorpay.example/9",
  posted_at: null,
  salary_text: null,
  active_status: "unknown",
  active_checked_at: null,
  tracked_opportunity_id: null,
}
const REC: Recommendation = {
  id: 3,
  job: JOB,
  vector_score: 0.74,
  best_resume_id: 2,
  best_resume_label: "Backend",
  created_at: "2026-11-14T10:00:00Z",
}
const PROFILE = {
  title_keywords: ["Backend Engineer"],
  locations: ["Bengaluru"],
  work_modes: [],
  min_vector_score: 0.55,
  enabled: true,
  last_refreshed_at: null,
}

describe("Jobs for you", () => {
  it("lists ranked jobs with their best resume and lets the user dismiss one", async () => {
    let dismissed = false
    const api = mockApi({
      "GET /auth/me": { body: authResponse() },
      "GET /recommendations": () => ({ body: dismissed ? [] : [REC] }),
      "GET /recommendations/profile": { body: PROFILE },
      "POST /recommendations/3/dismiss": () => {
        dismissed = true
        return { status: 204 }
      },
    })
    show(<RecommendationsPage />, "/jobs-for-you")
    expect(await screen.findByText("Platform Engineer")).toBeInTheDocument()
    expect(screen.getByText(/74% similar · best resume: Backend/)).toBeInTheDocument()

    await userEvent
      .setup()
      .click(screen.getByRole("button", { name: /dismiss platform engineer/i }))
    await waitFor(() => expect(api.called("POST", "/recommendations/3/dismiss")).toHaveLength(1))
    expect(await screen.findByText("No recommendations yet")).toBeInTheDocument()
  })

  it("refreshes, reports what it found, and shows the daily limit message", async () => {
    const api = mockApi({
      "GET /auth/me": { body: authResponse() },
      "GET /recommendations": { body: [] },
      "GET /recommendations/profile": { body: PROFILE },
      "POST /recommendations/refresh": apiError(
        429,
        "recommendations_quota",
        "You've refreshed Jobs for you as often as today allows.",
      ),
    })
    show(<RecommendationsPage />, "/jobs-for-you")
    const user = userEvent.setup()
    await user.click(await screen.findByRole("button", { name: /find new jobs/i }))
    await waitFor(() => expect(api.called("POST", "/recommendations/refresh")).toHaveLength(1))
    await waitFor(() =>
      expect(toasts.error).toHaveBeenCalledWith(
        "You've refreshed Jobs for you as often as today allows.",
      ),
    )
  })

  it("saves the search profile", async () => {
    const api = mockApi({
      "GET /auth/me": { body: authResponse() },
      "GET /recommendations": { body: [] },
      "GET /recommendations/profile": { body: PROFILE },
      "PUT /recommendations/profile": { body: { ...PROFILE, title_keywords: ["SRE", "DevOps"] } },
    })
    show(<RecommendationsPage />, "/jobs-for-you")
    const user = userEvent.setup()
    await user.click(await screen.findByRole("button", { name: /search profile/i }))
    const titles = await screen.findByLabelText("Job titles")
    await user.clear(titles)
    await user.type(titles, "SRE, DevOps")
    await user.click(screen.getByRole("button", { name: "Save" }))
    await waitFor(() => expect(api.called("PUT", "/recommendations/profile")).toHaveLength(1))
    expect(api.called("PUT", "/recommendations/profile")[0]?.body).toEqual({
      title_keywords: ["SRE", "DevOps"],
      locations: ["Bengaluru"],
      min_vector_score: 0.55,
    })
  })
})
