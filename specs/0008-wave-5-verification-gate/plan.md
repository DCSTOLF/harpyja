---
spec: "0008"
status: planned
strategy: tdd
---

# Plan — 0008 Wave 5: Verification Gate + Tier-0→1→2 auto-escalation

## Approach / design decisions

This wave is orchestration-only; tier internals (Tier-0 seed, Scout, Deep) are
untouched. Four new seams, all injected so unit tests stay network- and
model-free:

- **`harpyja/orchestrator/classify.py`** — `classify_query(query) -> Classification`
  (`Classification = Literal["point","broad"]`). Heuristic only this wave;
  ambiguous → `"point"`. The classifier is a pluggable callable seam
  (`locate(..., classifier=classify_query)`) so a model classifier can replace it
  later without touching the matrix or ACs.
- **`harpyja/orchestrator/matrix.py`** — `plan_ladder(mode, classification, index_ready) -> list[int]`
  backed by a single `_MATRIX` dict literal holding all 12 rows. This is the
  **single source of truth** for routing; `locate` and tests both read it, the
  escalation bullets are derived from it.
- **`harpyja/orchestrator/gate.py`** — `VerificationGate` with
  `verify(query, citations, *, settings, gateway, judge=None) -> GateOutcome`
  (`GateOutcome(passed, score, scored_count, dropped_count, failed)`). It reads
  the **cited lines back from disk**, scores the **top-N** (`verify_top_n`) via an
  **injected judge seam** `Judge = Callable[[str, str], float]`. The default judge
  routes through `ModelGateway.complete()` (the one outbound caller) and the gate
  **additionally** calls `gateway.assert_local()` on the resolved `scout_model`
  endpoint **before** the judge call (belt-and-suspenders, still the one helper —
  no parallel air-gap type). Unit tests inject a fake judge so no model is needed.
- **Ladder wiring in `harpyja/orchestrator/locate.py`** — the `mode=auto` branch
  becomes classifier → `plan_ladder` → execute (seed → Scout → gate → Deep), with
  the empty-case split and the pinned gate-scoring-failed contract. `fast` gains
  the informational gate; `deep` is unchanged.

### Decision — AC13 validation location

`verify_method` is validated in **`Settings.__post_init__`** (a frozen-dataclass
post-init that raises a typed `UnsupportedVerifyMethod(ValueError)` naming the
field and the accepted set `{"scout_model"}`). Rationale: `__post_init__` fires on
**every** construction path — defaults, `harpyja.toml`, `HARPYJA_*` env, and
per-request `dataclasses.replace` overrides — so an unsupported value is rejected
uniformly with one seam, with no silent fall-through to `scout_model` and no inert
no-op. The default `"scout_model"` passes, so all existing `Settings()` callers are
unaffected. (Alternative considered: an explicit validate step inside
`load_settings`/`resolve_settings` — rejected because it would miss the
per-request `replace` path and need duplicating in two functions.)

### Decision — confidence `degraded` vs `low` reconciliation

The existing Scout **typed-unavailable** path stays **UNCHANGED**: `_degrade(...)`
keeps returning `confidence="degraded"` with `scout-degraded:<cause>`. The
confidence map's `low` rows are the **new gate-related** states only:
honest-empty seed-empty (`gate-skipped:scout-empty+no-matches`), query-only-empty,
and any `gate-low-confidence` / `gate-scoring-failed` flag. Tests must **not**
assert `low` on the typed-unavailable degrade path — that path remains
`"degraded"`. This is called out explicitly so AC8/AC9 do not collide.

### Decision — `index_ready` derivation

`index_ready` is computed **inside `locate()`** from the artifacts already loaded
there: `index_ready = bool(manifest) and symbol_records is not None` (manifest
built *and* `load_symbols_or_none` returned records). When false, `plan_ladder`
drops the leading `0` and the seed step is skipped (model tier runs query-only) —
a routing variant, not a floor failure.

### Decision — AC1 lockstep ordering

Removing `_MODE_NO_EFFECT` and wiring the classifier→matrix→ladder for `mode=auto`
land in **one** RED→GREEN pair (T09→T10). There is never a committed state where
`auto` neither emits the old `_MODE_NO_EFFECT` lock nor honors the new contract —
the Wave-0 zero-call lock and the new AC1 contract swap atomically.

## Test-first sequence

### Step 1 — Settings verify_* fields + AC13 rejection (RED)
- Add to `harpyja/config/test_settings.py`:
  - `test_settings_has_verify_defaults` — `Settings().verify_method == "scout_model"`,
    `verify_threshold == 0.6`, `verify_top_n == 3`.
  - `test_verify_method_rejects_unsupported_value` — `load_settings` with
    `environ={"HARPYJA_VERIFY_METHOD": "embedding"}` raises `UnsupportedVerifyMethod`
    whose message names `verify_method` and the accepted set `{"scout_model"}`.
  - `test_verify_method_arbitrary_value_rejected` — `Settings(verify_method="model_judge")`
    and an arbitrary string both raise (no silent fall-through).
  - `test_verify_method_scout_model_loads_clean` — `Settings(verify_method="scout_model")`
    constructs without error.
- Tests fail: fields don't exist; no validation seam.
- AC: 13.

### Step 2 — Settings verify_* fields + __post_init__ validation (GREEN)
- Implement in `harpyja/config/settings.py`: append `verify_method: str = "scout_model"`,
  `verify_threshold: float = 0.6`, `verify_top_n: int = 3` **last**; add
  `_VERIFY_METHODS = {"scout_model"}`, `class UnsupportedVerifyMethod(ValueError)`,
  and `__post_init__` raising it when `verify_method` is unsupported. Extend `_coerce`
  to handle `float`.
- All Step-1 tests pass.
- AC: 13.

### Step 3 — Query classifier point/broad (RED)
- Add `harpyja/orchestrator/test_classify.py`:
  - `test_classify_point_query_returns_point` — representative point lookups
    (e.g. `"where is parse_config defined"`) → `"point"`.
  - `test_classify_broad_query_returns_broad` — broad/trace/audit phrasings
    (e.g. `"trace the request lifecycle"`, `"audit all auth checks"`) → `"broad"`.
  - `test_classify_ambiguous_returns_point` — an ambiguous query biases to `"point"`.
- Tests fail: module `classify` does not exist.
- AC: 2.

### Step 4 — Classifier heuristic + seam (GREEN)
- Implement `harpyja/orchestrator/classify.py`: `Classification` literal,
  `classify_query(query) -> Classification` heuristic (broad/trace/audit triggers),
  ambiguous → `"point"`. Pluggable callable signature documented as the seam.
- All Step-3 tests pass.
- AC: 2.

### Step 5 — Planning matrix, all 12 rows (RED)
- Add `harpyja/orchestrator/test_matrix.py`:
  - `test_matrix_all_twelve_rows` — parametrized over every
    `(mode, classification, index_ready)` asserting `plan_ladder(...)` equals the
    spec table's planned ladder (incl. every `index_ready=false` row dropping the
    leading `0`, and `fast`+`broad` ⇒ `[0,1]`).
  - `test_matrix_index_not_ready_drops_leading_zero` — focused check on the
    seed-skip variant for `auto`+`point`.
- Tests fail: module `matrix` does not exist.
- AC: 3.

### Step 6 — Planning matrix single source of truth (GREEN)
- Implement `harpyja/orchestrator/matrix.py`: `_MATRIX` dict with all 12 rows and
  `plan_ladder(mode, classification, index_ready) -> list[int]`.
- All Step-5 tests pass.
- AC: 3.

### Step 7 — VerificationGate: scoring, top-N, air-gap, scoring-failed (RED)
- Add `harpyja/orchestrator/test_gate.py` (unit, fake judge injected):
  - `test_gate_passes_when_score_at_or_above_threshold` — judge returns `0.9`,
    `threshold=0.6` → `GateOutcome.passed is True`, `failed is False`.
  - `test_gate_fails_when_score_below_threshold` — judge returns `0.3` →
    `passed is False`.
  - `test_gate_scores_at_most_top_n_and_logs_dropped` — 5 citations, `verify_top_n=3`
    → judge invoked ≤ 3 times and `caplog` records the dropped count `2`
    (`dropped_count == 2`); a bounded scan is distinguishable from a full one.
  - `test_gate_asserts_local_before_judge` — a non-loopback `scout_model` endpoint
    → `AirGapError` raised and the injected judge is **never called** (call counter
    stays 0).
  - `test_gate_scoring_failed_when_judge_raises` — judge raises → `GateOutcome.failed
    is True`, no exception escapes, `passed is False` (cannot vouch).
- Tests fail: module `gate` does not exist.
- AC: 10 (unit half), 11; gate primitives for 5/6.

### Step 8 — VerificationGate implementation (GREEN)
- Implement `harpyja/orchestrator/gate.py`: read cited lines back from disk, bound to
  `verify_top_n` (log dropped count via `logging`), score each via the injected
  `Judge` (default routes through `gateway.complete()`), call `gateway.assert_local()`
  **before** the judge, `passed = score >= verify_threshold`, map any judge exception
  to `GateOutcome.failed=True` (never raise, never silently pass). `AirGapError`
  propagates as a floor.
- All Step-7 tests pass.
- AC: 10 (unit), 11.

### Step 9 — AC1 lockstep: remove `_MODE_NO_EFFECT`, wire `auto` (RED)
- Extend `harpyja/orchestrator/test_locate.py` (inject `FakeEngine` Scout/Deep, a
  fake judge, and a loopback `ModelGateway`):
  - `test_locate_auto_gated_pass_runs_zero_one` — point query, gate passes →
    `tiers_run == [0,1]` and the deep engine's `.run` is **never** invoked.
  - `test_locate_auto_gate_fail_escalates_to_deep` — point query, gate fails →
    `tiers_run == [0,1,2]`.
  - `test_locate_auto_broad_routes_straight_to_deep` — broad query → `tiers_run ==
    [0,2]`, Scout engine **not** called, no gate.
  - `test_locate_auto_index_not_ready_gated_pass_is_one` — `index_ready=false`,
    gate passes → `tiers_run == [1]`.
  - `test_locate_auto_index_not_ready_escalated_is_one_two` — `index_ready=false`,
    gate fails → `tiers_run == [1,2]`.
  - `test_locate_auto_no_longer_emits_mode_no_effect` — `notes` never contains the
    old `mode has no effect` lock.
- Tests fail: `auto` still returns `[0]` + `_MODE_NO_EFFECT`; no ladder wiring.
- AC: 1, 4, 5, 6, 7 (broad half).

### Step 10 — AC1 lockstep: ladder execution for `auto` (GREEN)
- Implement in `harpyja/orchestrator/locate.py`: delete `_MODE_NO_EFFECT`; in the
  `auto` branch derive `index_ready` (manifest + symbols), call
  `classifier(req.query)` and `plan_ladder(...)`, then execute the planned ladder
  (seed if `0` present → Scout → gate → Deep). Add injected params
  `gateway`, `judge`, `classifier=classify_query` to `locate(...)` (additive,
  defaulted). Gate decides whether the trailing Tier-2 step runs; realized
  `tiers_run` is the executed prefix. This is the **same change** that retires the
  Wave-0 zero-call lock.
- All Step-9 tests pass.
- AC: 1, 4, 5, 6, 7.

### Step 11 — Empty-case split + gate-scoring-failed contract (RED)
- Extend `harpyja/orchestrator/test_locate.py`:
  - `test_locate_auto_scout_typed_unavailable_degrades` — Scout raises
    `ScoutUnavailable(cause)` → `tiers_run == [0]`, note `scout-degraded:<cause>`,
    `confidence == "degraded"` (UNCHANGED, **not** `low`), **no** escalation.
  - `test_locate_auto_scout_honest_empty_skips_gate_returns_seed` — Scout returns
    `[]` cleanly, seed has matches → `tiers_run == [0,1]`, note contains
    `gate-skipped:scout-empty`, Deep **not** invoked.
  - `test_locate_auto_scout_honest_empty_query_only_is_one` — same with
    `index_ready=false` → `tiers_run == [1]` (seed-empty vs query-only-empty not
    collapsed).
  - `test_locate_auto_scout_honest_empty_no_matches_suffix` — empty seed →
    note carries `gate-skipped:scout-empty+no-matches`.
  - `test_locate_auto_scout_malformed_escalates` — malformed Scout result →
    `tiers_run == [0,1,2]`.
  - `test_locate_auto_gate_scoring_failed_escalates_retains_flag` — judge errors →
    `tiers_run == [0,1,2]`, note contains `gate-scoring-failed`, `confidence == "low"`.
- Tests fail: empty-case split and scoring-failed contract not yet wired.
- AC: 8.

### Step 12 — Empty-case split + scoring-failed routing (GREEN)
- Implement in `harpyja/orchestrator/locate.py`: three-way Tier-1 outcome split
  (typed-unavailable → existing `_degrade`; honest-empty → skip gate, return seed
  with `gate-skipped:scout-empty` [+`no-matches`]; malformed → escalate); the
  pinned gate-scoring-failed contract (in `auto`, a tier remains → escalate to
  Tier-2, retain `gate-scoring-failed`, `confidence=low`).
- All Step-11 tests pass.
- AC: 8.

### Step 13 — fast informational gate + gate-low-confidence (RED)
- Extend `harpyja/orchestrator/test_locate.py`:
  - `test_locate_fast_never_escalates_even_for_broad` — `fast`+broad, gate would
    fail → `tiers_run == [0,1]` (never Tier-2), note `gate-low-confidence`.
  - `test_locate_fast_gate_would_fail_flags_low_confidence` — `fast`+point, gate
    would fail → Tier-1 result returned with `gate-low-confidence`.
  - `test_locate_fast_gate_pass_no_flag` — gate passes → no `gate-low-confidence`.
  - `test_locate_fast_honest_empty_no_low_confidence_flag` — Scout honest-empty →
    `gate-skipped:scout-empty`, **not** `gate-low-confidence`.
  - `test_locate_fast_gate_scoring_failed_best_effort_tier1` — judge errors in
    `fast` (no further tier) → best-effort un-gated Tier-1 + `gate-scoring-failed`,
    `confidence == "low"`.
- Tests fail: `fast` informational gate not wired.
- AC: 7, 8 (fast branch).

### Step 14 — fast informational gate implementation (GREEN)
- Implement in `harpyja/orchestrator/locate.py`: run the gate informationally in
  `fast` (only when Scout returned scoreable citations); emit `gate-low-confidence`
  when it would fail; never climb; handle `gate-scoring-failed` best-effort branch.
- All Step-13 tests pass.
- AC: 7, 8.

### Step 15 — confidence map + stable flag ids (RED)
- Extend `harpyja/orchestrator/test_locate.py`:
  - `test_locate_confidence_gated_pass_high` — `[0,1]`/`[1]` clean → `high`.
  - `test_locate_confidence_honest_empty_medium_or_low` — seed-has-matches →
    `medium`; `+no-matches` → `low` (explicitly distinct from the gated-pass that
    shares `[0,1]` tokens).
  - `test_locate_confidence_escalated_medium` — `[0,1,2]`/`[1,2]` → `medium`.
  - `test_locate_confidence_broad_deep_medium` — `[0,2]`/`[2]` → `medium`.
  - `test_locate_confidence_flag_override_low` — any `gate-low-confidence` /
    `gate-scoring-failed` → `low` override.
  - `test_locate_flag_ids_are_stable_strings` — `gate-low-confidence`,
    `gate-scoring-failed`, `gate-skipped:scout-empty` asserted as exact identifier
    strings (not wording).
- Tests fail: confidence not yet derived from terminal-tier + flags.
- AC: 9.

### Step 16 — confidence derivation (GREEN)
- Implement in `harpyja/orchestrator/locate.py`: derive `confidence` from terminal
  tier + flags per the map (flags override to `low`); keep the typed-unavailable
  path at `"degraded"`.
- All Step-15 tests pass.
- AC: 9.

### Step 17 — Refactor: confidence/flag helper (REFACTOR, optional)
- Extract the repeated confidence-from-(tier, flags) logic and flag-id constants
  into module-level constants/helper in `harpyja/orchestrator/locate.py` (or a small
  `flags.py`) to remove duplication introduced by Steps 12/14/16.
- All tests still pass.

### Step 18 — Production wiring for the gate/judge (GREEN, preceded by Steps 19/20 RED)
- Add `harpyja/orchestrator/wiring.py` (or extend existing wiring): build the
  `VerificationGate` + default `scout_model` judge from `Settings` and inject into
  `locate`'s default `gateway`/`judge` so the server path constructs them. No new
  unit assertions beyond integration coverage below.
- AC: enables 10 (integration), 12.

### Step 19 — Air-gap network-deny integration (RED, [integration])
- Add `harpyja/orchestrator/test_gate.py`:
  - `test_gate_network_deny_zero_egress` — `@pytest.mark.integration`, skip-not-fail:
    end-to-end on a loopback-only `scout_model` endpoint, assert **zero** non-loopback
    egress from the gate (Scout/Deep network-deny pattern).
- Fails (or skips) until production wiring (Step 18) exists.
- AC: 10 (integration half).

### Step 20 — End-to-end `auto` over the real stack (RED, [integration])
- Add `harpyja/orchestrator/test_locate.py`:
  - `test_locate_auto_end_to_end_point_cheap` — `@pytest.mark.integration`,
    skip-not-fail: a point query resolves `[0,1]`, no Tier-2, confined citations.
  - `test_locate_auto_end_to_end_broad_to_deep` — a broad query routes `[0,2]`
    (straight to Deep, not a gate-driven climb), confined citations.
- Fails (or skips) until production wiring (Step 18) exists.
- AC: 12.

(Steps 19 and 20 are written RED before Step 18's GREEN wiring makes them pass;
both are `@pytest.mark.integration` and skip — not fail — in constrained envs.)

## Delegation

- Steps 7–8 (gate air-gap + `ModelGateway` judge routing) → delegate to a
  gateway/air-gap-savvy agent (reason: reuses the exact `assert_local` belt-and-
  suspenders pattern proven in 0006/0007; one helper, no parallel check).
- Steps 19–20 (`@pytest.mark.integration` network-deny + real-stack) → delegate to
  the integration-test agent (reason: network-deny harness + skip-not-fail
  discipline match its strength).
- Steps 1–6, 9–17 (Settings, classifier, matrix, ladder wiring) → general Python
  implementer (reason: pure orchestration, fakes-only, no model).

## Risk

- **AC1 lockstep window** → mitigation: T09 RED + T10 GREEN are one pair; the
  `_MODE_NO_EFFECT` removal and the new `auto` contract land together, asserted by
  `test_locate_auto_no_longer_emits_mode_no_effect`.
- **`confidence` `degraded` vs `low` confusion** → mitigation: explicit test
  (`test_locate_auto_scout_typed_unavailable_degrades`) pins the typed-unavailable
  path at `"degraded"`; the map's `low` rows are gate-states only.
- **`__post_init__` firing on every `replace`** → mitigation: default
  `"scout_model"` is valid, so all existing construction stays green; only an
  unsupported value (env/toml/per-request) raises, which is the intended AC13
  behavior.
- **`index_ready` mis-derivation collapsing seed-empty vs query-only-empty** →
  mitigation: AC8 tests assert both `[0,1]` and `[1]` prefixes separately.
- **Judge seam leaking a real model into unit tests** → mitigation: `Judge` is an
  injected callable defaulting to the gateway-backed judge; every unit test passes
  a fake judge and a loopback `ModelGateway`, keeping the suite network-free.
