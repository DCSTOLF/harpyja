# Domain requirement archive

Verbatim superseded requirement text demoted from a domain file by spec consolidation. Append-only.

## scout | spec 0024 | MODIFY
- Scout (Tier 1) is a model-backed locator that lets an explorer model run read-only Read/Glob/Grep exploration over a local-only model reached through the Gateway; it preserves the read-only and air-gap guarantees and is invoked only on explicit opt-in. (spec 0005)

## scout | spec 0024 | MODIFY
- Scout hands its backend exactly the whitelist — bounded read-only Read/Glob/Grep wrappers plus the loopback-enforced Gateway model client — and never a raw `base_url`, env-derived endpoint, HTTP client/session, or other transport; the backend's own in-process egress containment is an assumption verified by a network-deny integration test, not an asserted guarantee. (spec 0005)

## scout | spec 0024 | MODIFY
- Backend output is parsed from the `<final_answer>` text (FC invoked `citation=False`, FastContext unpatched, `scout/` the only wire-format owner): a `path:start[:end]` ref → spanned `CodeSpan`, while a bare `path` or a malformed/non-numeric line → a file-level `CodeSpan` (no fabricated range); refs are normalized, clamped, and repo-confined, with out-of-repo/nonexistent/over-budget/duplicate refs dropped (bounded by `scout_max_citations` clamped to `min(scout_max_citations, req.max_results)` and `scout_max_span_lines`). (specs 0005, 0011)

## scout | spec 0024 | MODIFY
- Degrade notes are stable machine-readable identifiers (`scout-degraded:connection-refused`, `scout-degraded:no-endpoint-configured`, `scout-degraded:backend-error`, optionally suffixed `+no-matches`), never free prose. (spec 0005)

## scout | spec 0024 | MODIFY
- Scout drives the real FastContext agent (Microsoft's Read/Glob/Grep exploration loop via `make_fastcontext_agent`), not `dspy.RLM` — the distinct engine that keeps Tier 1 structurally separate from Tier 2; Scout is never routed through Deep's machinery. (spec 0007)

## scout | spec 0025 | REMOVE
- The default FastContext client has two paths behind the unchanged synchronous `ScoutBackend` seam: Path A (primary, in-process) lazily imports the package and bridges `await agent.run(prompt, max_turns, citation=...)` via `asyncio.run`; Path B (fallback) drives the `fastcontext` CLI as a subprocess via an injected runner when the package isn't importable. (spec 0007)

## scout | spec 0025 | MODIFY
- Scout uses the FastContext fine-tune selected by `FC_MODEL`, mapped from the Scout-specific `scout_model` setting (not the shared `lm_model`); FastContext config (`FC_*`) is derived from `Settings`, never ambient env. (spec 0007)

## scout | spec 0025 | REMOVE
- Because `make_fastcontext_agent` is env-only (no per-call config seam) and `FC_REASONING_EFFORT` is read lazily per model call, Path A sets `FC_*` in process env only while holding a Scout single-flight lock spanning the entire `agent.run()` (serializing Scout, accepted on the single-GPU profile); Path B scopes env to the child process. This env-injection latitude is Scout-only and must not leak to Deep. (spec 0007)

## scout | spec 0024 | MODIFY
- `gateway.assert_local` fires on the resolved `FC_BASE_URL` before the agent is constructed (Path A) and before the subprocess is spawned (Path B), using the single air-gap helper; zero non-loopback egress is proven by a network-deny test. (spec 0007)

## scout | spec 0025 | REMOVE
- The FastContext `trajectory_file` resolves to a temp path outside the scanned repo; an end-to-end run leaves the scanned repo byte-unchanged (read-only verified by test), and the residual in-process write risk is recorded. (spec 0007)

## scout | spec 0024 | MODIFY
- Scout degradation has four distinct stable causes — `fastcontext-missing` (package not importable), `cli-missing` (Path A unavailable and no CLI on PATH), `connection-refused` (endpoint down), `backend-error` (agent/CLI ran but failed) — mapped to `ScoutUnavailable` and the four-state Tier-0 floor; `ScoutUnavailable` is raised only for typed infra failure (any unexpected backend exception included), never for weak/empty citations, and a missing `rg` surfaces as the `RipgrepMissingError` floor. (spec 0007)

## scout | spec 0025 | REMOVE
- Scout result resolution is text-level: ≥1 parseable ref → normalize (dropped refs counted, no silent coverage); no parseable ref → honest-empty `[]` (not a raise); only a genuine `agent.run` exception → `ScoutUnavailable(backend-error)`. (spec 0011)

## scout | spec 0025 | MODIFY
- `parse_final_answer`/`normalize_spans` return a per-shape text-ref tally (spanned / file-level / dropped) as metadata on the Scout result so the bare-path frequency and every drop are visible and no drop is silent. (spec 0011)

## scout | spec 0025 | REMOVE
- Before dropping a Scout citation whose path does not resolve in the repo, `normalize.py` attempts deterministic bounded suffix recovery against the repo's indexed manifest file set: for `k` from the cited path's segment count down to `MIN_TAIL_SEGMENTS` (=2), match manifest files whose repo-relative path equals or segment-aligned-ends-with the last `k` segments; exactly one match at the longest `k` (whose leading segment is a known top-level manifest entry) recovers to that path, while more-than-one (ambiguous) or none drops. A recovered span is re-validated by repo-confine + `is_file` (+ line-range clamp). With no/empty file set, recovery is skipped (spec-0011 drop), and recovery only ever adds keeps. (spec 0012)

## scout | spec 0025 | REMOVE
- A recovered citation keeps its shape bucket and is tracked orthogonally by shape (`recovered_spanned` / `recovered_filelevel`) on the `ScoutTally`; a recovered file-level citation still carries `gate-skipped:no-line-range`, is never read-back-verified, and never produces a high-confidence/verified gate result — a recovered keep reads no more confidently than a non-recovered one. (spec 0012)

