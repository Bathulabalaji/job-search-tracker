# Bug report — Career Command Center

Test date: 15 Nov 2026 · Build: `main` at `b75aba7` · Tester: QA pass by Claude (acting as SDET)

## Scope and method

- **What was tested:** every backend feature, through real HTTP against a separate copy of the
  API (port 8010, its own throwaway database, outgoing email and search keys disabled). Real
  Groq and Google models were used for the assistant, resume indexing and matching. Web and
  mobile were covered by their automated suites plus a code review of how they show the data.
- **Checks run:** about 200 scripted checks, plus the existing suites (backend 594, web 131, mobile 63,
  all passing).
- **Not covered:** clicking through the web and mobile screens in a real browser or phone (no
  browser was available), email delivery, Google sign-in, and production (Render, Neon, R2).
- **Result:** 17 bugs, 1 of them still being investigated. No critical bugs. Isolation between
  users, sign-in security and the assistant's confirm-before-change rule all held up.

## Summary

| ID | Feature | Title | Severity |
|---|---|---|---|
| BUG-01 | Mobile · Resumes | Resume upload on the phone fails with "Can't reach the server" | High (open) |
| BUG-02 | All APIs | An id above 2,147,483,647 in any URL returns 500 | Medium |
| BUG-03 | All APIs | A NUL character in any text field returns 500 | Medium |
| BUG-04 | Opportunities · Contacts | Links are not validated by the API; LinkedIn links not validated anywhere | Medium |
| BUG-05 | Interactions | Future-dated interactions are accepted and stop ghosting detection | Medium |
| BUG-06 | Resume matching | Missing-skills list can leave out a required skill | Medium |
| BUG-07 | Account | There is no way to delete an account | Medium |
| BUG-08 | Opportunities | Company and role can be only spaces | Low |
| BUG-09 | Opportunities | Job description size is unlimited | Low |
| BUG-10 | Opportunities | Stack tags: no limit on count, duplicates kept | Low |
| BUG-11 | Search (all lists) | `%` and `_` in search act as wildcards | Low |
| BUG-12 | Contacts | API accepts invalid emails and any text as a phone number | Low |
| BUG-13 | Interactions | Clients can create "stage change" entries; summary size is unlimited | Low |
| BUG-14 | Daily log | Logs can be saved for future dates and skew the streak | Low |
| BUG-15 | Follow-ups | Due dates have no sensible range (1999 is accepted) | Low |
| BUG-16 | Navigation | "Jobs for you" shows even when job search is not set up | Low |
| BUG-17 | Job search | Apply links keep Google's tracking parameters | Low |

Severity: **High** blocks a main task for users. **Medium** gives wrong results, a server error
or a real gap, with a workaround. **Low** is a data-quality or polish issue.

---

## Mobile · Resumes

### BUG-01 — Resume upload on the phone fails with "Can't reach the server" (High, open)

- **Reported by:** the user, on the installed Android app.
- **Steps:** open a resume, choose a PDF, upload.
- **Expected:** the file uploads and shows "Indexing…".
- **Actual:** the error "Can't reach the server". Web upload to the same API works.
- **Found so far:**
  - The API accepts multipart uploads from outside (checked on the deployed API) and the same
    upload works end to end here over HTTP.
  - The phone gives up after 60 s (`TIMEOUT_MS` in `apps/mobile/src/api/client.ts`). Render's
    free tier takes about a minute to wake up, so the first upload after a quiet spell can time
    out before the server answers. The chat stream already waits 75 s for this reason; uploads
    don't.
  - The installed APK may also predate the document-picker build.
  - Since commit `a57c8ab` the app reports the real reason (timeout vs network error), but that
    needs a new APK.
- **Next step:** build a new APK, reproduce, and read the new error text and Render's logs.
- **Suggested fix:** give uploads a longer timeout (90–120 s) or wake the API first with a call
  to `/health`.
- **Mobile fix (2026-11-15):** uploads now wait 150 s (`UPLOAD_TIMEOUT_MS`). Still to confirm on a new APK; if it
  still fails, the error text now says why.
- **Root cause found (2026-11-15):** the real error on the phone was "Unsupported FormDataPart implementation". Expo's
  `fetch` (default since SDK 52) cannot send React Native's old `{ uri, name, type }` file part. The upload now sends a
  part that has `bytes()` (read through `expo-file-system`), and a test runs it through Expo's own multipart encoder.
  Needs a new APK to confirm on a phone.

---

## All APIs

### BUG-02 — An id above 2,147,483,647 in any URL returns 500 (Medium)

- **Steps:** `GET /api/v1/opportunities/99999999999999999999` (any route with an `{id}`).
- **Expected:** 404 or 422.
- **Actual:** 500 `internal_error`. Postgres raises `integer out of range`. The server also
  drops that connection, so the client's next request on it fails with "connection reset".
- **Suggested fix:** declare path ids as `Annotated[int, Path(ge=1, le=2_147_483_647)]`, or map
  `DataError` to 422 in `app/main.py`.

### BUG-03 — A NUL character in any text field returns 500 (Medium)

- **Steps:** `POST /api/v1/opportunities` with `{"company": "C\u0000", "role": "R"}`.
- **Expected:** 422 with a clear message, or the character removed.
- **Actual:** 500 `internal_error` (Postgres text cannot contain `\x00`), and the connection is
  dropped as in BUG-02.
- **Suggested fix:** a shared validator that removes or rejects `\x00` in every string field.

---

## Opportunities

### BUG-04 — Links are not validated by the API; LinkedIn links not validated anywhere (Medium)

- **Steps:**
  1. `POST /opportunities` with `"jd_url": "javascript:alert(1)"` or `"not a url"`.
  2. `POST /contacts` with `"linkedin_url": "javascript:alert(1)"`, or in the web or mobile
     contact form enter `linkedin.com/in/riya` (no `https://`).
- **Expected:** only `http(s)://` links are accepted, everywhere.
- **Actual:**
  - The API stores both values as given.
  - The web and mobile opportunity forms do check `jd_url`, but the API, and the assistant's
    `create_opportunity` tool, do not.
  - Neither form checks the LinkedIn URL. A link without `https://` becomes a relative link on
    web ("LinkedIn" opens a page inside the app that doesn't exist), and on mobile
    `Linking.openURL` fails silently.
  - The web puts these values straight into `href` (`features/detail/side-cards.tsx`,
    `features/contacts/contacts-tab.tsx`). React 19 blocks `javascript:` links, so this is a
    dead link today, not script execution, but it relies on that one safeguard.
- **Suggested fix:** an `HttpUrl`-style validator on `jd_url` and `linkedin_url` in the API
  schemas, the assistant's argument schemas, and both contact forms.
- **Mobile fix (2026-11-15):** the contact, outreach-profile and opportunity forms accept `linkedin.com/in/x`,
  store it as `https://…`, and reject other schemes; the LinkedIn and job-posting buttons check the link before
  opening it and say when it can't be opened. The API half is still open.

### BUG-08 — Company and role can be only spaces (Low)

- **Steps:** `POST /opportunities` with `{"company": "   ", "role": "R"}`.
- **Expected:** 422, as the web form does.
- **Actual:** 201 and the card has a blank title. Also reachable through the assistant's
  `create_opportunity` tool.
- **Suggested fix:** trim and require at least one character in the API schema.

### BUG-09 — Job description size is unlimited (Low)

- **Steps:** create an opportunity with a 300,000-character `jd_text`.
- **Expected:** a sensible cap (for example 20,000 characters) and 422 beyond it.
- **Actual:** 201. Every list and detail response then carries the full text. (The assistant
  only reads a capped excerpt, so it is not affected.)

### BUG-10 — Stack tags: no limit on count, duplicates kept (Low)

- **Steps:** create with `stack_tags` of 200 items, or `["python", "Python", "python"]`.
- **Expected:** at most about 20 tags, de-duplicated without regard to case.
- **Actual:** all 200 are stored; the three copies of python are all kept.

### BUG-11 — `%` and `_` in search act as wildcards (Low)

- **Steps:** search opportunities for `%` or `_`.
- **Expected:** only rows that contain that character.
- **Actual:** every row matches. The search text goes into `ILIKE` unescaped
  (`repositories/opportunity.py`, `contact.py`, `prep_item.py`, `resume.py`, `job_posting.py`).
- **Suggested fix:** escape `\`, `%` and `_` and use `ilike(pattern, escape="\\")`.

---

## Contacts

### BUG-12 — API accepts invalid emails and any text as a phone number (Low)

- **Steps:** `POST /contacts` with `"email": "nope"` or `"phone": "call me maybe; drop table"`.
- **Expected:** 422, like the web and mobile forms for email.
- **Actual:** 201; `nope` is stored and shown as a `mailto:nope` link. (The forms check email,
  so this is reachable through the API only. Phone is not checked anywhere.)

---

## Interactions

### BUG-05 — Future-dated interactions are accepted and stop ghosting detection (Medium)

- **Steps:** log an interaction with `occurred_at` 400 days ahead.
- **Expected:** 422, or a cap of a few minutes in the future to allow for clock differences.
- **Actual:** 201. The opportunity's last contact becomes a 2027 date and "days since contact"
  stays at 0, so the ghosting warning never shows for it. A typo in the year causes this.
- **Fixed (2026-11-15):** the API rejects an interaction dated more than 5 minutes ahead (422 "The date can't be in the future"); web and mobile forms check it too.

### BUG-13 — Clients can create "stage change" entries; summary size is unlimited (Low)

- **Steps:** `POST /interactions` with `"type": "stage_change"`; or a 20,000-character summary.
- **Expected:** stage changes are only written by the server when a stage moves; the summary has
  a cap.
- **Actual:** both are accepted. A forged stage change appears in the timeline as if the stage
  had moved (the analytics funnel is not affected).
- **Fixed (2026-11-15):** the API rejects `stage_change` from clients and caps the summary at 2,000 characters.

---

## Daily log

### BUG-14 — Logs can be saved for future dates and skew the streak (Low)

- **Steps:** create a log for tomorrow.
- **Expected:** 422 ("You can't log a day that hasn't happened").
- **Actual:** 201; the streak then reports a last active date of tomorrow and a longest streak
  that includes it.

---

## Follow-ups

### BUG-15 — Due dates have no sensible range (Low)

- **Steps:** create a follow-up due on 1999-01-01.
- **Expected:** 422 for dates far in the past (and far in the future).
- **Actual:** 201; it shows on Today as thousands of days overdue.

---

## Resume matching

### BUG-06 — Missing-skills list can leave out a required skill (Medium)

- **Steps:** a JD that requires Python, FastAPI, PostgreSQL, Docker and Kubernetes (Golang a
  plus); a resume with no Kubernetes; compare.
- **Expected:** Kubernetes listed as missing.
- **Actual:** with the live model, missing listed only Golang. The model's own suggestion then
  said "mention any Kubernetes experience", which contradicts the list. Score 85.
- **Why:** the missing list comes only from the model. The server removes wrong entries but
  never adds skills the model forgot.
- **Suggested fix:** also compare the JD against a skills vocabulary (the resume profile's
  skills and the stack keyword list already in the code), and add JD skills that are absent from
  the resume.

---

## Account

### BUG-07 — There is no way to delete an account (Medium)

- **Steps:** look for "Delete account" on web, mobile, or in the API.
- **Expected:** a user can delete their account and data (expected by India's DPDP Act and the
  app stores). The data model already deletes a user's rows when the user row is deleted, and
  `storage_admin gc` removes their files afterwards.
- **Actual:** no endpoint or screen exists; only the operator can delete a user.

---

## Navigation

### BUG-16 — "Jobs for you" shows even when job search is not set up (Low)

- **Steps:** run the web app against a server with no search keys.
- **Expected:** the nav item is hidden, as Account hides the assistant card.
- **Actual:** it shows; "Find new jobs" then fails with "Job search isn't set up".
- **Mobile fix (2026-11-15):** the More tab hides "Jobs for you" when the server reports it unavailable. Web still open.

---

## Job search

### BUG-17 — Apply links keep Google's tracking parameters (Low)

- **Steps:** search with SerpApi and open a result.
- **Expected:** a clean link (the app already computes one for de-duplication).
- **Actual:** links end in `?utm_campaign=google_jobs_apply&utm_source=google_jobs_apply&…`,
  which also ends up in the opportunity's job link when tracked. The links still work.

---

## Tested and working

These were checked and behaved correctly; listed so they need not be re-tested.

- **Sign-up and sign-in:** duplicate email (case-insensitive), weak password, terms, blank name;
  same answer for unknown email and wrong password; lockout after 5 failures with
  `Retry-After`; 5 sign-ups per hour per IP.
- **Sessions:** changing the password signs out other devices; logout and logout-all revoke
  tokens; the web cookie is HttpOnly and SameSite.
- **Request protection:** the web needs the CSRF token; requests from another website's origin
  are refused; CORS allows only the app; `nosniff`, `X-Frame-Options: DENY` and `no-store` are
  sent.
- **Isolation:** user B cannot read, change, move or delete user A's opportunities, contacts,
  follow-ups, logs, prep items, resumes, conversations or stored matches, nor attach to them.
- **Pipeline rules:** moving to applied creates one follow-up and one stage-change entry; moving
  to the same stage adds nothing.
- **Validation that works:** priority, fit score, stage, dates, limits and offsets, weekly
  target must start on a Monday, one log per day, prep confidence and category.
- **Resume files:** wrong file type (415), over 5 MB (413), forged download link; text PDF
  uploads, is indexed and redacted (phone and email removed); download works.
- **Assistant (live models):** answers from tools; off-topic and "print your system prompt"
  are declined; changes wait for a confirmation card; confirm runs once, a second confirm is
  refused; reject writes nothing; a new message while a card waits is refused; it cannot delete
  data; cancel works; a re-sent message is refused; 6 messages a minute then 429 with
  `Retry-After`; opt-out; usage counts.
- **Resume matching (live):** scores the resume, caches the repeat, and chat shows the match
  card.
- **Maintenance endpoint:** refuses a missing secret, runs with the right one, rejects GET.
