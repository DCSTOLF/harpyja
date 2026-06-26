# Guardrails

Hard rules. Violations block at the hook level when `enforce:` is set.

## Air-gap / network egress

- No network egress at runtime. Model, search, and parsing stay on the local machine; no telemetry, no external calls.
- The Model Gateway is the **only** outbound caller and must point at a loopback/localhost endpoint. Enforce the air-gap in this one place.
- Never add a non-loopback endpoint to a profile or config without an explicit, reviewed opt-out.

## Read-only locator

- Harpyja never modifies the target repository. No edits, writes, code generation, or destructive operations against indexed code.
- Host tools exposed to the Deep tier (`list_manifest`, `search`, `symbols`, `read_span`) are read-only and bounded (max lines / max matches / max files). Never add a tool that mutates the repo or escapes those bounds.

## Graceful degradation

- Every layer must have a fallback: no parser → ripgrep; no model → deterministic Tier 0; escalation failure → best-effort Tier 1 result with a confidence flag.
- Prefer a degraded, honest answer (with a confidence flag) over a hard failure. Never return a confident citation that wasn't verified when verification was available.

## Process

- Never bypass the spec-first invariant by editing files outside Claude Code.
- Never commit `.speccraft/state.json` (gitignored).
