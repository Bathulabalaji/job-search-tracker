import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, screen, waitFor } from "@testing-library/react-native";

import { renderWithTheme } from "@/test/render";
import { AssistantPrivacySection } from "./assistant-privacy-section";

const USAGE = [
  {
    name: "messages",
    label: "Assistant messages",
    limit: 60,
    used: 12,
    resets_at: null,
  },
];

function fakeApi(state: { optedOut: boolean }) {
  const calls: { method: string; path: string; body: unknown }[] = [];
  global.fetch = jest.fn(
    async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = new URL(String(input)).pathname.replace(/^\/api\/v1/, "");
      const method = (init?.method ?? "GET").toUpperCase();
      calls.push({
        method,
        path,
        body:
          typeof init?.body === "string" ? JSON.parse(init.body) : undefined,
      });
      if (method === "PUT" && path === "/chat/preferences") {
        state.optedOut = (
          calls[calls.length - 1]!.body as { assistant_opt_out: boolean }
        ).assistant_opt_out;
      }
      const body =
        path === "/chat/usage"
          ? USAGE
          : { enabled: !state.optedOut, assistant_opt_out: state.optedOut };
      return new Response(JSON.stringify(body), { status: 200 });
    },
  ) as unknown as typeof fetch;
  return calls;
}

async function show() {
  const client = new QueryClient({
    defaultOptions: {
      queries: { gcTime: Infinity, retry: false },
      mutations: { retry: false, gcTime: Infinity },
    },
  });
  return renderWithTheme(
    <QueryClientProvider client={client}>
      <AssistantPrivacySection />
    </QueryClientProvider>,
  );
}

describe("assistant privacy section", () => {
  it("shows what is sent and today's allowances, and switches the assistant off", async () => {
    const calls = fakeApi({ optedOut: false });
    await show();
    expect(await screen.findByText(/Groq and Google/)).toBeTruthy();
    expect(await screen.findByText("12/60")).toBeTruthy();

    await fireEvent(
      screen.getByLabelText("Use the AI assistant"),
      "valueChange",
      false,
    );

    await waitFor(() =>
      expect(calls.some((c) => c.method === "PUT")).toBe(true),
    );
    expect(calls.find((c) => c.method === "PUT")?.body).toEqual({
      assistant_opt_out: true,
    });
    expect(await screen.findByText(/Off: no chat/)).toBeTruthy();
    expect(screen.queryByText("12/60")).toBeNull();
  });
});
