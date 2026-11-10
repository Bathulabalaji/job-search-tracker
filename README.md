# Career Command Center

Single-user job search tracker + analytics. See [docs/PROJECT_BRIEF.md](docs/PROJECT_BRIEF.md) for the full brief.

**Status:** scaffold only. A health endpoint, an empty database layer, and a frontend layout shell. No features yet.

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
| OpenAPI docs | browser | <http://localhost:8000/docs> | Swagger UI listing `GET /api/v1/health` |
| Tests | `apps/backend` | `uv run pytest` | 1 passed |
| Types | `apps/backend` | `uv run mypy` | `Success: no issues found` |
| Lint | `apps/backend` | `uv run ruff check .` | `All checks passed!` |
| Alembic connects | `apps/backend` | `uv run alembic current` | exits 0 with no error (prints nothing while no migrations exist) |

### Migrations (for later steps)

From `apps/backend`:

```bash
uv run alembic revision --autogenerate -m "describe change"   # create a migration
uv run alembic upgrade head                                   # apply migrations
```

Import each new model module in `migrations/env.py` so autogenerate can see it. The database URL comes from `DATABASE_URL` in `.env`, not from `alembic.ini`.

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
| | `AUTH_ENABLED` | Reserved for the later single-user JWT login; keep `false` |
| `apps/frontend/.env` | `VITE_API_BASE_URL` | Backend base URL, default `http://localhost:8000/api/v1` |
