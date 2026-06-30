---
spec: "0001-wave-0-foundations"
title: "Wave 0 — Foundations"
reviewers: [codex, claude-p, opencode]
quorum: 1
verdict: approve-with-comments
generated: 2026-06-26T00:00:00Z
---

# Cross-model review — 0001-wave-0-foundations

## codex

**Verdict:** changes-requested

Concerns:
- Tool naming inconsistent: repo architecture says MCP exposes locate/read/index, spec requires `harpyja_locate`. Cite SPEC.md explicitly or it bakes in the wrong contract.
- Config includes per-request overrides, but no acceptance criterion proves request overrides work. Only `HARPYJA_LM_API_BASE` over `harpyja.toml` is tested.
- Static air-gap assertion in `doctor` is underspecified (which URLs/profiles/env it validates).
- Registration verification for Claude Code/Codex doesn't define automated vs manual vs documented-evidence vs reproducible smoke script.

Suggestions:
- Align MCP tool names with SPEC.md; criteria should reference exact schema and exact tool name.
- Add acceptance coverage for request-level config overrides and rejection of non-loopback `HARPYJA_LM_API_BASE`.
- Define `doctor` air-gap output as structured pass/fail checks including exact non-loopback failure condition.
- Clarify whether Wave 0 registers only `harpyja_locate` or all three tools as stubs; avoid optional wording for `harpyja_read`/`harpyja_index`.

## claude-p

**Verdict:** approve-with-comments

Concerns:
- Response contract delegated entirely to SPEC.md but never pinned in the spec. Criteria 5, 9, 10 hinge on "schema-valid per SPEC.md" — not objectively testable without cross-referencing SPEC.md §2.1 directly.
- `harpyja serve --http` has no specified bind address. Air-gap guardrail is enforced for outbound `ModelGateway` (`assert_local`) but silent on the inbound HTTP listener — binding `0.0.0.0` would expose the server on the network.
- "Loopback" never defined for `assert_local()` (criterion 7): `127.0.0.0/8`? `::1`? literal `localhost`? `0.0.0.0`? The accept/reject boundary for the most security-relevant function in this wave is ambiguous.
- `stdio` stdout-cleanliness requirement (logs to stderr) is load-bearing for criteria 3/5/9 — stray stdout corrupts MCP framing — yet is neither an explicit requirement nor an acceptance check.

Suggestions:
- Add an acceptance criterion exercising the per-request override precedence level (criterion 6 only tests env > toml).
- Specify `harpyja.toml` discovery location (cwd / `--config` flag / XDG / repo root).
- Pin `requires-python = ">=3.12"` explicitly; resolve "3.12" vs "3.12+" ambiguity in the spec text.
- Mark criteria 9 and 10 as manual integration checks; note where verified recipe snippets live.
- Define what `doctor`'s "static air-gap assertion" checks; tie it to the same loopback definition as criterion 7.

## opencode

**Verdict:** FAILED (non-fatal)

opencode launched but failed with `ProviderModelNotFoundError: configured model qwen/qwen3.6-35b-a3b not found`. No review signal produced. This is a tooling/config failure, not a review signal, and does not affect quorum.

---

## Synthesis

### SPEC.md finding (authoritative)

SPEC.md §2.1 explicitly defines `harpyja_locate` by that name and pins its full output schema (`citations: list[Citation]`, `confidence: Literal["high","medium","low"]`, `tiers_run`, `elapsed_ms`, `notes`). SPEC.md §3 defines `Citation(CodeSpan)` with all field names and types. Therefore:

- **codex concern #1 (tool naming) is resolved.** `harpyja_locate` is correct; "locate/read/index" in architecture prose is shorthand.
- **claude-p concern #1 (schema pinning) is mitigated.** "Schema-valid per SPEC.md" is objectively testable. Downgraded to a convenience suggestion: quote or cross-reference the relevant SPEC.md section number in criteria 5/9/10.

### Quorum

Quorum is met. claude-p returned `approve-with-comments`. codex returned `changes-requested`, but its primary blocker (tool naming) is resolved by the SPEC.md finding; remaining concerns overlap with claude-p's suggestions and are tightening edits, not spec-level blockers.

### Prioritized concerns

**Near-blocking — address before planning:**

1. **Inbound HTTP bind address unspecified (claude-p, unique).** Criterion 4 says `harpyja serve --http --port <p>` with no bind constraint. Binding `0.0.0.0` would violate the project's air-gap guarantee from the inbound side. The spec must assert loopback-only bind (e.g., `127.0.0.1`) and add an acceptance check or note.

2. **`assert_local()` loopback definition missing (claude-p, unique).** Criterion 7 says "passes for a loopback endpoint and raises for a non-loopback endpoint" but never defines the boundary. SPEC.md §3.6 only says "non-loopback and `allow_remote` is False." The spec should enumerate what counts as loopback: `127.0.0.0/8`, `::1`, and optionally `localhost` as a resolved alias; and what the rejection condition is for `0.0.0.0` / any routable address.

**Moderate — fix in the same pass (low effort, high clarity):**

3. **Per-request override not tested (codex + claude-p, agreement).** Criterion 6 exercises only `HARPYJA_*` env > `harpyja.toml`. The fourth precedence level (per-request override) has no acceptance criterion. Add one, even a unit test: pass a request-level field and assert it wins over the env value.

4. **`doctor` air-gap assertion underspecified (codex + claude-p, agreement).** Criterion 8 says "air-gap status (pass/fail)" without stating what is checked. Tie it explicitly to the same loopback definition as criterion 7 (once that is defined): `doctor` should report pass when `api_base` resolves to loopback, fail when it does not, with no live call.

5. **stdout cleanliness not an explicit requirement (claude-p, unique).** Stray stdout from the server process will corrupt MCP framing over stdio. Add a requirement and/or acceptance note: all server logging MUST go to stderr; stdout is reserved for MCP protocol frames.

6. **`harpyja.toml` discovery path unspecified (claude-p, unique).** The spec uses `harpyja.toml` without saying where it is looked up. Specify the search order (e.g., `--config` flag > cwd > `$XDG_CONFIG_HOME/harpyja/harpyja.toml`).

**Nice-to-have — deferrable to implementation:**

7. **Criteria 9/10 test modality unclear (codex + claude-p, agreement).** Mark these explicitly as manual integration checks and note where the verified recipe snippets live (e.g., `docs/recipes/`). They cannot run under `pytest`.

8. **`requires-python` ambiguity.** Spec prose says "Python 3.12" while SPEC.md header says "Python 3.12+". Pin `requires-python = ">=3.12"` in `pyproject.toml` and match the spec text.

9. **Cross-reference SPEC.md §2.1 in criteria 5/9/10.** Replace "schema-valid per SPEC.md" with "schema-valid per SPEC.md §2.1 (`citations`, `confidence`, `tiers_run`, `elapsed_ms`, `notes`)". Zero ambiguity, no functional change.

10. **`harpyja_read` / `harpyja_index` stub scope (codex, minor).** Out-of-scope section says "beyond stub registration, *if registered at all*." Decide and state: Wave 0 registers only `harpyja_locate`; `harpyja_read` and `harpyja_index` are Wave 1. Eliminates "if" ambiguity.

---

**Action:** Quorum is met; the spec is approved-with-comments and may proceed to planning. Before or during planning, apply the following minimal edits to `spec.md`:

1. Add a bind-address assertion to criterion 4: `--http` binds `127.0.0.1` only; verify with `ss`/`netstat` or a connection-refused test from a non-loopback address.
2. Define loopback for criterion 7 and the `doctor` check: `127.0.0.0/8` and `::1` pass; any other address fails unless `allow_remote=true`.
3. Add a criterion for per-request override precedence (can be a unit test).
4. Add a requirement that server logging goes to stderr; stdout is MCP-only.
5. Specify `harpyja.toml` discovery order.
6. (Optional, low cost) Cross-reference SPEC.md §2.1 in criteria 5/9/10 and mark 9/10 as manual.
