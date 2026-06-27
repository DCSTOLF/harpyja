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
- Caller-visible degrade/failure markers are **stable machine-readable identifiers**, not free prose, so callers and tests branch on the identifier rather than the wording. A cause taxonomy is an enumerated, stable set with a composable suffix that keeps otherwise-collapsible states distinct — e.g. Scout emits `scout-degraded:{connection-refused|no-endpoint-configured|backend-error}` with a `+no-matches` suffix that distinguishes "Tier-0 honestly empty" from "Tier-0 had results." (See `harpyja/scout/errors.py`, `harpyja/orchestrator/locate.py`.)
- The air-gap is enforced in **one** place only: reuse `gateway.assert_local` / `AirGapError` — never introduce a parallel air-gap error type or a second check. A new outbound path (e.g. `ModelGateway.complete()`) asserts loopback on **resolved** addresses *before* any I/O leaves the process; a non-loopback endpoint is a loud floor error, never a degrade note.
- Third-party in-process code that can open its own socket is an **assumption verified by test**, never an asserted air-gap guarantee. The air-gap is enforced only at the Gateway; everything Harpyja *hands* such code is constrained to an exact positive-equality whitelist (no raw `base_url`, no env-derived endpoint, no HTTP client), and the residual in-process egress risk is backed by a network-deny integration test plus a tracked sandbox follow-up — recorded, not buried (no false-capability claim). (See `harpyja/scout/tools.py`, AC10/AC11.)
- When wrapping a foreign exception, preserve the cause (`raise ... from err`).
- No-silent-coverage lockstep: a capability's routing, its identity/cache slot, and
  its implementation ship in the **same change** — never route inputs to a capability
  ahead of the code that handles them. A routed-but-unimplemented input that parses
  to an empty result is a silent false claim ("we never looked" reading as "we looked
  and found nothing"), the same honesty violation as a silent empty result. Enforce
  with a lockstep invariant test where the two sides can drift (e.g.
  `classify.KNOWN_LANGUAGES == indexer.SYMBOL_LANGUAGES`, asserted in
  `index/test_routing.py`); until a slice ships, its inputs stay on the honest
  degraded path (null-language / ripgrep-only), never silent zero.

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
- A derived artifact that is treated as **untrusted on read** must self-authenticate against its **own generation**, not just its producer. Pair the data file with a sidecar carrying (a) a content fingerprint — a sha256 over the data file's exact bytes plus a record count — and (b) the producer identity (engine + each grammar version). On read, rebuild from source whenever the data is missing/unreadable/truncated, the sidecar is missing/unreadable, the producer identity differs, or the fingerprint mismatches. Commit the multi-file pair **data-first, sidecar-last** (each via same-dir temp + `os.replace`) so a crash residue — fresh data under a stale sidecar — fails the fingerprint and rebuilds. The producer identity alone is not enough: it misses a same-engine clean-truncation and a crash residue; the fingerprint is what binds the sidecar to *this* generation. (See `symbols/symbols_io.py`, `symbols/engine_identity.py`.)
- The producer-identity cache key enumerates **one slot per external grammar/plugin entry point**, each with a real version or a `"missing"` / `"load-error:<abi>"` sentinel, via a slot→(dist, module, load-fn) map — not a flat per-package list. Entry points that ship in the **same package share one version and move together** (bump/absence is coupled) but keep distinct identity keys; install/bump of any slot invalidates the cache and triggers a rebuild that clears stale `grammar-missing` flags. (See `symbols/engine_identity.py` `_GRAMMAR_SLOTS`; `typescript` + `tsx` share `tree-sitter-typescript`.)
- Additive dataclass / record fields are appended **last** with a default, so a legacy on-disk artifact still reads and an unchanged tree stays byte-reproducible (the field is absent from old entries, defaulted on read). E.g. the manifest per-file `degraded` field and `CodeSpan.kind`.

## Logging

- Use the standard `logging` module. Never log secrets, repo source content, or full file contents at info level. Keep stdout clean on the stdio MCP transport (logs go to stderr).
