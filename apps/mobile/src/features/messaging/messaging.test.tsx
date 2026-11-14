import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, screen, waitFor } from "@testing-library/react-native";
import * as Clipboard from "expo-clipboard";
import { Linking } from "react-native";
import { SafeAreaProvider } from "react-native-safe-area-context";

import type { DraftCardData } from "@/api/chat";
import type {
  MessagePreview,
  MessageTemplate,
  OutreachProfile,
  SentMessage,
  Suggestions,
} from "@/api/messaging";
import TemplatesScreen from "@/app/(app)/templates";
import { AttachmentList } from "@/features/assistant/job-cards";
import type { Opportunity } from "@/api/types";
import { renderWithTheme } from "@/test/render";
import { MessageSection } from "./message-section";
import { MessageSheet } from "./message-sheet";
import { OutreachProfileSheet } from "./outreach-profile-sheet";

jest.mock("expo-clipboard", () => ({
  setStringAsync: jest.fn(async () => true),
}));
jest.mock("expo-router", () => ({ router: { push: jest.fn() } }));
jest.mock("expo-web-browser", () => ({ openBrowserAsync: jest.fn() }));

const OPP = { id: 5, company: "Zepto", role: "Backend Engineer" };
const BODY =
  "Hi Riya,\n\nI applied for the Backend Engineer role at Zepto and wanted to check in.\n\nBalaji";

const preview = (o: Partial<MessagePreview> = {}): MessagePreview => ({
  template_key: "sys:follow_up_1",
  template_name: "Follow-up 1: checking in",
  channel: "email",
  to: "riya@zepto.example",
  to_name: "Riya Sharma",
  from_email: "me@work.example",
  subject: "Following up: Backend Engineer application",
  body: BODY,
  missing: [],
  char_count: BODY.length,
  char_limit: null,
  warnings: [],
  tips: [],
  attach: { resume_id: 2, label: "Backend v3", score: 85, has_file: true },
  edited: false,
  ...o,
});

const TEMPLATES: MessageTemplate[] = [
  {
    key: "sys:follow_up_1",
    source: "system",
    group: "after_applying",
    group_label: "After applying",
    name: "Follow-up 1: checking in",
    summary: "About 5 working days after applying.",
    stages: ["applied"],
    recipients: ["recruiter"],
    india_only: false,
    tips: [],
    archived: false,
    variants: [
      {
        channel: "email",
        subject: "Following up",
        body: "Hi {{recipient_first}}",
        edited: false,
        template_id: null,
      },
      {
        channel: "linkedin",
        subject: null,
        body: "Hi {{recipient_first}}",
        edited: false,
        template_id: null,
      },
    ],
  },
];

const SUGGESTIONS: Suggestions = {
  suggestions: [
    {
      kind: "send",
      template_key: "sys:follow_up_1",
      channel: "email",
      contact_id: 1,
      title: "Follow-up 1: checking in",
      reason: "6 working days since you applied with no reply.",
      due: true,
    },
  ],
  contacts: [
    {
      id: 1,
      name: "Riya Sharma",
      role: "recruiter",
      email: "riya@zepto.example",
      linkedin_url: "https://linkedin.com/in/riya",
      last_messaged_days: null,
    },
  ],
};

type Reply = { status?: number; body: unknown };
type Route = (init: RequestInit | undefined, body: unknown) => Reply;

function fakeApi(routes: Record<string, Route | Reply>) {
  const calls: { method: string; path: string; body: unknown }[] = [];
  global.fetch = jest.fn(
    async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = new URL(String(input)).pathname.replace(/^\/api\/v1/, "");
      const method = (init?.method ?? "GET").toUpperCase();
      const body =
        typeof init?.body === "string"
          ? (JSON.parse(init.body) as unknown)
          : undefined;
      calls.push({ method, path, body });
      const route = routes[`${method} ${path}`];
      if (!route) throw new Error(`Unmocked request: ${method} ${path}`);
      const reply = typeof route === "function" ? route(init, body) : route;
      return new Response(
        reply.status === 204 ? null : JSON.stringify(reply.body),
        {
          status: reply.status ?? 200,
        },
      );
    },
  ) as unknown as typeof fetch;
  return {
    calls,
    called: (method: string, path: string) =>
      calls.filter((c) => c.method === method && c.path === path),
  };
}

const base = {
  "GET /messages/templates": { body: TEMPLATES },
  "GET /opportunities/5/messages/suggestions": { body: SUGGESTIONS },
  "GET /opportunities/5/messages": { body: [] as SentMessage[] },
};

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

beforeEach(() => {
  jest.spyOn(Linking, "openURL").mockResolvedValue(undefined as never);
  (Clipboard.setStringAsync as jest.Mock).mockClear();
});
afterEach(() => {
  jest.restoreAllMocks();
});

describe("message sheet", () => {
  it("opens on the suggested message, hands it to the mail app, and records it as sent", async () => {
    const api = fakeApi({
      ...base,
      "POST /opportunities/5/messages/preview": { body: preview() },
      "POST /opportunities/5/messages/sent": {
        status: 201,
        body: {
          message: { id: 9 },
          next_followup_due: "2026-11-27",
          followup_closed_id: 3,
          next_followup_id: 4,
          already_recorded: false,
        },
      },
    });
    await show(
      <MessageSheet opportunity={OPP} visible onClose={() => undefined} />,
    );

    expect(await screen.findByDisplayValue(BODY)).toBeTruthy();
    expect(
      screen.getByDisplayValue("Following up: Backend Engineer application"),
    ).toBeTruthy();
    expect(screen.getByText(/6 working days since you applied/)).toBeTruthy();
    expect(screen.getByText(/From me@work.example/)).toBeTruthy();
    expect(screen.getByText(/Attach your Backend v3 resume/)).toBeTruthy();
    expect(
      api.called("POST", "/opportunities/5/messages/preview")[0]?.body,
    ).toEqual({
      template_key: "sys:follow_up_1",
      channel: "email",
      contact_id: 1,
    });

    await fireEvent.press(
      screen.getByRole("button", { name: "Open in email" }),
    );
    await waitFor(() => expect(Linking.openURL).toHaveBeenCalledTimes(1));
    const opened = decodeURIComponent(
      (Linking.openURL as jest.Mock).mock.calls[0][0] as string,
    );
    expect(opened).toContain(
      "mailto:riya@zepto.example?subject=Following up: Backend Engineer application",
    );
    expect(opened).toContain("Hi Riya,");

    await fireEvent.press(screen.getByRole("button", { name: "I sent it" }));
    await waitFor(() =>
      expect(api.called("POST", "/opportunities/5/messages/sent")).toHaveLength(
        1,
      ),
    );
    expect(
      api.called("POST", "/opportunities/5/messages/sent")[0]?.body,
    ).toMatchObject({
      template_key: "sys:follow_up_1",
      channel: "email",
      contact_id: 1,
      body: BODY,
      schedule_next: true,
    });
  });

  it("sends exactly what the user edited", async () => {
    const api = fakeApi({
      ...base,
      "POST /opportunities/5/messages/preview": { body: preview() },
      "POST /opportunities/5/messages/sent": {
        status: 201,
        body: {
          message: { id: 9 },
          next_followup_due: null,
          followup_closed_id: null,
          next_followup_id: null,
          already_recorded: false,
        },
      },
    });
    await show(
      <MessageSheet opportunity={OPP} visible onClose={() => undefined} />,
    );
    await screen.findByDisplayValue(BODY);
    await fireEvent.changeText(
      screen.getByLabelText("Message"),
      "My own words",
    );
    await fireEvent.press(screen.getByRole("button", { name: "I sent it" }));
    await waitFor(() =>
      expect(api.called("POST", "/opportunities/5/messages/sent")).toHaveLength(
        1,
      ),
    );
    expect(
      (
        api.called("POST", "/opportunities/5/messages/sent")[0]?.body as {
          body: string;
        }
      ).body,
    ).toBe("My own words");
  });

  it("won't record a draft with gaps until they are filled or confirmed", async () => {
    const gappy =
      "Hi Riya, I enjoyed learning about [[something specific you discussed]]. Thanks";
    const api = fakeApi({
      ...base,
      "POST /opportunities/5/messages/preview": {
        body: preview({
          body: gappy,
          missing: [
            {
              name: "talking_point",
              label: "something specific you discussed",
            },
          ],
        }),
      },
      "POST /opportunities/5/messages/sent": {
        status: 201,
        body: {
          message: { id: 9 },
          next_followup_due: null,
          followup_closed_id: null,
          next_followup_id: null,
          already_recorded: false,
        },
      },
    });
    await show(
      <MessageSheet opportunity={OPP} visible onClose={() => undefined} />,
    );
    await screen.findByDisplayValue(gappy);

    await fireEvent.press(screen.getByRole("button", { name: "I sent it" }));
    expect(await screen.findByText(/still has gaps like/)).toBeTruthy();
    expect(api.called("POST", "/opportunities/5/messages/sent")).toHaveLength(
      0,
    );

    await fireEvent.changeText(
      screen.getByLabelText("something specific you discussed"),
      "the payments roadmap",
    );
    await fireEvent.press(screen.getByRole("button", { name: "Insert" }));
    expect(
      await screen.findByDisplayValue(
        "Hi Riya, I enjoyed learning about the payments roadmap. Thanks",
      ),
    ).toBeTruthy();
  });

  it("copies the message and opens LinkedIn for a LinkedIn message", async () => {
    fakeApi({
      ...base,
      "POST /opportunities/5/messages/preview": (_i, body) => ({
        body:
          (body as { channel: string }).channel === "linkedin"
            ? preview({
                channel: "linkedin",
                subject: null,
                body: "Hi Riya, quick check-in.",
              })
            : preview(),
      }),
    });
    await show(
      <MessageSheet opportunity={OPP} visible onClose={() => undefined} />,
    );
    await screen.findByDisplayValue(BODY);
    await fireEvent.press(screen.getByRole("button", { name: "LinkedIn" }));
    await fireEvent.press(
      await screen.findByRole("button", { name: "Copy and open LinkedIn" }),
    );
    await waitFor(() =>
      expect(Linking.openURL).toHaveBeenCalledWith(
        "https://linkedin.com/in/riya",
      ),
    );
    expect(Clipboard.setStringAsync).toHaveBeenCalledWith(
      "Hi Riya, quick check-in.",
    );
  });

  it("rewrites with AI and can undo", async () => {
    fakeApi({
      ...base,
      "POST /opportunities/5/messages/preview": { body: preview() },
      "POST /opportunities/5/messages/polish": {
        body: {
          subject: "Quick check-in",
          body: "Short version.",
          changed: true,
          notice: null,
        },
      },
    });
    await show(
      <MessageSheet opportunity={OPP} visible onClose={() => undefined} />,
    );
    await screen.findByDisplayValue(BODY);
    await fireEvent.press(
      screen.getByRole("button", { name: "Improve with AI" }),
    );
    await fireEvent.press(await screen.findByText("Make it shorter"));
    expect(await screen.findByDisplayValue("Short version.")).toBeTruthy();
    await fireEvent.press(screen.getByRole("button", { name: "Undo rewrite" }));
    expect(await screen.findByDisplayValue(BODY)).toBeTruthy();
  });
});

describe("message section", () => {
  const opp = { ...OPP, stage: "applied" } as Opportunity;

  it("shows what to send next and lets the user log a reply", async () => {
    const sent: SentMessage[] = [
      {
        id: 9,
        opportunity_id: 5,
        contact_id: 1,
        template_key: "sys:follow_up_1",
        channel: "email",
        subject: "S",
        body: "B",
        sent_at: "2026-11-10T10:00:00Z",
        replied_at: null,
        template_name: "Follow-up 1: checking in",
      },
    ];
    const api = fakeApi({
      ...base,
      "GET /opportunities/5/messages": { body: sent },
      "POST /messages/9/replied": {
        body: { ...sent[0], replied_at: "2026-11-12T10:00:00Z" },
      },
    });
    await show(<MessageSection opportunity={opp} />);
    expect(
      await screen.findByText("Next: Follow-up 1: checking in"),
    ).toBeTruthy();
    await fireEvent.press(
      await screen.findByRole("button", { name: "They replied" }),
    );
    await waitFor(() =>
      expect(api.called("POST", "/messages/9/replied")).toHaveLength(1),
    );
  });
});

describe("outreach details", () => {
  it("saves the send-from address and the other details", async () => {
    const profile: OutreachProfile = {
      from_email: "acct@example.com",
      headline: null,
      phone: null,
      linkedin_url: null,
      location: null,
      notice_period: null,
      current_ctc: null,
      expected_ctc: null,
      career_story: null,
      proof_points: [],
      india_style: true,
      suggested_headline: null,
    };
    const api = fakeApi({
      "GET /messages/profile": { body: profile },
      "PUT /messages/profile": (_i, body) => ({
        body: { ...profile, ...(body as object) },
      }),
    });
    await show(<OutreachProfileSheet visible onClose={() => undefined} />);
    const from = await screen.findByLabelText("Send from (email)");
    await fireEvent.changeText(from, "me@work.example");
    await fireEvent.changeText(
      screen.getByLabelText("Notice period"),
      "30 days",
    );
    await fireEvent.changeText(
      screen.getByLabelText("Achievement 1"),
      "Cut latency 40%.",
    );
    await fireEvent.press(screen.getByRole("button", { name: "Save" }));
    await waitFor(() =>
      expect(api.called("PUT", "/messages/profile")).toHaveLength(1),
    );
    expect(api.called("PUT", "/messages/profile")[0]?.body).toMatchObject({
      from_email: "me@work.example",
      notice_period: "30 days",
      proof_points: ["Cut latency 40%."],
      india_style: true,
    });
  });

  it("refuses a bad email", async () => {
    const api = fakeApi({
      "GET /messages/profile": {
        body: {
          from_email: "acct@example.com",
          headline: null,
          phone: null,
          linkedin_url: null,
          location: null,
          notice_period: null,
          current_ctc: null,
          expected_ctc: null,
          career_story: null,
          proof_points: [],
          india_style: true,
          suggested_headline: null,
        },
      },
    });
    await show(<OutreachProfileSheet visible onClose={() => undefined} />);
    await fireEvent.changeText(
      await screen.findByLabelText("Send from (email)"),
      "nope",
    );
    await fireEvent.press(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText("Enter a valid email address")).toBeTruthy();
    expect(api.called("PUT", "/messages/profile")).toHaveLength(0);
  });
});

describe("templates screen", () => {
  it("edits a built-in as the user's own copy", async () => {
    const api = fakeApi({
      ...base,
      "POST /messages/templates": { status: 201, body: TEMPLATES[0] },
    });
    await show(<TemplatesScreen />);
    expect(await screen.findByText("Follow-up 1: checking in")).toBeTruthy();
    await fireEvent.press(
      (await screen.findAllByRole("button", { name: "Edit" }))[0]!,
    );
    const body = await screen.findByLabelText("Message");
    await fireEvent.changeText(body, "Hello again");
    await fireEvent.press(screen.getByRole("button", { name: "Save" }));
    await waitFor(() =>
      expect(api.called("POST", "/messages/templates")).toHaveLength(1),
    );
    expect(api.called("POST", "/messages/templates")[0]?.body).toMatchObject({
      base_key: "follow_up_1",
      channel: "email",
      body: "Hello again",
      subject: "Following up",
    });
  });
});

describe("draft card in chat", () => {
  it("shows the draft and what is still to fill in, and opens the sheet on it", async () => {
    const draft: DraftCardData = {
      type: "draft",
      opportunity_id: 5,
      company: "Zepto",
      role: "Backend Engineer",
      template_key: "sys:recruiter_intro",
      template_name: "Introduce yourself to a recruiter",
      channel: "email",
      to: "riya@zepto.example",
      to_name: "Riya Sharma",
      subject: "Backend Engineer at Zepto: Balaji",
      body: "Hi Riya,\n\nI'm interested.",
      missing: ["one achievement"],
    };
    const api = fakeApi({
      ...base,
      "POST /opportunities/5/messages/preview": {
        body: preview({ template_key: "sys:recruiter_intro" }),
      },
    });
    await show(<AttachmentList items={[draft]} />);
    expect(
      screen.getByText(
        /Draft · Introduce yourself to a recruiter to Riya Sharma/,
      ),
    ).toBeTruthy();
    expect(screen.getByText("Still to fill in: one achievement")).toBeTruthy();
    await fireEvent.press(
      screen.getByRole("button", { name: "Edit and send" }),
    );
    await waitFor(() =>
      expect(
        api.called("POST", "/opportunities/5/messages/preview")[0]?.body,
      ).toMatchObject({
        template_key: "sys:recruiter_intro",
        channel: "email",
      }),
    );
  });
});
