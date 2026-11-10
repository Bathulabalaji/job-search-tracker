# Career Command Center

Single-user job search tracker + analytics. See [docs/PROJECT_BRIEF.md](docs/PROJECT_BRIEF.md) for the full brief.

**Status:** feature-complete against the brief. The backend covers opportunities, contacts, interactions, follow-ups (with `/move` and the follow-up auto-rule), daily logs, weekly targets, prep items, resumes, and the dashboard and analytics endpoints. The frontend has Today, Pipeline (kanban), Opportunity detail, Analytics, Daily log, Prep, Contacts & Resumes and the Cmd/Ctrl+K command palette.

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
| Tests | `apps/backend` | `uv run pytest` | 117 passed |
| Types | `apps/backend` | `uv run mypy` | `Success: no issues found` |
| Lint | `apps/backend` | `uv run ruff check .` | `All checks passed!` |
| Alembic connects | `apps/backend` | `uv run alembic current` | `0003 (head)` after you run the migration below |

### Migrations

From `apps/backend`:

```bash
uv run alembic upgrade head                                   # create/update tables (do this first)
uv run alembic current                                        # show the applied revision (expect 0003 (head))
uv run alembic downgrade base                                 # undo everything (dev only)
uv run alembic revision --autogenerate -m "describe change"   # after changing a model; review the file it writes
```

The database URL comes from `DATABASE_URL` in `.env`, not from `alembic.ini`. New model modules must be imported in `app/models/__init__.py` so autogenerate sees them.

### Seed sample data

From `apps/backend`, after `alembic upgrade head`:

```bash
uv run python -m app.scripts.seed            # seeds each empty section; skips the ones that already have data
uv run python -m app.scripts.seed --reset    # wipes ALL tables, then reseeds (ENVIRONMENT=local only)
```

The script has three independent sections, and each runs only if its own tables are empty, so it is safe to re-run:

- **Opportunities:** 10 fictional opportunities across all stages, with contacts, interactions and follow-ups. Stages are reached through real moves, so the funnel has history. One applied opportunity has been silent for 26 days (ghosted suggestion), and one follow-up is overdue.
- **Activity:** 21 days of daily logs, including rest days, and this week's targets.
- **Prep:** 17 prep topics across all seven categories.
- **Resumes:** 3 sample resume versions.

Check with `curl http://localhost:8000/api/v1/analytics/weekly`.

### Run the tests

From `apps/backend`:

```bash
uv run pytest            # 117 tests
uv run pytest tests/unit # pure rules only, no database needed
```

Service and API tests need PostgreSQL. They use a separate `<database>_test` database on the same server (for example `career_command_center_test`). It is created if missing and **dropped and rebuilt from the Alembic migrations on every run**, so the tests also check the migrations. Each test runs in a transaction that is rolled back. Your dev data is never touched. Set `TEST_DATABASE_URL` to use a different server; its database name must end in `_test`.

### API summary (`/api/v1`, full docs at `/docs`)

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

Start the backend first (section 2), apply migrations and seed it, then run `npm run dev`.

| Check | Directory | Command / action | Expected |
| --- | --- | --- | --- |
| Type check + build | `apps/frontend` | `npm run build` | Builds with no TypeScript errors |
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

## Configuration

Each app has its own `.env.example`. Copy it to `.env` in the same folder. `.env` files are git-ignored. Do not put secrets in the frontend `.env`, because every `VITE_` variable is shipped to the browser.

| File | Variable | Purpose |
| --- | --- | --- |
| `apps/backend/.env` | `DATABASE_URL` | SQLAlchemy URL (`postgresql+psycopg://...`) |
| | `CORS_ORIGINS` | JSON list of allowed browser origins |
| | `TIMEZONE`, `FOLLOWUP_WORKING_DAYS`, `GHOST_AFTER_DAYS` | "Today" for due dates, and the two auto-rule numbers (defaults `Asia/Kolkata`, 2, 21) |
| | `AUTH_ENABLED` | Reserved for the later single-user JWT login; keep `false` |
| `apps/frontend/.env` | `VITE_API_BASE_URL` | Backend base URL, default `http://localhost:8000/api/v1` |
