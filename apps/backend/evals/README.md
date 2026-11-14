# Golden conversations

Each `golden/*.yaml` file is one conversation with scripted model behaviour and the things
that must hold afterwards. The suite (`uv run pytest tests/evals`) replays them against the
real graph, tools, services and database, with the language models replaced by scripts. It is
deterministic and free, so it runs in CI.

What it protects: scope and routing (an off-topic message never reaches the agent model), tool
wiring and arguments, confirmation before any write, the card payloads, untrusted text never
reaching a model, and graceful fallback. What it can **not** tell you is whether a real model
would pick these tools or word the answer well; that takes a live run, which is not built.

## Case format

```yaml
name: due_today
description: one line on what this protects
seed:                      # optional rows created for the signed-in user
  opportunities:
    - {company: Zepto, role: Backend Engineer, stage: applied}
turns:
  - say: "What's due today?"
    groq:                  # scripted replies, in order (guardrail first, then the agent)
      - verdict: {intent: today}
      - tool_call: {name: get_today}
      - reply: "Nothing is due today."
    google: []             # optional: the second provider
    expect:
      tools: [get_today]            # exact list of tools the turn called
      contains: ["Nothing is due"]  # in the streamed answer
      not_contains: ["error"]
      events: [cards]               # events that must appear
      no_events: [confirmation_required]
      agent_calls: 1                # model calls that were not the guardrail
      never_sent_to_a_model: ["Ignore all previous instructions"]
```
