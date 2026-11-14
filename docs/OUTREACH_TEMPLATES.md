# Outreach messages: follow-ups for email and LinkedIn

A job seeker usually loses to silence, not to a bad interview: they apply and never follow up,
nudge too early or too often, send the same generic note to everyone, or forget to say thanks.
This feature turns each opportunity's stage, age and contact into a ready-to-send message, hands
it to the user's own mail app or LinkedIn, then records that it was sent so the pipeline stays true.

## What it does and does not do

- **It never sends anything.** There is no sending service, and sending from the user's own
  address would need Gmail or Outlook sign-in. The user's mail app or LinkedIn sends; they read
  every message first.
- **Email**: a `mailto:` link pre-fills To, Subject and Body. A mailto link **cannot attach a
  file** (the sheet names the best-fit resume to attach) and **cannot choose the sending
  account**. The *Send from* address signs the message and picks the Google account in the
  Gmail compose link (`authuser`). Over about 1,900 characters the text is copied instead,
  because some mail clients drop long links.
- **LinkedIn** has no link that pre-fills a message, for anyone. The text is copied and the
  contact's profile (or a people search) is opened. A connection-request note is limited to about
  300 characters (LinkedIn has changed this before; the value is `LINKEDIN_NOTE_MAX_CHARS`).
- **It cannot tell whether a message was sent or answered.** "I sent it" and "They replied" are
  explicit one-tap actions. Follow-up closing and reply-rate results depend on them.

## The templates (14 ready-made, India-first with a neutral option)

Each has an email version and, where it makes sense, a short LinkedIn version.

| Group | Template | When |
|---|---|---|
| Reach out | Ask for a referral | someone you know works there |
| | Introduce yourself to a recruiter | an open role, before you apply |
| | LinkedIn connection note (300 chars) | with a connection request |
| After applying | I've applied: a quick introduction | right after you apply |
| | Follow-up 1: checking in | about 5 working days with no reply |
| | Follow-up 2: with something new | 7 working days after follow-up 1 |
| | Closing the loop | 7 working days after follow-up 2 |
| Screening | Thank you after a recruiter call | within 24 hours of the call |
| | Share notice period and CTC *(India)* | a recruiter asks for them |
| Interviewing | Thank you after an interview | within 24 hours of any round |
| | No decision yet: checking in | about 5 working days after |
| Offer | Acknowledge the offer and ask for time | within 24 hours |
| | Discuss the compensation | you want to negotiate |
| Closing | Reply gracefully to a rejection | you were turned down |

More are planned as content-only additions (no code change): referral thank-you, hiring-manager
intro, career-switch coffee chat, interview slot confirm and reschedule, accept and decline an
offer, withdraw, ghosted last nudge, re-engage after months.

Career switchers and returners need no separate library: the profile holds an optional one-line
*career switch* bridge that introductions include only when it is filled in.

## How a job seeker should use it (built into the suggestions)

- **Cadence**: follow up about 5 working days after applying; again 7 working days later with
  something new; once more 7 days after that; then stop. After three unanswered messages the
  app suggests marking the opportunity ghosted. Thank people within 24 hours of any call or
  interview. Acknowledge an offer within a day. (Numbers: `app/services/rules.py`.)
- **Never spam**: nobody is suggested a message within 3 days of the last one to them.
- **Who to write to**: a referrer first, then the recruiter or HR, then the hiring manager.
- **Content**: one ask, one proof point, under 150 words, the person's name in the greeting,
  something specific from the conversation for thank-yous (the draft leaves a visible gap for
  it), a plain respectful tone. Send Tuesday to Thursday morning. Attach one resume.

## How it works

- `app/messaging/render.py`: a tiny template grammar (`{{field}}`, `{{field|fallback}}`,
  `{{?field}}…{{/}}`). No code runs; values can't inject template syntax. A missing value shows
  as a gap like `[[something specific you discussed]]` that the app asks the user to fill.
- `app/messaging/catalog.py`: the templates as data; a test enforces word counts, the connect-note
  limit, known fields and a subject on every email.
- `app/messaging/suggest.py`: stage and elapsed working days to "what next and why".
- `app/services/messaging.py`: preview, suggestions, sent/replied, custom templates, polish, stats.
- Data (migration `0012`): `outreach_profiles` (sender details), `message_templates` (the user's
  own or edited copies; deleting one restores the original), `outreach_messages` (a snapshot of
  every message marked sent, with the reply time).
- API: `/messages/templates`, `/messages/profile`, `/messages/stats`, `/messages/{id}/replied`,
  `/opportunities/{id}/messages` (+ `/suggestions`, `/preview`, `/polish`, `/sent`).
- Assistant tool `draft_message` returns a draft card. It cannot send; the user does.

## AI polish and its limits

"Improve with AI" (shorter, warmer, more formal, more direct, fix grammar) uses the free models
and counts against `MESSAGE_POLISH_DAILY_LIMIT`. The assistant opt-out switches it off. The
rewrite is checked before it is shown: it is refused if it adds a number, a link, an email
address or a new proper name, drops a gap, or changes the length too much. **A check can't catch
every invented claim in plain words**, so the original is always one tap away (Undo) and nothing
is sent without the user reading it.

## Settings

`MESSAGE_POLISH_DAILY_LIMIT` (default 20), `MESSAGE_TEMPLATES_MAX` (default 50).
