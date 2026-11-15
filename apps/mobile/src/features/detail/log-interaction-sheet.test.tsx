import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, screen, waitFor } from "@testing-library/react-native";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { renderWithTheme } from "@/test/render";
import { LogInteractionSheet } from "./log-interaction-sheet";

const calls: { method: string; path: string; body: unknown }[] = [];

beforeEach(() => {
  calls.length = 0;
  global.fetch = jest.fn(
    async (input: RequestInfo | URL, init?: RequestInit) => {
      calls.push({
        method: (init?.method ?? "GET").toUpperCase(),
        path: new URL(String(input)).pathname.replace(/^\/api\/v1/, ""),
        body:
          typeof init?.body === "string" ? JSON.parse(init.body) : undefined,
      });
      return new Response(JSON.stringify({ id: 1 }), { status: 201 });
    },
  ) as unknown as typeof fetch;
});

async function show() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return renderWithTheme(
    <SafeAreaProvider
      initialMetrics={{
        frame: { x: 0, y: 0, width: 390, height: 844 },
        insets: { top: 0, left: 0, right: 0, bottom: 0 },
      }}
    >
      <QueryClientProvider client={client}>
        <LogInteractionSheet
          visible
          onClose={() => undefined}
          opportunityId={5}
        />
      </QueryClientProvider>
    </SafeAreaProvider>,
  );
}

const posts = () => calls.filter((c) => c.method === "POST");

describe("log activity sheet", () => {
  it("will not save without a summary", async () => {
    await show();
    await fireEvent.press(screen.getByText("Save"));
    expect(await screen.findByText("Say what happened")).toBeTruthy();
    expect(posts()).toHaveLength(0);
  });

  it("will not save a date in the future or a malformed one", async () => {
    await show();
    await fireEvent.changeText(
      screen.getByLabelText("What happened?"),
      "Spoke to HR",
    );
    const when = screen.getByPlaceholderText("YYYY-MM-DD");

    await fireEvent.changeText(when, "2999-01-01");
    await fireEvent.press(screen.getByText("Save"));
    expect(await screen.findByText("That date is in the future")).toBeTruthy();

    await fireEvent.changeText(when, "2026-13-40");
    await fireEvent.press(screen.getByText("Save"));
    expect(await screen.findByText("Enter a date as YYYY-MM-DD")).toBeTruthy();
    expect(posts()).toHaveLength(0);
  });

  it("saves a trimmed summary dated today (now) or an earlier day (midday)", async () => {
    await show();
    await fireEvent.changeText(
      screen.getByLabelText("What happened?"),
      "  Spoke to HR  ",
    );
    await fireEvent.press(screen.getByText("Save"));
    await waitFor(() => expect(posts()).toHaveLength(1));
    expect(posts()[0]?.body).toMatchObject({
      opportunity_id: 5,
      summary: "Spoke to HR",
      occurred_at: null,
    });

    await fireEvent.changeText(
      screen.getByPlaceholderText("YYYY-MM-DD"),
      "2026-11-10",
    );
    await fireEvent.press(screen.getByText("Save"));
    await waitFor(() => expect(posts()).toHaveLength(2));
    const body = posts()[1]?.body as { occurred_at: string };
    expect(new Date(body.occurred_at).getTime()).toBe(
      new Date("2026-11-10T12:00:00").getTime(),
    );
  });
});
