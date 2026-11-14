import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, screen, waitFor } from "@testing-library/react-native";
import { router } from "expo-router";
import { SafeAreaProvider } from "react-native-safe-area-context";

import type { JobCardData, MatchCardData } from "@/api/chat";
import type { MatchResult, Recommendation } from "@/api/matching";
import type { Opportunity } from "@/api/types";
import RecommendationsScreen from "@/app/(app)/recommendations";
import { ResumeFitSection } from "@/features/detail/resume-fit-section";
import { AttachmentList } from "@/features/assistant/job-cards";
import { renderWithTheme } from "@/test/render";

jest.mock("expo-web-browser", () => ({ openBrowserAsync: jest.fn() }));
jest.mock("expo-router", () => ({ router: { push: jest.fn() } }));

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
};
const OPP = {
  id: 5,
  company: "Zepto",
  role: "Backend Engineer",
  fit_score: null,
} as Opportunity;

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
};
const REC: Recommendation = {
  id: 3,
  job: JOB,
  vector_score: 0.74,
  best_resume_id: 2,
  best_resume_label: "Backend",
  created_at: "2026-11-14T10:00:00Z",
};
const PROFILE = {
  title_keywords: ["Backend Engineer"],
  locations: ["Bengaluru"],
  work_modes: [],
  min_vector_score: 0.55,
  enabled: true,
  last_refreshed_at: null,
};

type Route = (init: RequestInit | undefined) => {
  status?: number;
  body: unknown;
};

/** A fake API: "METHOD /path" -> reply. Unknown requests fail the test. */
function fakeApi(routes: Record<string, Route>) {
  const calls: { method: string; path: string; body: unknown }[] = [];
  global.fetch = jest.fn(
    async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input));
      const path = url.pathname.replace(/^\/api\/v1/, "");
      const method = (init?.method ?? "GET").toUpperCase();
      calls.push({
        method,
        path,
        body:
          typeof init?.body === "string" ? JSON.parse(init.body) : undefined,
      });
      const route = routes[`${method} ${path}`];
      if (!route) throw new Error(`Unmocked request: ${method} ${path}`);
      const reply = route(init);
      return new Response(
        reply.status === 204 ? null : JSON.stringify(reply.body),
        { status: reply.status ?? 200 },
      );
    },
  ) as unknown as typeof fetch;
  return calls;
}

async function show(ui: React.ReactElement) {
  const client = new QueryClient({
    defaultOptions: {
      queries: { gcTime: Infinity, retry: false },
      mutations: { retry: false, gcTime: Infinity },
    },
  });
  return renderWithTheme(
    <SafeAreaProvider
      initialMetrics={{
        frame: { x: 0, y: 0, width: 390, height: 844 },
        insets: { top: 0, left: 0, right: 0, bottom: 0 },
      }}
    >
      <QueryClientProvider client={client}>{ui}</QueryClientProvider>
    </SafeAreaProvider>,
  );
}

describe("resume fit", () => {
  it("compares the resumes, shows the breakdown and saves the best score", async () => {
    const calls = fakeApi({
      "GET /chat/config": () => ({ body: { enabled: true, matching: true } }),
      "GET /opportunities/5/match": () => ({ body: null }),
      "POST /opportunities/5/match": () => ({ body: RESULT }),
      "PATCH /opportunities/5": () => ({ body: { ...OPP, fit_score: 82 } }),
    });
    await show(<ResumeFitSection opportunity={OPP} />);

    await fireEvent.press(
      await screen.findByRole("button", { name: "Compare my resumes" }),
    );

    expect(await screen.findByText("82/100")).toBeTruthy();
    expect(screen.getByText("Best fit")).toBeTruthy();
    expect(screen.getByText("Kubernetes")).toBeTruthy();
    expect(screen.getByText("• Add Kubernetes work.")).toBeTruthy();
    expect(
      calls.find((c) => c.method === "POST" && c.path.endsWith("/match"))?.body,
    ).toEqual({ force: false });

    await fireEvent.press(
      screen.getByRole("button", { name: "Use 82 as fit score" }),
    );
    await waitFor(() =>
      expect(calls.some((c) => c.method === "PATCH")).toBe(true),
    );
    expect(calls.find((c) => c.method === "PATCH")?.body).toEqual({
      fit_score: 82,
    });
  });

  it("is hidden when matching isn't available", async () => {
    fakeApi({
      "GET /chat/config": () => ({ body: { enabled: true, matching: false } }),
    });
    await show(<ResumeFitSection opportunity={OPP} />);
    await waitFor(() =>
      expect(screen.queryByText("Which resume fits?")).toBeNull(),
    );
  });

  it("renders a match card in chat and opens the opportunity", async () => {
    const match: MatchCardData = { type: "match", ...RESULT };
    await show(<AttachmentList items={[match]} />);
    expect(
      screen.getByText("Resume fit · Zepto — Backend Engineer"),
    ).toBeTruthy();
    await fireEvent.press(
      screen.getByRole("button", { name: "Open opportunity" }),
    );
    expect(router.push).toHaveBeenCalledWith({
      pathname: "/opportunity/[id]",
      params: { id: 5 },
    });
  });
});

describe("Jobs for you", () => {
  it("lists ranked jobs and dismisses one", async () => {
    let dismissed = false;
    const calls = fakeApi({
      "GET /recommendations": () => ({ body: dismissed ? [] : [REC] }),
      "GET /recommendations/profile": () => ({ body: PROFILE }),
      "POST /recommendations/3/dismiss": () => {
        dismissed = true;
        return { status: 204, body: null };
      },
    });
    await show(<RecommendationsScreen />);
    expect(await screen.findByText("Platform Engineer")).toBeTruthy();
    expect(screen.getByText("74% similar · best resume: Backend")).toBeTruthy();

    await fireEvent.press(screen.getByRole("button", { name: "Dismiss" }));
    await waitFor(() =>
      expect(calls.some((c) => c.path === "/recommendations/3/dismiss")).toBe(
        true,
      ),
    );
    expect(await screen.findByText("No recommendations yet")).toBeTruthy();
  });
});
