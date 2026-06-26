# Conventions

## Naming

- Modules/functions/variables: `snake_case`. Classes: `PascalCase`. Constants: `UPPER_SNAKE_CASE`.
- Test functions: `test_<subject>_<scenario>`. <!-- enforce: regex pattern="^def test_" scope="**/test_*.py" -->

## Types & interfaces

- Public functions are fully type-annotated. Tier engines implement the shared `Locator` protocol and return the common `CodeSpan` / `Citation` shapes — callers never branch on which engine ran.

## Errors & failure posture

- Prefer graceful degradation over raising (see guardrails.md): fall back a tier and attach a confidence flag rather than hard-failing a `locate`.
- When wrapping a foreign exception, preserve the cause (`raise ... from err`).

## Tests

- pytest. Test files are `test_*.py`, kept next to the package under test unless a top-level `tests/` root is added later (no test root configured yet).
- Cover the fallback paths explicitly: parser-missing → ripgrep, model-down → Tier 0, gate-fail → escalation.

## Logging

- Use the standard `logging` module. Never log secrets, repo source content, or full file contents at info level. Keep stdout clean on the stdio MCP transport (logs go to stderr).
