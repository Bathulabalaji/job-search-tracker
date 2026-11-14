# Career Command Center

Job search tracker + analytics. Accounts are supported (email and password, or Google), and every account sees only its own data. See [docs/PROJECT_BRIEF.md](docs/PROJECT_BRIEF.md) for the full brief.

**Status:** feature-complete against the brief, plus accounts (see [Authentication and accounts](#authentication-and-accounts)). The backend covers opportunities, contacts, interactions, follow-ups (with `/move` and the follow-up auto-rule), daily logs, weekly targets, prep items, resumes, and the dashboard and analytics endpoints. The frontend has Today, Pipeline (kanban), Opportunity detail, Analytics, Daily log, Prep, Contacts & Resumes and the Cmd/Ctrl+K command palette.

```
apps/
  backend/    FastAPI + SQLAlchemy 2.0 + Alembic (managed with uv)
  frontend/   Vite + React + TypeScript + Tailwind + shadcn/ui
```

## Prerequisites

- Python 3.12 and [uv](https://docs.astral.sh/uv/)
- Node.js 20+ and npm
- PostgreSQL running locally (only needed for migrations; the health endpoint does not touch the DB)

## 1. Database (one-time)

Run from anywhere. Adjust the user to match your local Postgres.

```bash
createdb career_command_center
```

## 2. Backend

All commands run from **`apps/backend`**.

```bash
cd apps/backend
cp .env.example .env          # then edit DATABASE_URL to match your Postgres credentials
uv sync                       # create .venv and install dependencies
uv run uvicorn app.main:app --reload --port 8000
```

Layout: `app/api` (routers), `app/services`, `app/repositories`, `app/models`, `app/schemas`, `app/db` (engine, session, Base), `app/core` (config), `migrations/` (Alembic).

### Verify the backend

| Check | Directory | Command | Expected |
| --- | --- | --- | --- |
| Health endpoint | any | `curl http://localhost:8000/api/v1/health` | `{"status":"ok"}` |
| OpenAPI docs | browser | <http://localhost:8000/docs> | Swagger UI listing health, opportunities, contacts, interactions, followups |
| Tests | `apps/backend` | `uv run pytest` | 501 passed |
| Types | `apps/backend` | `uv run mypy` | `Success: no issues found` |
| Lint | `apps/backend` | `uv run ruff check .` | `All checks passed!` |
| Alembic connects | `apps/backend` | `uv run alembic current` | `0004 (head)` after you run the migration below |

### Migrations

From `apps/backend`:

```bash
uv run alembic upgrade head                                   # create/update tables (do this first)
uv run alembic current                                        # show the applied revision (expect 0004 (head))
uv run alembic downgrade base                                 # undo everything (dev only)
uv run alembic revision --autogenerate -m "describe change"   # after changing a model; review the file it writes
```

The database URL comes from `DATABASE_URL` in `.env`, not from `alembic.ini`. New model modules must be imported in `app/models/__init__.py` so autogenerate sees them.

### Seed sample data

Sample data belongs to an account, so create one first (register in the app, or use the CLI under [Operating accounts](#operating-accounts)). From `apps/backend`, after `alembic upgrade head`:

```bash
uv run python -m app.scripts.seed --user-email you@example.com            # seeds each empty section for that account
uv run python -m app.scripts.seed --user-email you@example.com --reset    # deletes THAT account's data first (ENVIRONMENT=local only)
```

The script has four independent sections, and each runs only if that account has none of it yet, so it is safe to re-run:

- **Opportunities:** 10 fictional opportunities across all stages, with contacts, interactions and follow-ups. Stages are reached through real moves, so the funnel has history. One applied opportunity has been silent for 26 days (ghosted suggestion), and one follow-up is overdue.
- **Activity:** 21 days of daily logs, including rest days, and this week's targets.
- **Prep:** 17 prep topics across all seven categories.
- **Resumes:** 3 sample resume versions.

### Run the tests

From `apps/backend`:

```bash
uv run pytest            # 501 tests
uv run pytest tests/unit # pure rules only, no database needed
```

Service and API tests need PostgreSQL. They use a separate `<database>_test` database on the same server (for example `career_command_center_test`). It is created if missing and **dropped and rebuilt from the Alembic migrations on every run**, so the tests also check the migrations. Each test runs in a transaction that is rolled back. Your dev data is never touched. Set `TEST_DATABASE_URL` to use a different server; its database name must end in `_test`.

### API summary (`/api/v1`, full docs at `/docs`)

Every endpoint except `/health` and the public `/auth/*` ones requires a signed-in session cookie, and every state-changing request must carry the `X-CSRF-Token` header. Each account only ever sees its own rows; another account's id returns 404.

| Resource | Endpoints |
| --- | --- |
| Opportunities | `GET/POST /opportunities`, `GET/PATCH/DELETE /opportunities/{id}`, `POST /opportunities/{id}/move` |
| Contacts | `GET/POST /contacts`, `GET/PATCH/DELETE /contacts/{id}` |
| Interactions | `GET/POST /interactions`, `GET/PATCH/DELETE /interactions/{id}` |
| Follow-ups | `GET/POST /followups`, `GET/PATCH/DELETE /followups/{id}` |
| Dashboard | `GET /dashboard/today` (follow-ups due or overdue, interviews today, top 3 next actions), `GET /dashboard/summary` (counts per stage, response rate, interviews this week) |
| Daily logs | `GET/POST /daily-logs`, `GET/PATCH/DELETE /daily-logs/{id}`, `GET /daily-logs/streak` |
| Weekly targets | `GET/POST /weekly-targets`, `GET/PATCH/DELETE /weekly-targets/{id}` |
| Prep items | `GET/POST /prep-items`, `GET/PATCH/DELETE /prep-items/{id}` |
| Auth | See [Authentication and accounts](#authentication-and-accounts) |
| Resumes | `GET/POST /resumes`, `GET/PATCH/DELETE /resumes/{id}` (`?q=` searches label, focus and file name) |
| Analytics | `GET /analytics/weekly?week_of=YYYY-MM-DD` (targets vs actual, daily points, 8-week trend, funnel, response rate by source, scorecard) |

List endpoints take `limit` and `offset`, plus filters (for example `?stage=applied&priority=1&q=acme`, `?opportunity_id=3`, `?status=pending&due_on_or_before=2026-11-13`).

Rules to know:

- **Stage changes only via `/move`.** `PATCH /opportunities/{id}` ignores `stage`, so the auto-rule cannot be bypassed.
- **Follow-up auto-rule.** Entering `applied` or `screening` (on create or move) adds a follow-up due in 2 working days (Mon-Fri, holidays not modelled). If the opportunity already has a pending follow-up, none is added.
- **Ghosted suggestion.** Opportunities in applied, screening, interview_scheduled or interviewing get `ghosted_suggestion: true` after 21 days without contact. It is a flag only; the stage is never changed automatically. `days_since_contact` counts from the last real interaction, or from creation if there is none.
- **Move records an interaction** of type `stage_change`. This type is an addition to the brief's list, and it does not count as contact.
- **Streak.** Counts consecutive days with any activity (any count above zero, or prep hours). A log full of zeros is a rest day and does not extend it. Today is not held against you until it ends: with nothing logged yet, the streak counts back from yesterday.
- **Daily logs and targets.** One daily log per date (a second `POST` returns 409). `week_start` of a target must be a Monday. A week with no target of its own reuses the most recent earlier one, and the response says so (`target_carried_over`).
- **Interviews in analytics** come from logged `interview` interactions, because daily logs have no interview column.
- **Funnel.** Counts how many opportunities *reached* each step (Found, Applied, Screening, Interview, Offer, Accepted), using stage history. Rejected, ghosted and parked are exits, so a rejection after Screening still counts as having reached Screening. History is stored as `from_stage` and `to_stage` on `stage_change` interactions. Migration `0002` backfills them from existing move summaries.
- **Response rate.** Opportunities that reached Applied or beyond and have at least one inbound interaction, divided by all that reached Applied or beyond. Source rates use the same rule per source.
- **Resumes are metadata only.** There is no upload. `file_name` must be a plain file name; anything containing `/` or `\\` is rejected.
- **Done and snooze.** `PATCH /followups/{id}` with `{"status":"done"}` sets `done_at`. A new `due_date` snoozes it.

## 3. Frontend

All commands run from **`apps/frontend`**.

```bash
cd apps/frontend
cp .env.example .env
npm install
npm run dev                   # http://localhost:5173
```

### Verify the frontend

Start the backend first (section 2) and apply migrations, then run `npm run dev` and create an account in the app. Use `http://localhost:5173` (not `127.0.0.1`) so the session cookie is sent.

| Check | Directory | Command / action | Expected |
| --- | --- | --- | --- |
| Type check + build | `apps/frontend` | `npm run build` | Builds with no TypeScript errors |
| Tests | `apps/frontend` | `npm test` | 103 passed |
| Lint | `apps/frontend` | `npm run lint` | No errors (a few warnings from generated shadcn files are expected) |
| Format | `apps/frontend` | `npm run format:check` | `All matched files use Prettier code style!` |
| Today | browser | <http://localhost:5173> | Overdue follow-up with Done and Snooze, an interview today, top next actions. Click Done: the row disappears at once and a toast appears |
| Pipeline | browser | <http://localhost:5173/pipeline> | Ten stage columns. Drag a Found card onto Applied: it moves immediately and a "follow-up scheduled" toast appears. Reload to confirm it persisted |
| Keyboard move | browser | Tab to a card's grip handle, press Space, Left/Right arrows, Space | Card moves one column per arrow press |
| Filters | browser | Pipeline filters | Priority, source and search narrow the cards |
| Opportunity detail | browser | Click a card title | JD tab, interaction timeline, contacts, follow-ups, stage selector, Log interaction, Edit, Delete. An applied opportunity silent for 21+ days shows a "Mark as ghosted" banner |
| Analytics | browser | <http://localhost:5173/analytics> | Scorecard, six progress rings, applications per day, 8-week trend with a metric switcher, funnel, response rate by source. Use the arrows to change week. "Set targets" saves targets for the shown week |
| Daily log | browser | <http://localhost:5173/daily-log> | Numbers-only form for today, streak counter, last 14 days. Pick an earlier date or click a row to edit it. A negative number shows an error |
| Prep | browser | <http://localhost:5173/prep> | Topics grouped by category with progress bars. Tick a checkbox, click a confidence dot, change status. Add, edit and delete topics |
| Contacts & Resumes | browser | <http://localhost:5173/contacts> | Two tabs (the tab is kept in the URL as `?tab=resumes`). Search contacts by name, company or email and filter by role. Add, edit and delete both. A contact can be linked to an opportunity |
| Responsive | browser | Device toolbar at 360, 768 and 1440 px wide | No page scrolls sideways (the kanban board scrolls inside its own area). On a phone the sidebar slides over, and the pipeline cards have a ⋮ Move to menu |
| Sign up and sign in | browser | <http://localhost:5173/register> | Creates an account, shows "Check your email"; sign-in is refused until the email is verified |
| Protected pages | browser | Open <http://localhost:5173/prep> while signed out | Redirects to `/login?next=%2Fprep` and returns there after sign-in |
| Account | browser | Sidebar user menu > Account | Edit your name, change your password, sign out of all devices |
| Command palette | browser | Cmd+K (macOS) or Ctrl+K | Add opportunity, Log interaction, jump to a page or an opportunity |
| Theme | browser | Sun/moon button in the sidebar | Dark by default, light on toggle, remembered after reload |

### Responsive layout

The UI is built mobile-first and has been checked at 360, 390, 768, 1024 and 1440 px wide, in portrait and landscape.

| Width | Behaviour |
| --- | --- |
| Under 768 px (phones) | The sidebar is a slide-over opened from the top-left button, and it closes after you pick a page. The top bar shrinks the search field and turns "Add opportunity" into a `+` button. Contacts, Resumes and the daily-log history become stacked cards instead of wide tables. Forms use two columns where the fields are short. |
| 768 to 1023 px (tablets) | The sidebar starts collapsed to icons so content gets the room. Toggle it with the button in the top bar. |
| 1024 px and up | The sidebar starts expanded, and tables and charts use the full layout. |

Touch devices:

- **Kanban:** press and hold a card for about a quarter of a second to drag it. A quick swipe still scrolls the board. Every card also has a **⋮ Move to** menu, which is the easiest way to change a stage on a phone. The grip handle is shown only on devices with a mouse.
- **Targets:** rating dots, checkboxes and list rows are enlarged on touch screens.
- **Dialogs:** they never exceed the screen height (they scroll inside themselves), including on a phone held sideways.

To check it yourself, open the app and use your browser's device toolbar (Chrome: Cmd/Ctrl+Shift+M), then try a phone, a tablet and a desktop size. Nothing should scroll sideways except the kanban board, which scrolls inside its own area.

### Formatting

Prettier is configured in `apps/frontend/.prettierrc.json` (no semicolons, double quotes, trailing commas, 100 columns). Run these from `apps/frontend`:

```bash
npm run format          # rewrite files
npm run format:check    # check only (use this in CI)
```

`src/components/ui` is ignored because the shadcn CLI generates it. Backend formatting is `uv run ruff format .` from `apps/backend`.

### Adding shadcn/ui components

From `apps/frontend`:

```bash
npx shadcn@latest add card table dialog
```

## Authentication and accounts

Email-and-password accounts with email verification and password reset (via SendGrid), Google sign-in, and per-account data. Mobile OTP is intentionally not included.

### How it works

| Concern | Design |
| --- | --- |
| Passwords | Argon2id hashes, never the password. Minimum 10 characters, a letter and a number, a short common-password deny-list, and no part of your email or name. Checked in the browser for feedback and again on the server. |
| Sessions | A random 256-bit token in an **HttpOnly** cookie (`session`). Only its SHA-256 hash is stored, so a database leak cannot be replayed, and signing out really invalidates it. 30-day absolute lifetime, 7-day idle timeout. A new session id is issued on every sign-in. Suspending an account ends its sessions immediately. |
| CSRF | Every POST/PATCH/PUT/DELETE needs an `X-CSRF-Token` header. The token is derived from the session (HMAC), returned by `/auth/me` and the sign-in endpoints, and kept in memory (never `localStorage`). The `Origin` header must also be an allowed origin. CORS allows credentials only for listed origins. |
| Email links | Verification and reset tokens are random, stored hashed, single-use and time-limited (24 hours and 30 minutes). Links look like `/verify-email#token=...`: the token is in the URL **fragment**, so it never reaches servers, logs or `Referer`. The page reads it, scrubs it from the address bar and calls the API with a POST, so email-security scanners that pre-fetch links cannot use it up. SendGrid click tracking is turned off for these emails. |
| No account enumeration | `forgot-password` and `resend-verification` answer identically for unknown and known emails. Sign-in gives one generic error for wrong email or wrong password (and takes the same time). Registration does report a duplicate email, as requested; it is rate limited. |
| Rate limiting | Stored in PostgreSQL, so every worker shares it. Sign-in: 5 failures per email and 20 per IP per 15 minutes (the correct password is also refused while locked). Sign-up: 5 per IP per hour. Verification and reset emails: 3 per address and 10 per IP per hour. Token attempts: 30 per IP per hour. Responses are `429` with `Retry-After`. |
| Google | The button returns a Google ID token. The server verifies its signature, issuer, audience and expiry with Google's library, requires `email_verified`, and checks a **nonce** it issued (signed, 10 minutes) that Google embedded in the token, so a stolen token cannot be replayed. Nothing about the user is read from the browser. Accounts are matched by Google's stable `sub`, then by email. |
| Linking Google to an existing email | If that account's email was verified, the two are linked. If it was **never verified**, the account's password is discarded and its sessions revoked: someone may have registered the address without owning it, and the real owner now proves control through Google. |
| Your data | Eight tables carry `user_id`, set from the session and never from the request body. Every repository query filters by it (a test fails if one forgets), and another user's id is a 404. Deleting an account deletes its data. |
| Logging | Structured JSON. Never passwords, tokens or links; emails appear only as short hashes. |

### API

All under `/api/v1/auth`. Errors are `{"detail": "...", "code": "..."}`; the frontend branches on `code`.

| Endpoint | Purpose |
| --- | --- |
| `POST /register` | Create an account and email a verification link (201). No session yet. |
| `POST /verify-email` | Use a verification token. Codes: `invalid_token`, `token_used`, `token_expired`. |
| `POST /resend-verification` | New link for an unverified account. Always 202. |
| `POST /login` | Sets the session cookie and returns the user and CSRF token. Codes: `invalid_credentials` (401), `email_not_verified` / `account_suspended` (403, only after the right password), `rate_limited` (429). |
| `POST /logout`, `POST /logout-all` | Revoke this session, or every session. |
| `GET /me`, `PATCH /me` | Current user and CSRF token; update your name. |
| `POST /change-password` | Needs the current password; signs out other devices. A wrong current password is a 400 (`incorrect_password`), not a 401. |
| `POST /forgot-password`, `POST /reset-password/check`, `POST /reset-password` | Reset flow. A reset also verifies the email, revokes every session and sends a "password changed" notice. |
| `GET /google/nonce`, `POST /google` | Google sign-in and sign-up. |

### Local development

You do not need SendGrid or Google to develop:

1. `cd apps/backend && uv run alembic upgrade head`, start the API, then start the frontend and open <http://localhost:5173>.
2. Register in the app. With no SendGrid key, emails are suppressed (a warning is logged, never the link). Pick one:
   - Set `AUTO_VERIFY_EMAIL=true` in `apps/backend/.env`. It is refused unless `FRONTEND_URL` is localhost.
   - Or print the link yourself: `uv run python -m app.scripts.auth_admin issue-link verify you@example.com` and open it.
3. Reset flow without email: `uv run python -m app.scripts.auth_admin issue-link reset you@example.com`.

Use `localhost`, not `127.0.0.1`, for both the app and the API: the cookie is same-site only on the same hostname.

### Your existing data

Rows created before accounts have no owner and are invisible to everyone until claimed. They are given to one account when that account's email is **verified**:

- **Local** (`FRONTEND_URL` is localhost): the first account to verify claims them. So create your own account first.
- **Deployed:** nothing is claimed unless `LEGACY_DATA_OWNER_EMAIL` is set, and then only that email can claim. (Otherwise the first stranger to sign up could take your data.)

### Setting up SendGrid

1. Create an API key with only **Mail Send** permission.
2. Verify the sender: a Single Sender address, or domain authentication (better for deliverability).
3. Set `SENDGRID_API_KEY`, `EMAIL_FROM_ADDRESS` and `EMAIL_FROM_NAME`. Failures are logged (status only) and never shown to users; the user can resend.

### Setting up Google sign-in

1. In Google Cloud Console, create an OAuth client of type **Web application**.
2. Add your frontend origin(s) (for example `http://localhost:5173` and your production URL) under **Authorized JavaScript origins**. No redirect URI or client secret is needed.
3. Set `GOOGLE_CLIENT_ID` in the backend and `VITE_GOOGLE_CLIENT_ID` in the frontend (same value; it is public). Leave both empty to hide the button.

### Deploying (checklist)

The backend refuses to start with an unsafe production configuration, so do these **before** deploying the new code:

1. **Back up the database**, then run `uv run alembic upgrade head` (migration `0004`). It adds accounts and an owner column to every data table; nothing is deleted.
2. Backend environment (see `apps/backend/.env.example`): `FRONTEND_URL` (https), `SECRET_KEY` (32+ random characters), `CORS_ORIGINS` (your frontend origin), `SENDGRID_API_KEY`, `EMAIL_FROM_ADDRESS`, `LEGACY_DATA_OWNER_EMAIL` (your email), and `TRUSTED_PROXY_COUNT=1` if the host puts a proxy in front (otherwise every user shares one rate-limit IP).
3. Frontend environment: `VITE_API_BASE_URL`, and `VITE_GOOGLE_CLIENT_ID` if you use Google.
4. **Cookies and domains.** The session cookie must be first-party to work in Safari and other browsers that block third-party cookies. Best: serve the API under the same site as the app. On Vercel, proxy it: rename `apps/frontend/vercel.json.example` to `vercel.json`, put your API host in it, and set `VITE_API_BASE_URL=/api/v1`. The included `vercel.json` already sends deep links (such as the `/verify-email` and `/reset-password` pages that emails open) to the app instead of a 404. If you keep the app and API on different sites, set `COOKIE_SAMESITE=none` and expect some browsers to refuse the cookie.
5. Sign up with the `LEGACY_DATA_OWNER_EMAIL` address and verify it to claim your existing data.

### Operating accounts

From `apps/backend`:

```bash
uv run python -m app.scripts.auth_admin list-users
uv run python -m app.scripts.auth_admin create-user you@example.com --name "Your Name"   # verified; password is prompted, hidden
uv run python -m app.scripts.auth_admin verify-email you@example.com
uv run python -m app.scripts.auth_admin suspend you@example.com     # signs them out everywhere, blocks sign-in
uv run python -m app.scripts.auth_admin activate you@example.com
uv run python -m app.scripts.auth_admin issue-link verify|reset you@example.com   # local only
```

### Known limits

- Changing your email address is not supported (it is your sign-in name). Deleting your own account from the UI is not built; delete a user row to remove an account and its data.
- Locking sign-in after repeated failures protects against guessing, but means someone could deliberately lock you out for 15 minutes.
- Public holidays and CAPTCHA are not part of this release.

## AI assistant

The assistant is being built in phases (see [docs/AI_ASSISTANT_PRD.md](docs/AI_ASSISTANT_PRD.md)).
Phase 0, the LLM gateway, is in place: one component that picks a model for each task across the
free tiers of Groq and Google AI Studio, tracks every model's budget in Postgres, falls back
when a model is rate-limited or down, and turns provider errors into messages that are safe to
show. Nothing in the app calls a provider SDK directly.

### Keys

Create a key at <https://console.groq.com/keys> and/or <https://aistudio.google.com/apikey>
and set `GROQ_API_KEY` / `GOOGLE_AI_API_KEY` in `apps/backend/.env` (and on Render). With
neither key the assistant is disabled and its endpoints answer `503 assistant_disabled`; with
one key only that provider's models are used. Embeddings need the Google key.

### Budgets and routing

Free-tier limits are per model and small. The defaults in `app/llm/catalog.py` are indicative:
set `LLM_MODEL_LIMITS` to what your provider console shows for your account, for example
`LLM_MODEL_LIMITS={"openai/gpt-oss-120b": {"rpm": 30, "rpd": 1000, "tpm": 12000}}`. The
ledger (`provider_resource_state`) counts requests and tokens per minute and per day, trusts the
rate-limit headers Groq sends, cools a model down after a 429, and opens a circuit after
repeated failures. `LLM_POLICY_OVERRIDE` changes which models a task tries, in order
(`app/llm/policy.py` lists the tasks). A run may switch models at most `LLM_MAX_MODEL_SWITCHES`
times before it reports "at capacity" with a retry time.

### Operating it

From `apps/backend`:

```bash
uv run python -m app.scripts.llm_admin ping "Say hello"     # which model answered, latency, tokens
uv run python -m app.scripts.llm_admin status                # budget, cooldowns and circuits per model
uv run python -m app.scripts.llm_admin usage --since 7d      # calls, tokens and errors per model/task
uv run python -m app.scripts.llm_admin reset-cooldowns       # after fixing a key or a provider outage
```

### Chat (Phase 1)

The assistant page (`/assistant` on the web, More → Assistant in the app) answers questions about
the signed-in user's own data and can make changes on request: move a stage, add or complete a
follow-up, log a call or email, set a next action, add an opportunity. **Every change is shown as
a card first** and nothing is written until the user confirms it (editable fields on the web).

- **API** (`/api/v1/chat`): `GET /config`; `GET|POST /conversations`;
  `GET|PATCH|DELETE /conversations/{id}`; `POST /conversations/{id}/messages` answers with
  server-sent events (`run_started`, `token`, `tool_start`, `tool_end`, `confirmation_required`,
  `model_switched`, `notice`, `error`, `done`), with a `: ping` comment every
  `CHAT_HEARTBEAT_SECONDS` while a model call is in flight; `POST .../actions/{action_id}` with
  `{"decision": "confirm" | "reject", "edits"?: {...}}` answers a card and streams the rest of
  the reply; `POST .../runs/{run_id}/resume` continues a reply that failed on capacity from its
  last completed step; `POST .../runs/{run_id}/cancel` stops one (and declines an open card).
- **How a turn runs** (`app/assistant/`): a LangGraph graph, guardrail → (polite decline |
  agent ⇄ read-only tools). Tools wrap the existing services, so data is always the user's own.
  Older turns are folded into a rolling summary so prompts stay small enough for Groq.
- **Limits**: `CHAT_DAILY_MESSAGES` (60) and `CHAT_PER_MINUTE` (6) per user, one reply at a time
  per conversation, 2,000 characters per message, a card waits `CHAT_ACTION_TTL_MINUTES` (15) for
  a decision, and a lookup may use `CHAT_TOOL_TIMEOUT_SECONDS` (8) of database time
  (Postgres `statement_timeout`). `CHAT_WRITES_ENABLED=false` makes the assistant read-only.
- **Checkpoints**: LangGraph keeps run state in Postgres (tables `checkpoints`,
  `checkpoint_blobs`, `checkpoint_writes`, `checkpoint_migrations`). They are created
  automatically on the first chat, outside Alembic, and deleted when a run finishes.
- **Deploying**: run `alembic upgrade head` (migrations `0006`–`0008`) on Neon, and set `GROQ_API_KEY` /
  `GOOGLE_AI_API_KEY` on Render. If replies arrive all at once instead of word by word, a proxy
  is buffering the stream: the page still works, just without the typing effect.

### Resume files (Phase 2)

Each resume can carry one PDF (up to `RESUME_MAX_DOCUMENTS`, default 3 files per user; 5 MB and
10 pages each). On upload the text is extracted and **redacted** (Aadhaar with checksum, PAN,
passport, voter ID, bank account/IFSC, card numbers, DOB, passwords) before anything is stored,
then split into section-aware passages. Embeddings (`gemini-embedding-001`, 768 dims) and a
structured profile (titles, years, skills, domains) are produced in the background; if the
free quota is exhausted the resume shows "Indexing paused" and heals on a later read or a
manual retry (`POST /resumes/{id}/document/process`, limited per day).

- **API**: `POST /resumes/{id}/document` (multipart `file`), `DELETE /resumes/{id}/document`,
  `GET /resumes/{id}/document/url` (a link valid for `OBJECT_STORE_PRESIGN_SECONDS`).
- **Storage**: the PDF lives in S3-compatible object storage, never on the server's disk.
  Production: create a Cloudflare R2 bucket and an API token (object read/write), then set
  `OBJECT_STORE_ENDPOINT_URL=https://<account>.r2.cloudflarestorage.com`,
  `OBJECT_STORE_BUCKET`, `OBJECT_STORE_ACCESS_KEY_ID`, `OBJECT_STORE_SECRET_ACCESS_KEY` on Render.
  Local development: `OBJECT_STORE_LOCAL_DIR=.object-store` stores files in a folder.
- **pgvector**: migration `0008` enables the extension and an HNSW index where it is available
  (Neon has it). A stock local Postgres without pgvector gets a plain array column instead and
  search runs in Python, so every test passes either way. To exercise the real index locally:
  `docker run -d --name ccc-pgvector -p 55432:5432 -e POSTGRES_PASSWORD=postgres pgvector/pgvector:pg17`
  then `TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:55432/ccc_test uv run pytest`.
- **Assistant**: new tools `get_resume_profile` and `search_resume` ("what does my backend resume
  say about Kafka?"); search falls back to keywords if embeddings are unavailable.

Every provider call is a row in `provider_usage_events` (tokens, latency, outcome; never the
prompt). Logs carry the same fields under the `llm_call` event. Optional LangSmith tracing
(`LANGSMITH_TRACING=true` plus a key) sends prompts to LangSmith, so it is off by default.

## Configuration

Each app has its own `.env.example`. Copy it to `.env` in the same folder. `.env` files are git-ignored. Do not put secrets in the frontend `.env`, because every `VITE_` variable is shipped to the browser.

| File | Variable | Purpose |
| --- | --- | --- |
| `apps/backend/.env` | `DATABASE_URL` | SQLAlchemy URL (`postgresql+psycopg://...`) |
| | `CORS_ORIGINS` | JSON list of allowed browser origins |
| | `TIMEZONE`, `FOLLOWUP_WORKING_DAYS`, `GHOST_AFTER_DAYS` | "Today" for due dates, and the two auto-rule numbers (defaults `Asia/Kolkata`, 2, 21) |
| | `FRONTEND_URL`, `SECRET_KEY`, `COOKIE_*`, `SESSION_*`, `GOOGLE_CLIENT_ID`, `SENDGRID_API_KEY`, `EMAIL_FROM_*`, `LEGACY_DATA_OWNER_EMAIL`, `TRUSTED_PROXY_COUNT` | Accounts. See [Authentication and accounts](#authentication-and-accounts) and `.env.example` |
| `apps/frontend/.env` | `VITE_API_BASE_URL` | Backend base URL, default `http://localhost:8000/api/v1` |
| | `VITE_GOOGLE_CLIENT_ID`, `VITE_TERMS_URL`, `VITE_PRIVACY_URL` | Public Google client ID; optional terms and privacy links |
