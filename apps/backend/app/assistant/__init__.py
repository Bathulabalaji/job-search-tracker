"""The AI assistant: a LangGraph agent over the user's own data, streamed as SSE.

- `prompts`  system prompt, guardrail prompt, decline template
- `tools`    read-only tools wrapping the existing services (user-scoped by construction)
- `context`  token-budgeted history window plus a rolling summary
- `graph`    guardrail -> (decline | agent <-> tools)
- `runner`   runs one turn: persistence, SSE events, failure handling, resume
"""
