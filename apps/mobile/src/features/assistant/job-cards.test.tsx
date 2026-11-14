import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, screen, waitFor } from "@testing-library/react-native";
import * as WebBrowser from "expo-web-browser";

import type { JobCardData } from "@/api/chat";
import { renderWithTheme } from "@/test/render";
import { AttachmentList } from "./job-cards";

jest.mock("expo-web-browser", () => ({
  openBrowserAsync: jest.fn(async () => ({ type: "opened" })),
}));
jest.mock("expo-router", () => ({ router: { push: jest.fn() } }));

function job(overrides: Partial<JobCardData> = {}): JobCardData {
  return {
    type: "job",
    id: 7,
    title: "Backend Engineer",
    company: "Zepto",
    location: "Bengaluru",
    work_mode: "hybrid",
    source_site: "naukri",
    provider: "jsearch",
    apply_url: "https://www.naukri.com/job-listings-1",
    posted_at: new Date(Date.now() - 86_400_000).toISOString(),
    salary_text: null,
    active_status: "active",
    active_checked_at: null,
    tracked_opportunity_id: null,
    ...overrides,
  };
}

async function show(items: JobCardData[]) {
  const client = new QueryClient({
    // No garbage-collection timers, so Jest can exit as soon as the tests finish.
    defaultOptions: {
      queries: { gcTime: Infinity },
      mutations: { retry: false, gcTime: Infinity },
    },
  });
  return renderWithTheme(
    <QueryClientProvider client={client}>
      <AttachmentList items={items} />
    </QueryClientProvider>,
  );
}

describe("job cards", () => {
  it("shows source, freshness and link status, and opens only http links", async () => {
    await show([
      job(),
      job({
        id: 8,
        apply_url: "javascript:alert(1)",
        active_status: "unknown",
      }),
    ]);
    expect(screen.getAllByText("Naukri")).toHaveLength(2);
    expect(screen.getByText("Verified open")).toBeTruthy();
    expect(screen.getByText("Not verified")).toBeTruthy();
    expect(screen.getAllByText("Posted yesterday")).toHaveLength(2);
    const open = screen.getAllByRole("button", { name: "Open" });
    expect(open).toHaveLength(1);
    await fireEvent.press(open[0]!);
    expect(WebBrowser.openBrowserAsync).toHaveBeenCalledWith(
      "https://www.naukri.com/job-listings-1",
    );
  });

  it("tracks a job, then offers the opportunity", async () => {
    const fetchMock = jest.fn(
      async () =>
        new Response(JSON.stringify({ id: 31, company: "Zepto" }), {
          status: 201,
        }),
    );
    global.fetch = fetchMock as unknown as typeof fetch;
    await show([job()]);
    await fireEvent.press(screen.getByRole("button", { name: "Track" }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "In pipeline" })).toBeTruthy(),
    );
    const [url, init] = fetchMock.mock.calls[0] as unknown as [
      string,
      RequestInit,
    ];
    expect(url).toMatch(/\/jobs\/7\/track$/);
    expect(init.method).toBe("POST");
  });
});
