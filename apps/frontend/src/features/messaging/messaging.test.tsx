import { screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"

import type { DraftCardData } from "@/api/chat"
import type {
  MessagePreview,
  MessageTemplate,
  OutreachProfile,
  SentMessage,
  Suggestions,
} from "@/api/messaging"
import type { Opportunity } from "@/api/types"
import { AttachmentList } from "@/features/assistant/job-cards"
import { ProtectedRoute } from "@/features/auth/route-guards"
import { apiError, authResponse, mockApi } from "@/test/mock-api"
import { renderRoutes } from "@/test/render"
import { MessageCard } from "./message-card"
import { MessageDialog } from "./message-dialog"
import { OutreachProfileCard } from "./outreach-profile-card"
import { TemplatesTab } from "./templates-tab"

const toasts = vi.hoisted(() => ({ error: vi.fn(), success: vi.fn(), info: vi.fn() }))
vi.mock("sonner", () => ({ toast: toasts }))

const OPP = { id: 5, company: "Zepto", role: "Backend Engineer" }

const BODY =
  "Hi Riya,\n\nI applied for the Backend Engineer role at Zepto and wanted to check in.\n\nBalaji"
const preview = (overrides: Partial<MessagePreview> = {}): MessagePreview => ({
  template_key: "sys:follow_up_1",
  template_name: "Follow-up 1: checking in",
  channel: "email",
  to: "riya@zepto.example",
  to_name: "Riya Sharma",
  from_email: "me@work.example",
  subject: "Following up: Backend Engineer application, Balaji",
  body: BODY,
  missing: [],
  char_count: BODY.length,
  char_limit: null,
  warnings: [],
  tips: ["Keep it short and polite."],
  attach: { resume_id: 2, label: "Backend v3", score: 85, has_file: true },
  edited: false,
  ...overrides,
})

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
  {
    key: "sys:thank_you_screening",
    source: "system",
    group: "screening",
    group_label: "Screening",
    name: "Thank you after a recruiter call",
    summary: "Within 24 hours of a call.",
    stages: ["screening"],
    recipients: ["recruiter"],
    india_only: false,
    tips: [],
    archived: false,
    variants: [
      { channel: "email", subject: "Thank you", body: "Thanks", edited: false, template_id: null },
    ],
  },
]

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
}

const SENT = {
  message: { id: 9, template_key: "sys:follow_up_1" },
  followup_closed_id: 3,
  next_followup_id: 4,
  next_followup_due: "2026-11-27",
  already_recorded: false,
}

function show(element: React.ReactNode) {
  return renderRoutes(
    [
      { path: "/login", element: <p>Login page</p> },
      {
        element: <ProtectedRoute />,
        children: [
          { path: "/a", element },
          { path: "/contacts", element: <p>Contacts page</p> },
          { path: "/opportunities/:id", element: <p>Opportunity page</p> },
        ],
      },
    ],
    { route: "/a" },
  )
}

const base = {
  "GET /auth/me": { body: authResponse() },
  "GET /messages/templates": { body: TEMPLATES },
  "GET /opportunities/5/messages/suggestions": { body: SUGGESTIONS },
  "GET /opportunities/5/messages": { body: [] as SentMessage[] },
}

afterEach(() => vi.restoreAllMocks())

describe("Message dialog", () => {
  it("opens on the suggested message, filled in, and hands it to the mail app", async () => {
    const clicks: string[] = []
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (
      this: HTMLAnchorElement,
    ) {
      clicks.push(this.href)
    })
    const api = mockApi({
      ...base,
      "POST /opportunities/5/messages/preview": { body: preview() },
      "POST /opportunities/5/messages/sent": { status: 201, body: SENT },
    })
    show(<MessageDialog opportunity={OPP} open onOpenChange={() => undefined} />)
    const user = userEvent.setup()

    const subject = await screen.findByLabelText("Subject")
    expect(subject).toHaveValue("Following up: Backend Engineer application, Balaji")
    expect(screen.getByLabelText("Message")).toHaveValue(BODY)
    expect(screen.getByText("6 working days since you applied with no reply.")).toBeInTheDocument()
    expect(screen.getByText("me@work.example")).toBeInTheDocument()
    expect(screen.getByText("riya@zepto.example")).toBeInTheDocument()
    expect(api.called("POST", "/opportunities/5/messages/preview")[0]?.body).toEqual({
      template_key: "sys:follow_up_1",
      channel: "email",
      contact_id: 1,
    })
    expect(screen.getByRole("link", { name: "Backend v3" })).toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: /open in email/i }))
    expect(clicks).toHaveLength(1)
    const mailto = decodeURIComponent(clicks[0] ?? "")
    expect(mailto).toContain(
      "mailto:riya@zepto.example?subject=Following up: Backend Engineer application, Balaji",
    )
    expect(mailto).toContain("Hi Riya,")

    await user.click(screen.getByRole("button", { name: "I sent it" }))
    await waitFor(() =>
      expect(api.called("POST", "/opportunities/5/messages/sent")).toHaveLength(1),
    )
    const sent = api.called("POST", "/opportunities/5/messages/sent")[0]?.body as Record<
      string,
      unknown
    >
    expect(sent).toMatchObject({
      template_key: "sys:follow_up_1",
      channel: "email",
      contact_id: 1,
      subject: "Following up: Backend Engineer application, Balaji",
      body: BODY,
      schedule_next: true,
    })
    expect(String(sent.request_id)).toMatch(/^[0-9a-f-]{36}$/)
    await waitFor(() =>
      expect(toasts.success).toHaveBeenCalledWith("Logged as sent", expect.anything()),
    )
  })

  it("keeps the user's edits and sends exactly what is on screen", async () => {
    const api = mockApi({
      ...base,
      "POST /opportunities/5/messages/preview": { body: preview() },
      "POST /opportunities/5/messages/sent": { status: 201, body: SENT },
    })
    show(<MessageDialog opportunity={OPP} open onOpenChange={() => undefined} />)
    const user = userEvent.setup()
    const message = await screen.findByLabelText("Message")
    await user.clear(message)
    await user.type(message, "My own words")
    await user.click(screen.getByRole("button", { name: "I sent it" }))
    await waitFor(() =>
      expect(api.called("POST", "/opportunities/5/messages/sent")).toHaveLength(1),
    )
    expect(
      (api.called("POST", "/opportunities/5/messages/sent")[0]?.body as { body: string }).body,
    ).toBe("My own words")
  })

  it("won't record a draft with gaps until they are filled or confirmed", async () => {
    const gappy = "Hi Riya, I enjoyed learning about [[something specific you discussed]]. Thanks"
    const api = mockApi({
      ...base,
      "POST /opportunities/5/messages/preview": {
        body: preview({
          body: gappy,
          subject: "Thank you",
          missing: [{ name: "talking_point", label: "something specific you discussed" }],
          warnings: ["Fill in the highlighted gaps before you send this."],
        }),
      },
      "POST /opportunities/5/messages/sent": { status: 201, body: SENT },
    })
    show(<MessageDialog opportunity={OPP} open onOpenChange={() => undefined} />)
    const user = userEvent.setup()
    await screen.findByLabelText("Message")

    await user.click(screen.getByRole("button", { name: "I sent it" }))
    expect(screen.getByRole("alert")).toHaveTextContent("still has highlighted gaps")
    expect(api.called("POST", "/opportunities/5/messages/sent")).toHaveLength(0)

    const field = screen.getByLabelText("something specific you discussed")
    await user.type(field, "the payments roadmap")
    await user.click(screen.getByRole("button", { name: "Insert" }))
    expect(screen.getByLabelText("Message")).toHaveValue(
      "Hi Riya, I enjoyed learning about the payments roadmap. Thanks",
    )
    expect(screen.queryByText("Fill in the gaps")).not.toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: /I sent it|Mark sent anyway/ }))
    await waitFor(() =>
      expect(api.called("POST", "/opportunities/5/messages/sent")).toHaveLength(1),
    )
  })

  it("copies the message and opens LinkedIn for a LinkedIn message", async () => {
    const open = vi.spyOn(window, "open").mockReturnValue(null)
    const api = mockApi({
      ...base,
      "POST /opportunities/5/messages/preview": (call) => ({
        body:
          (call.body as { channel: string }).channel === "linkedin"
            ? preview({
                channel: "linkedin",
                subject: null,
                body: "Hi Riya, quick check-in.",
                to: "https://linkedin.com/in/riya",
              })
            : preview(),
      }),
      "POST /opportunities/5/messages/sent": { status: 201, body: SENT },
    })
    show(<MessageDialog opportunity={OPP} open onOpenChange={() => undefined} />)
    const user = userEvent.setup()
    await screen.findByLabelText("Subject")
    await user.click(screen.getByRole("button", { name: "LinkedIn message" }))
    await waitFor(() => expect(screen.queryByLabelText("Subject")).not.toBeInTheDocument())
    await user.click(await screen.findByRole("button", { name: /copy and open linkedin/i }))
    expect(await navigator.clipboard.readText()).toBe("Hi Riya, quick check-in.")
    expect(open).toHaveBeenCalledWith(
      "https://linkedin.com/in/riya",
      "_blank",
      "noopener,noreferrer",
    )

    await user.click(screen.getByRole("button", { name: "I sent it" }))
    await waitFor(() =>
      expect(api.called("POST", "/opportunities/5/messages/sent")).toHaveLength(1),
    )
    expect(
      (api.called("POST", "/opportunities/5/messages/sent")[0]?.body as { channel: string })
        .channel,
    ).toBe("linkedin")
  })

  it("rewrites with AI, can undo, and explains a refused rewrite", async () => {
    let call = 0
    mockApi({
      ...base,
      "POST /opportunities/5/messages/preview": { body: preview() },
      "POST /opportunities/5/messages/polish": () => {
        call += 1
        return call === 1
          ? {
              body: {
                subject: "Quick check-in",
                body: "Short version.",
                changed: true,
                notice: null,
              },
            }
          : {
              body: {
                subject: null,
                body: BODY,
                changed: false,
                notice: "The rewrite added a number that was not in your draft.",
              },
            }
      },
    })
    show(<MessageDialog opportunity={OPP} open onOpenChange={() => undefined} />)
    const user = userEvent.setup()
    await screen.findByLabelText("Message")

    await user.click(screen.getByRole("button", { name: /improve with ai/i }))
    await user.click(await screen.findByRole("menuitem", { name: "Make it shorter" }))
    await waitFor(() => expect(screen.getByLabelText("Message")).toHaveValue("Short version."))
    expect(screen.getByLabelText("Subject")).toHaveValue("Quick check-in")

    await user.click(screen.getByRole("button", { name: /undo rewrite/i }))
    expect(screen.getByLabelText("Message")).toHaveValue(BODY)

    await user.click(screen.getByRole("button", { name: /improve with ai/i }))
    await user.click(await screen.findByRole("menuitem", { name: "Warmer tone" }))
    await waitFor(() =>
      expect(toasts.info).toHaveBeenCalledWith(
        "The rewrite added a number that was not in your draft.",
      ),
    )
    expect(screen.getByLabelText("Message")).toHaveValue(BODY)
  })

  it("tells the user to add a contact when there is nobody to write to", async () => {
    mockApi({
      ...base,
      "GET /opportunities/5/messages/suggestions": {
        body: {
          suggestions: [
            {
              kind: "add_contact",
              template_key: null,
              channel: null,
              contact_id: null,
              title: "Add someone",
              reason: "Add the recruiter to this opportunity, then message them.",
              due: false,
            },
          ],
          contacts: [],
        },
      },
      "POST /opportunities/5/messages/preview": {
        body: preview({
          to: null,
          to_name: null,
          warnings: ["Choose who this goes to, or add a contact to this opportunity."],
        }),
      },
    })
    show(<MessageDialog opportunity={OPP} open onOpenChange={() => undefined} />)
    expect(await screen.findByText(/Add the recruiter to this opportunity/)).toBeInTheDocument()
    expect(await screen.findByText(/Choose who this goes to/)).toBeInTheDocument()
  })
})

describe("Message card", () => {
  const opp = { ...OPP, stage: "applied" } as Opportunity

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
    ]
    const api = mockApi({
      ...base,
      "GET /opportunities/5/messages": { body: sent },
      "POST /messages/9/replied": { body: { ...sent[0], replied_at: "2026-11-12T10:00:00Z" } },
    })
    show(<MessageCard opportunity={opp} />)
    expect(await screen.findByText("Next: Follow-up 1: checking in")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /write it/i })).toBeInTheDocument()
    const list = await screen.findByRole("list", { name: "Messages you sent" })
    await userEvent.setup().click(within(list).getByRole("button", { name: "They replied" }))
    await waitFor(() => expect(api.called("POST", "/messages/9/replied")).toHaveLength(1))
  })

  it("says so when nothing is due", async () => {
    mockApi({
      ...base,
      "GET /opportunities/5/messages/suggestions": { body: { suggestions: [], contacts: [] } },
    })
    show(<MessageCard opportunity={opp} />)
    expect(await screen.findByText(/Nothing is due/)).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /write a message/i })).toBeInTheDocument()
  })
})

describe("Templates tab", () => {
  it("edits a built-in as the user's own copy, and restores the original", async () => {
    const edited: MessageTemplate[] = TEMPLATES.map((t) =>
      t.key === "sys:follow_up_1"
        ? { ...t, variants: [{ ...t.variants[0]!, edited: true, template_id: 11 }, t.variants[1]!] }
        : t,
    )
    let current = TEMPLATES
    const api = mockApi({
      ...base,
      "GET /messages/templates": () => ({ body: current }),
      "POST /messages/templates": () => {
        current = edited
        return { status: 201, body: edited[0] }
      },
      "DELETE /messages/templates/11": () => {
        current = TEMPLATES
        return { status: 204 }
      },
    })
    show(<TemplatesTab />)
    const user = userEvent.setup()
    await user.click(
      await screen.findByRole("button", { name: "Edit Follow-up 1: checking in (Email)" }),
    )
    const body = await screen.findByLabelText("Message")
    await user.clear(body)
    await user.type(body, "Hello again")
    await user.click(screen.getByRole("button", { name: "Save" }))
    await waitFor(() => expect(api.called("POST", "/messages/templates")).toHaveLength(1))
    expect(api.called("POST", "/messages/templates")[0]?.body).toMatchObject({
      base_key: "follow_up_1",
      channel: "email",
      body: "Hello again",
      subject: "Following up",
    })

    await user.click(
      await screen.findByRole("button", { name: /restore the original follow-up 1/i }),
    )
    await waitFor(() => expect(api.called("DELETE", "/messages/templates/11")).toHaveLength(1))
  })

  it("creates a template and shows the server's explanation of a mistake", async () => {
    const api = mockApi({
      ...base,
      "POST /messages/templates": apiError(422, "unknown_field", "Unknown field {{nonsense}}."),
    })
    show(<TemplatesTab />)
    const user = userEvent.setup()
    await user.click(await screen.findByRole("button", { name: /new template/i }))
    await user.type(await screen.findByLabelText("Name"), "Mine")
    await user.type(screen.getByLabelText("Subject"), "Hello")
    await user.type(screen.getByLabelText("Message"), "Hi there")
    await user.click(screen.getByRole("button", { name: "Save" }))
    expect(await screen.findByRole("alert")).toHaveTextContent("Unknown field")
    expect(api.called("POST", "/messages/templates")[0]?.body).toMatchObject({
      name: "Mine",
      channel: "email",
      subject: "Hello",
      body: "Hi there",
    })
  })
})

describe("Outreach profile", () => {
  const PROFILE: OutreachProfile = {
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
    suggested_headline: "a senior engineer with 4 years of experience",
  }

  it("saves the details, including the send-from address, and offers a headline from the resume", async () => {
    const api = mockApi({
      "GET /auth/me": { body: authResponse() },
      "GET /messages/profile": { body: PROFILE },
      "PUT /messages/profile": (call) => ({ body: { ...PROFILE, ...(call.body as object) } }),
    })
    show(<OutreachProfileCard />)
    const user = userEvent.setup()
    const from = await screen.findByLabelText("Send from (email)")
    expect(from).toHaveValue("acct@example.com")
    await user.clear(from)
    await user.type(from, "me@work.example")
    await user.click(screen.getByRole("button", { name: /use “a senior engineer/i }))
    await user.type(screen.getByLabelText("Notice period"), "30 days")
    await user.type(screen.getByLabelText("Achievement 1"), "Cut latency 40%.")
    await user.click(screen.getByRole("button", { name: "Save details" }))
    await waitFor(() => expect(api.called("PUT", "/messages/profile")).toHaveLength(1))
    expect(api.called("PUT", "/messages/profile")[0]?.body).toMatchObject({
      from_email: "me@work.example",
      headline: "a senior engineer with 4 years of experience",
      notice_period: "30 days",
      proof_points: ["Cut latency 40%."],
      india_style: true,
    })
  })

  it("refuses a bad email or a link that isn't http(s)", async () => {
    const api = mockApi({
      "GET /auth/me": { body: authResponse() },
      "GET /messages/profile": { body: PROFILE },
    })
    show(<OutreachProfileCard />)
    const user = userEvent.setup()
    const from = await screen.findByLabelText("Send from (email)")
    await user.clear(from)
    await user.type(from, "not-an-email")
    await user.type(screen.getByLabelText("LinkedIn profile link"), "javascript:alert(1)")
    await user.click(screen.getByRole("button", { name: "Save details" }))
    expect(await screen.findByText("Enter a valid email address")).toBeInTheDocument()
    expect(screen.getByText("Must start with http:// or https://")).toBeInTheDocument()
    expect(api.called("PUT", "/messages/profile")).toHaveLength(0)
  })
})

describe("Draft card in chat", () => {
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
    body: "Hi Riya,\n\nI'm interested in the role.",
    missing: ["one achievement"],
  }

  it("shows the draft and what is still to fill in, and opens the composer on it", async () => {
    const api = mockApi({
      ...base,
      "POST /opportunities/5/messages/preview": {
        body: preview({ template_key: "sys:recruiter_intro", template_name: draft.template_name }),
      },
    })
    show(<AttachmentList items={[draft]} />)
    expect(await screen.findByText(/Draft · Introduce yourself to a recruiter/)).toBeInTheDocument()
    expect(screen.getByText("Subject: Backend Engineer at Zepto: Balaji")).toBeInTheDocument()
    expect(screen.getByText("Still to fill in: one achievement")).toBeInTheDocument()
    await userEvent.setup().click(screen.getByRole("button", { name: "Edit and send" }))
    expect(await screen.findByLabelText("Message")).toBeInTheDocument()
    expect(api.called("POST", "/opportunities/5/messages/preview")[0]?.body).toMatchObject({
      template_key: "sys:recruiter_intro",
      channel: "email",
    })
  })
})
