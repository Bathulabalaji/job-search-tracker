# Project Brief: Career Command Center

Single-user job search tracker + analytics.

## Goal

A personal web app to track every job opportunity, recruiter interaction and follow-up, measure daily/weekly job-search activity against targets, and show what to do next.

## Stack (do not substitute)

- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2.0 (typed), Alembic, Pydantic v2, PostgreSQL, uv, pytest
- **Frontend:** React + Vite + TypeScript, Tailwind CSS, shadcn/ui, TanStack Query, React Router, react-hook-form + zod, Recharts, dnd-kit (kanban), lucide-react icons
- **Repo layout:** `apps/backend` and `apps/frontend` (monorepo, one git repo)
- **Architecture:** Router -> Service -> Repository layers. No business logic in routers.

## Data model (PostgreSQL)

- **opportunities:** id, company, role, source (naukri/linkedin/referral/recruiter/walkin/other), stack_tags[], location, work_mode, stage, priority (1-3), fit_score (0-100), jd_text, jd_url, expected_ctc_note, next_action, next_action_due, created_at, updated_at
- **stages (enum):** found, applied, screening, interview_scheduled, interviewing, offer, accepted, rejected, ghosted, parked
- **contacts:** id, opportunity_id (nullable), name, role (recruiter/hr/manager/referrer), company, email, phone, linkedin_url, notes
- **interactions:** id, opportunity_id, contact_id, type (call/email/linkedin/whatsapp/interview/nudge), direction (in/out), summary, occurred_at
- **followups:** id, opportunity_id, due_date, channel, message_draft, status (pending/done/skipped), done_at
- **daily_logs:** id, log_date (unique), applications_sent, messages_sent, referrals_requested, problems_solved, mocks_done, hours_prep, notes
- **weekly_targets:** id, week_start, applications, messages, referrals, problems, mocks, interviews
- **prep_items:** id, topic, category (python/fastapi/db/react/ai/system-design/behavioral), status (todo/doing/done), confidence (1-5), notes
- **resumes:** id, label, focus, file_name, version, notes (metadata only, no file storage)

**Rules:** never store government IDs, passwords or bank details anywhere in the app.

## API (all under `/api/v1`, OpenAPI documented, typed responses)

CRUD for each entity, plus:

- `POST /opportunities/{id}/move` (change stage, auto-create interaction record)
- `GET /dashboard/summary` (counts per stage, response rate, interviews this week)
- `GET /dashboard/today` (follow-ups due/overdue, interviews today, next actions)
- `GET /analytics/weekly` (daily_log totals vs weekly_target, trend, funnel conversion)
- **Auto-rule:** when an opportunity enters `applied` or `screening`, create a follow-up due in 2 working days; mark `ghosted` suggestion after 21 days of no interaction.

**Auth:** none locally; add a simple single-user JWT login behind an env flag later.

## Pages

1. **Today:** overdue and due follow-ups (one-click done/snooze), interviews today, top 3 next actions
2. **Pipeline:** kanban by stage (drag to move), filters by priority/source, card shows days since contact
3. **Opportunity detail:** JD, fit notes, timeline of interactions, contacts, follow-ups, quick-add forms
4. **Analytics:** weekly targets vs actual (progress rings), funnel chart, applications per day, response rate by source, scorecard summary
5. **Daily log:** fast form (numbers only) + streak counter
6. **Prep:** topic checklist with confidence ratings and progress bars
7. **Contacts and Resumes:** simple tables with search

## Design

- Modern "command center" feel: dark default with light toggle, deep navy background, one accent colour (electric indigo), generous spacing, soft card borders, subtle motion
- Typography: Inter for UI, JetBrains Mono for numbers/IDs
- shadcn/ui components throughout (Card, Table, Dialog, Command, Tabs, Badge, Progress, Toast and other components)
- Command palette (Cmd/Ctrl+K): quick add opportunity, log interaction, jump to page
- Empty states, skeleton loaders, optimistic updates, responsive down to tablet
- Accessibility: keyboard navigable, visible focus rings, AA contrast

## Engineering rules

- Strict typing (mypy-friendly Python, TypeScript strict mode), no `any`
- Env config via `.env` (provide `.env.example`), no secrets committed
- Alembic migration for every schema change; seed script for sample data
- pytest tests for services (stage moves, follow-up auto-rules, analytics math)
- Small, focused commits per feature; README with run instructions and verify steps
- Do not add libraries beyond the stack without asking
