# Career Command Center

Single-user job search tracker + analytics. See [docs/PROJECT_BRIEF.md](docs/PROJECT_BRIEF.md) for the full brief.

**Status:** backend API for opportunities, contacts, interactions and follow-ups (including `/move` and the follow-up auto-rule) is done. The frontend is still a layout shell.

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
| Tests | `apps/backend` | `uv run pytest` | 57 passed |
| Types | `apps/backend` | `uv run mypy` | `Success: no issues found` |
| Lint | `apps/backend` | `uv run ruff check .` | `All checks passed!` |
| Alembic connects | `apps/backend` | `uv run alembic current` | `0001 (head)` after you run the migration below |

### Migrations

From `apps/backend`:

```bash
uv run alembic upgrade head                                   # create/update tables (do this first)
uv run alembic current                                        # show the applied revision (expect 0001 (head))
uv run alembic downgrade base                                 # undo everything (dev only)
uv run alembic revision --autogenerate -m "describe change"   # after changing a model; review the file it writes
```

The database URL comes from `DATABASE_URL` in `.env`, not from `alembic.ini`. New model modules must be imported in `app/models/__init__.py` so autogenerate sees them.

### Seed sample data

From `apps/backend`, after `alembic upgrade head`:

```bash
uv run python -m app.scripts.seed            # refuses if opportunities already exist
uv run python -m app.scripts.seed --reset    # wipes the 4 tables, then reseeds (ENVIRONMENT=local only)
```

It creates 10 fictional opportunities across all stages. One applied opportunity has been silent for 26 days, so it shows the ghosted suggestion, and one follow-up is overdue. Check with `curl "http://localhost:8000/api/v1/opportunities"`.

### Run the tests

From `apps/backend`:

```bash
uv run pytest            # 57 tests
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

List endpoints take `limit` and `offset`, plus filters (for example `?stage=applied&priority=1&q=acme`, `?opportunity_id=3`, `?status=pending&due_on_or_before=2026-11-13`).

Rules to know:

- **Stage changes only via `/move`.** `PATCH /opportunities/{id}` ignores `stage`, so the auto-rule cannot be bypassed.
- **Follow-up auto-rule.** Entering `applied` or `screening` (on create or move) adds a follow-up due in 2 working days (Mon-Fri, holidays not modelled). If the opportunity already has a pending follow-up, none is added.
- **Ghosted suggestion.** Opportunities in applied, screening, interview_scheduled or interviewing get `ghosted_suggestion: true` after 21 days without contact. It is a flag only; the stage is never changed automatically. `days_since_contact` counts from the last real interaction, or from creation if there is none.
- **Move records an interaction** of type `stage_change`. This type is an addition to the brief's list, and it does not count as contact.
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

| Check | Directory | Command | Expected |
| --- | --- | --- | --- |
| App loads | browser | <http://localhost:5173> | Dark navy shell with a sidebar and a "Today" placeholder |
| Navigation | browser | click sidebar items | URL and heading change (Pipeline, Analytics, Daily log, Prep, Contacts & Resumes) |
| Theme toggle | browser | click the sun/moon button at the bottom of the sidebar | Switches between dark (default) and light; choice survives a reload |
| Type check + build | `apps/frontend` | `npm run build` | Builds with no TypeScript errors |
| Lint | `apps/frontend` | `npm run lint` | No errors (3 warnings from generated shadcn files are expected) |

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
