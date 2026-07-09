---
spec: "0024-v2"
closed: 2026-07-06
---

# Changelog — 0024-v2 Scout v2 (native explorer-loop finder)

## What shipped vs spec

The FastContext-backed Scout is retired and REPLACED by a self-contained
`ExplorerBackend` Harpyja owns end-to-end — a general OpenAI-compatible
tool-calling model driven over a bounded read-only loop to a citation list,
behind the UNCHANGED `ScoutBackend`/`ScoutEngine`/`Locator` seam. No orchestrator,
gate, matrix, formatter, `engine.py`, or `normalize.py` change. All 10 ACs met.

- **AC1 (seam + DI):** `ExplorerBackend` satisfies `ScoutBackend.run(query, seed)
  -> list[CodeSpan]`, injected via the existing slot; fakes drive the loop
  deterministically; round-trips through the unchanged `normalize_spans_with_tally`.
- **AC2 (three read-only tools):** `explorer_tools.build_explorer_tools` returns
  EXACTLY `{grep, glob, read_span}` — each `confine_path`-guarded, Settings-bounded,
  read-only; `grep` wraps the SAME `symbols.ripgrep.RipgrepEngine` the Deep `search`
  host tool wraps (invariant B — one bounded rg source of truth); `read_span` reuses
  `server.tools.read_snippet`; `glob` normalizes to file-level `CodeSpan` records
  (not raw strings), bounded by `scout_glob_max_paths`; out-of-repo scope / `../`
  traversal / over-budget all rejected or clamped.
- **AC3 (context map):** `context_map.build_context_map` renders a filtered tree
  from the manifest (no file bytes pre-loop), query-injected; the
  vendor/test/generated exclusion applies to the MAP display only — an excluded file
  stays reachable via `grep`/`glob`/`read_span` (map-filter ≠ tool-scope filter).
- **AC4 (bounded loop):** `explorer_loop.run_explorer_loop` — one tool call/turn,
  raw output appended, terminates at `scout_max_turns`; an injected monotonic clock
  trips the whole-loop `scout_wall_clock_s` ceiling when turns alone would not (a
  slow/hung turn cannot wedge); unknown tool names refused, not dispatched.
- **AC5 (self-recovery + PRESERVATION):** exact `(tool_name, normalized_args)` repeat
  over `scout_loop_repeat_n` consecutive no-new-span turns → corrective injection;
  history past `scout_history_char_cap` → truncation that drops ONLY stale
  navigational chatter. The negative is proved: a final citation depending on a
  `read_span`/`grep` observation older than the bloat threshold STILL resolves after
  truncation — the dropped-span compact index is re-injected. Truncation never
  converts a real find into honest-empty.
- **AC6 (`submit_citations` terminal action):** `submit.submit_citations` +
  `SubmitCitationsSchemaError` — strict schema (unknown/extra/diagnosis-shaped fields
  rejected, the enforceable locator-not-diagnoser guard), normalized via the unchanged
  `normalize_spans`; out-of-repo/nonexistent/over-budget/malformed refs dropped; empty
  is honest-empty (no raise); no repo-read capability; spans reach `source_tier=1`
  through the unchanged engine→formatter path (backend does not stamp it).
- **AC7 (air-gap):** new `ModelGateway.complete_with_tools(messages, tools, …)`
  returning `{content, tool_calls}` routes through `assert_local` BEFORE any transport
  touch; `ExplorerBackend` also calls `gateway.assert_local()` once before the loop
  starts — a non-loopback endpoint raises `AirGapError` and the loop never starts (no
  model call, no tool call).
- **AC8 (typed degrade):** four distinct stable causes — `MODEL_UNREACHABLE`,
  `LOOP_TURNS_EXHAUSTED`, `LOOP_WALLCLOCK_EXHAUSTED`, and reused `BACKEND_ERROR` — each
  a terminal loop state routed to the Tier-0 floor; a well-formed empty
  `submit_citations` is honest-empty and does NOT raise; `AirGapError` /
  `RipgrepMissingError` propagate as floors, never degrade.
- **AC9 (degrade-rate):** exposed as a first-class reported field per the standing
  "every floor reports its rate" convention.
- **AC10 (live integration):** `test_explorer_integration.py` reuses the
  `_deny_nonloopback_egress` harness from the 0007/0014 air-gap tests — a real
  tool-calling model over a real repo returns a parsed citation list within the turn
  cap, with ZERO non-loopback egress observed (not merely asserted).

## Deviation (one)

T19/T20 added a PARALLEL production factory `wiring.build_explorer_scout_engine`
that wires `ExplorerBackend` (loopback gateway + shared `RipgrepEngine` + context
map + explorer tools + the new loop budgets) instead of swapping `build_scout_engine`
in place. The FastContext factory (`build_scout_engine`) and its eval callers are
left byte-untouched. Rationale: deleting the FastContext adapter / dependency is
explicitly out-of-scope (a dedicated cleanup spec) — a parallel factory keeps the
backend swap and the FastContext removal from entangling in one diff, and lets the
new backend be proven before the old one is deleted. T21 was an honest near-no-op:
the dispatch table was already single-source in `run_explorer_loop`, so instead of a
hollow refactor it pinned the `submit_citations` schema ↔ tool-surface coupling guard.

## Result

Both `@pytest.mark.integration` tests PASSED LIVE (Qwen3-8B on loopback Ollama,
~28s, zero non-loopback egress). Full suite: 1015 passed / 23 skipped. ruff clean.

## Files touched

- `harpyja/scout/explorer_tools.py` (+ `test_explorer_tools.py`)
- `harpyja/scout/context_map.py` (+ `test_context_map.py`)
- `harpyja/scout/submit.py` (+ `test_submit_citations.py`)
- `harpyja/scout/explorer_loop.py` (+ `test_explorer_loop.py`)
- `harpyja/scout/explorer_backend.py` (+ `test_explorer_backend.py`)
- `harpyja/scout/test_explorer_integration.py`
- `harpyja/scout/errors.py` (new cause constants)
- `harpyja/scout/wiring.py` (new `build_explorer_scout_engine` factory; FastContext
  factory left intact) (+ `test_scout_wiring.py`)
- `harpyja/gateway/gateway.py` (new `complete_with_tools`) (+ `test_gateway.py`)
- `harpyja/config/settings.py` (five provisional loop budgets) (+ `test_settings.py`)

## Out-of-scope staged follow-ups (recorded, NOT pulled in)

- AST symbol-search tool (Tier-0-as-a-tool) — the staged second round.
- The model bake-off / choosing the driving model (OQ1/OQ3 budget tuning rides here).
- The representative eval set.
- Deleting the FastContext adapter code + dependency removal (the deferred cleanup
  that closes the parallel-factory deviation above).
