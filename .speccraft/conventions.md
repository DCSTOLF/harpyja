# Conventions

## Naming

- Modules/functions/variables: `snake_case`. Classes: `PascalCase`. Constants: `UPPER_SNAKE_CASE`.
- Test functions: `test_<subject>_<scenario>`. <!-- enforce: regex pattern="^def test_" scope="**/test_*.py" -->

## Types & interfaces

- Public functions are fully type-annotated. Tier engines implement the shared `Locator` protocol and return the common `CodeSpan` / `Citation` shapes — callers never branch on which engine ran.

## Config & immutable state

- Config is a frozen dataclass (`Settings`). Produce overrides with `dataclasses.replace`, never mutation — every override returns a new instance.
- Layer precedence is explicit and one-directional: defaults < `harpyja.toml` < `HARPYJA_*` env < per-request override. `harpyja.toml` keys mirror `Settings` field names; values are coerced to the field's declared type.

## Errors & failure posture

- Prefer graceful degradation over raising (see guardrails.md): fall back a tier and attach a confidence flag rather than hard-failing a `locate`.
- Graceful degradation has a floor: when a *hard precondition* for a tier is absent and there is no honest degraded answer to give, fail loudly with a typed, actionable error naming the missing dependency — never a silent empty result that reads as "nothing found." (e.g. `rg` missing → `RipgrepMissingError` on search/locate, surfaced by `doctor`; `index` does not require `rg` and still succeeds.) The same honesty rule means distinct failure causes get distinct caller-visible notes, never one collapsed empty result (e.g. unrecognized `language_hint` vs null-language exclusion).
- When wrapping a foreign exception, preserve the cause (`raise ... from err`).

## Tests

- pytest. Test files are `test_*.py`, kept next to the package under test unless a top-level `tests/` root is added later (no test root configured yet).
- Cover the fallback paths explicitly: parser-missing → ripgrep, model-down → Tier 0, gate-fail → escalation.
- Drive async code from sync tests with `asyncio.run(...)` rather than adding an async-test plugin (no `pytest-asyncio` dependency). See `server/test_app.py`, `server/test_stdio_hygiene.py`.
- Keep tests network-free by injecting collaborators: pass a `resolver` to `assert_local` and a `which` to `run_doctor` instead of touching live DNS or `PATH`. Default to the real implementation, override in tests.
- Mark tests that spawn a real process or event loop with `@pytest.mark.integration` (declared in `pyproject.toml`) so they are skippable in constrained environments.

## Filesystem & artifacts

- Harpyja is read-only on **source** files. The manifest and symbol index are *derived artifacts* and are the only sanctioned writes: default to `<repo>/.harpyja/` with a self-ignoring `.gitignore` of `*` (never modify the repo's root `.gitignore`); fall back to `${XDG_CACHE_HOME:-~/.cache}/harpyja/<repo-hash>/` when the repo dir is unwritable.
- Durable artifact writes are atomic: write to a temp file **in the same directory** as the final file, then `os.replace`. The same-dir requirement is load-bearing — it keeps the rename atomic on one filesystem, including the external-cache fallback, so a crash can't leave a truncated artifact.
- Files that must be byte-reproducible (e.g. `manifest.jsonl`) are written with a fixed key order and a stable sort, so two runs over an unchanged tree diff cleanly.

## Logging

- Use the standard `logging` module. Never log secrets, repo source content, or full file contents at info level. Keep stdout clean on the stdio MCP transport (logs go to stderr).
