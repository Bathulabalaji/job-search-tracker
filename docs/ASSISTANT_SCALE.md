# Assistant: limits today and the path to scale

Written for whoever runs this app next. It says what holds the assistant back today, in order,
and what to change when each limit is reached. Nothing here is built; it is the plan.

## What the system is built for today

One small API instance on a free tier, one Postgres database, free model and search tiers.
That is enough for you and a small group of testers, and every shortcut below is a deliberate
consequence of it:

- Work runs inside the request that asked for it (the chat stream, an upload's background task).
  Render's free tier has no worker process, no cron and no disk, and may restart at any time, so
  long work is chunked, saved as it goes and safe to repeat.
- Budgets (model rate limits, search quotas, per-user allowances) are rows in Postgres taken
  under a row lock, so several requests cannot overspend them.
- The scheduled sweep is a GitHub Actions job that calls a secret-protected endpoint.

## What breaks first, and the fix

| Order | What you will see | Why | Change |
|---|---|---|---|
| 1 | "I'm at capacity" at busy moments | Free model tiers allow a few requests a minute and a few thousand tokens a minute, per model | Turn on a paid tier. Only the numbers in `LLM_MODEL_LIMITS` change; the router already spreads load over models and falls back across providers |
| 2 | Searches "paused until tomorrow" | Free search APIs are a few hundred calls a month in total | Paid plans, or more providers in `JOBSEARCH_PROVIDER_ORDER`. Caching (6 h per search, 24 h per posting) already removes repeats; raise `JOBSEARCH_*_QUOTA` with the plan |
| 3 | Slow or dropped streams when several people chat at once | One sync worker thread per open stream on a small instance | A bigger instance and more workers first (cheap). Then see "Stateless API nodes" |
| 4 | Database connection limits | Each stream holds a session; checkpointing uses its own pool | Use Neon's pooled endpoint (already supported: `prepare_threshold=None`), cap `max_size` in `app/assistant/checkpoints.py` |
| 5 | Vector search gets slower than about 50 ms at p95 | pgvector HNSW on one database | See "Vectors" |

## Around 10,000 users

- **Paid model and search tiers.** Catalog numbers only. Nothing in the code changes.
- **Rate-limit counters in Redis.** The ledger and `RateLimiter` are small interfaces
  (`reserve/settle`, `consume`). Postgres row locks are fine to a few hundred requests a second;
  past that, put the counters in Redis token buckets behind the same interfaces.
- **Stateless API nodes.** Today a run lives in the API process that started it, which is why a
  second node could not take over a stream. Move run execution to a worker queue (Postgres-backed
  `procrastinate`, or Redis) and have API nodes relay events from pub/sub. The graph already
  checkpoints every step, so a worker can resume a run another worker started.
- **Infrastructure.** A paid API instance, two or more of them; Neon's pooler; a read replica for
  analytics-style reads. Add OpenTelemetry traces (every model and tool call already logs a
  `run_id`, `model`, `latency_ms` and token counts, never content).
- **Quotas.** The per-user allowances in `app/services/quotas.py` stay; raise them by plan.

## Around 1,000,000 users

- **Partition the big tables** by user hash: `chat_messages`, `resume_chunks`,
  `provider_usage_events`. Every query already carries a `user_id`, so the partition key is
  always known.
- **Vectors.** `ResumeChunkRepository.similar()` is the one place that knows how vectors are
  stored and searched. If pgvector's p95 passes about 50 ms, swap that method for a dedicated
  vector store. Nothing else changes.
- **More workers, per-tenant budgets.** Give teams their own model budgets and rate limits.
- **The job cache is a shared asset.** `job_postings` is global, so more users make it cheaper per
  user, not costlier.
- **Compliance (India, DPDP Act).** Consent copy at sign-up for sending text to model providers,
  a deletion service-level agreement (the maintenance sweep and `storage_admin gc` already remove
  old data and orphaned files; an account deletion needs to trigger them at once), and an audit
  log of who confirmed which write. Writes already leave a `chat_pending_actions` row.

## Cost visibility

`uv run python -m app.scripts.llm_admin usage --since 30d --by model,task --price-in 0.1 --price-out 0.4`
prints calls, errors, tokens and latency per model and task, and, with the prices you pass in
(dollars per million tokens), an estimate of what the same traffic would cost on a paid tier.
Prices are not built in because they differ per model and change; take them from the provider's
pricing page.
