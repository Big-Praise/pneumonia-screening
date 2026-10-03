# Tools & Capabilities Guidance (v2)

## Standard Claude Code tools (no setup)
- File read/write/edit, Bash/terminal (install deps, run streamlit, run checks),
  search/grep.

## Subagents (context isolation — recommended)
Define in `.claude/agents/<name>.md`:
- **verify-milestone** — after each milestone, run the app + the acceptance
  checks in docs/TESTING.md; report pass/fail + issues only.
- **security-reviewer** — before finishing auth/DB work, check: passwords
  hashed not plaintext, no secrets hard-coded, no external calls at inference,
  no patient data logged.
- **code-simplifier** — readability pass on finished modules.

## MCP servers (ask first)
Not required for v2. If the user later wants cloud storage, a hosted Postgres, or
a docs connector to auto-generate the report, propose it before wiring it. Any
MCP that would move images/patient data off-machine must be flagged against
GUARDRAILS first.

## Hard tool boundaries (tie to GUARDRAILS)
- No tool sends images or patient data to an external service.
- No network calls for inference — model runs locally.
- No tool commits secrets or real patient-identifying data.

## Anthropic SDK / API note
The pneumonia model is a local Keras model, not an LLM — no Anthropic API at
runtime. IF a future feature wants an LLM (e.g. turning a prediction into a
plain-language patient-friendly summary), use the Anthropic SDK with best
practice: API key in an environment variable (never hard-coded), handle errors
and rate limits, and NEVER send patient-identifying data in a prompt. Flag such a
feature for review first — it crosses the "no external data" guardrail.
