---
spec: "0016"
status: planned
strategy: tdd
---

# Plan — 0016 scout_model

Python project. Tests: `uv run pytest`. Test files `test_*.py`, functions
`test_<subject>_<scenario>`. This is a serving/plumbing fix: two `Settings`
default VALUES flip and two CLI flags are added. No tier/gate/classifier logic
changes. All existing precedence tests must keep passing unchanged.

`[unit]` = fakes / no network. `[integration]` = `@pytest.mark.integration`,
skip-not-fail. `[doc]` = inspection-verified, no test.

## Test-first sequence

### Step 1 — Pin the flipped config defaults + drift guard (RED) `[unit]`
- Edit `harpyja/config/test_settings.py`:
  - Update the paired constant `_FC_GGUF` (line 127) from the unserved
    `hf.co/mitkox/FastContext-1.0-4B-RL-Q4_K_M-GGUF:latest` to the served
    `hf.co/dstolf/FastContext-1.0-4B-RL-Q8_0-GGUF:latest`. This alone turns the
    existing `test_settings_scout_model_default` (line 130) RED (it asserts
    `Settings().scout_model == _FC_GGUF`, and settings.py still holds the old tag).
    The sibling `assert s.scout_model != s.lm_model` invariant in that test still
    holds (Q8 Scout != Qwen Deep). (AC1)
  - Add `test_settings_lm_model_default` — asserts
    `Settings().lm_model == "hf.co/Qwen/Qwen3-8B-GGUF:latest"`. There is currently
    NO test pinning the `lm_model` default value (the existing
    `test_settings_from_args_defaults_unchanged_without_flags` is tautological), so
    this is the load-bearing RED anchor for the Deep flip. (AC2)
  - Add `test_settings_defaults_drop_unserved_tags` — AC6 drift guard by
    FIELD-DEFAULT INTROSPECTION, never a text grep: iterate
    `dataclasses.fields(Settings)` defaults (or read `Settings()` values) and assert
    no field default equals the old `mitkox/...RL-Q4_K_M` scout tag and `lm_model`
    is not `"local"`. Introspects resolved field values only, so docstrings,
    comments, and historical fixtures cannot trip a false positive. (AC6)
- Tests fail: `settings.py:77` still names the mitkox RL-Q4 tag and `settings.py:43`
  is still `"local"`.

### Step 2 — Flip the two Settings defaults (GREEN) `[unit]`
- Edit `harpyja/config/settings.py`:
  - Line 77: `scout_model` default → `"hf.co/dstolf/FastContext-1.0-4B-RL-Q8_0-GGUF:latest"`. (AC1)
  - Line 43: `lm_model` default → `"hf.co/Qwen/Qwen3-8B-GGUF:latest"`. (AC2, D2 global flip)
- Values only — `__post_init__` `_VERIFY_METHODS` gate, precedence merge, and every
  other field untouched. All Step-1 tests pass. The existing scout/lm precedence
  tests (`test_settings_scout_model_precedence` :144, `test_settings_deep_defaults`
  :163) and `Settings()` frozen-`replace` contract still pass unchanged — only the
  default value moved. (AC5 base-not-mutated is inherent to `replace`.)

### Step 3 — CLI flags + reconciliation tests (RED) `[unit]`
- Edit `harpyja/eval/test_swebench_eval.py` (extend the AC9 CLI block near :360;
  reuse the `_build_parser` / `_settings_from_args` imports at :22):
  - `test_run_subcommand_accepts_scout_and_deep_model` —
    `_build_parser().parse_args(["run","--scout-model","x","--deep-model","y"])`
    yields `args.scout_model == "x"` and the deep-model value on its own distinct
    dest. (AC3/AC4 on `run`)
  - `test_sweep_subcommand_accepts_scout_and_deep_model` — same asserts for `sweep`
    (proves both share `_add_model_flags`). (AC3/AC4 on `sweep`)
  - `test_settings_from_args_applies_scout_model` — `_settings_from_args` over a
    namespace with `scout_model="x"` gives `.scout_model == "x"`; omitting the flag
    yields the AC1 default (`Settings().scout_model`). (AC3)
  - `test_settings_from_args_deep_model_maps_to_lm_model` — `--deep-model y` alone →
    `lm_model == "y"`; `--lm-model z` alone → `lm_model == "z"` (deprecated alias
    still works). (AC4)
  - `test_settings_from_args_deep_model_wins_over_lm_model_both_orders` — build args
    with both flags in BOTH CLI orders (`--deep-model D --lm-model L` and
    `--lm-model L --deep-model D`); each resolves `lm_model == "D"`. Pins D1:
    canonical wins via distinct dests reconciled in `_settings_from_args`, not
    argparse positional last-wins. Neither flag → AC2 default. (AC4/D1)
  - `test_settings_from_args_scout_model_precedence` — explicit `--scout-model`
    beats the new default; no flag → new default; the base `Settings()` is not
    mutated (frozen-replace). (AC5)
  - `test_settings_from_args_deep_model_precedence` — same frozen-replace precedence
    pinned for the Deep flag. (AC5)
  - `test_run_help_lists_scout_and_deep_model` — parser-introspection on `run`
    (walk `_build_parser` actions or `format_help()`): option strings include
    `--scout-model` and `--deep-model`, and `--lm-model`'s help text marks it
    deprecated. No live process. (AC8)
  - `test_sweep_help_lists_scout_and_deep_model` — same for `sweep`. (AC8)
- Tests fail: `--scout-model` / `--deep-model` are unknown args (argparse errors),
  and `_settings_from_args` neither threads `scout_model` nor reconciles
  deep-vs-lm.
- Note: existing `test_settings_from_args_applies_model_overrides` (:365, uses
  `--lm-model`) and `test_settings_from_args_defaults_unchanged_without_flags`
  (:378) must remain GREEN — the alias path is preserved.

### Step 4 — Implement CLI flags + reconciliation (GREEN) `[unit]`
- Edit `harpyja/eval/swebench_eval.py`:
  - `_add_model_flags` (:881): add
    `--scout-model` (dest `scout_model`, default `None`);
    `--deep-model` (dest `deep_model`, default `None`, canonical Deep override);
    keep `--lm-model` (dest `lm_model`) with help text marking it a DEPRECATED alias
    of `--deep-model`. Distinct dests (D1) — no shared dest.
  - `_settings_from_args` (:793): add
    `if getattr(args,"scout_model",None): overrides["scout_model"]=args.scout_model`;
    reconcile Deep so canonical wins regardless of order —
    `deep = args.deep_model or args.lm_model` (getattr-guarded); if set,
    `overrides["lm_model"]=deep`. Still `replace(Settings(), **overrides)` on a fresh
    base (never mutation).
- All Step-3 tests pass; Step-1/Step-2 and the pre-existing alias tests still pass.

### Step 5 — Live served-set membership smoke (RED-as-guard) `[integration]` skip-not-fail
- Edit `harpyja/eval/test_swebench_integration.py` (reuse `_socket_reachable` at
  :47 and the `@pytest.mark.integration` pattern):
  - `test_scout_model_default_present_in_ollama_served_set` — resolve the default
    `Settings().scout_model` (no model flags), query Ollama `/api/tags` on the
    configured host (derived from `lm_api_base`, default `localhost:11434`) and do a
    POSITIVE membership check on the returned tag list. Three-way branch:
    Ollama unreachable → `pytest.skip` (never fail); reachable but tag absent →
    `pytest.skip` with a diagnostic naming the missing tag; the OLD unserved tag
    resolving as the default → FAIL. Also assert the resolved default is not the old
    `mitkox/...RL-Q4_K_M` tag. Env-gated; the positive `/api/tags` check means it
    cannot pass trivially when the endpoint is down. (AC7)
- This is a test-only guard: its "GREEN" is the Step-2 default flip (against the old
  default this assertion would fail / the old tag would be the resolved value). No
  new production code. Add after Step 2 so the served default already holds.

### Step 6 — Doc consistency (GREEN, doc-only) `[doc]`
- No test; verified by inspection (blast-radius convention — every doc consumer of
  the flipped defaults made consistent in this change):
  - `harpyja/config/settings.py` `scout_model` comment (near :73-77) — name the
    served Q8 default.
  - `README` model guidance — name the served Q8 Scout default; note the Deep
    default is provisional / "for now".
  - `_settings_from_args` docstring (`swebench_eval.py:796`) — currently states the
    `lm_model` default is `"local"` (factually wrong after Step 2); rewrite to the
    Qwen served default and describe the `--deep-model` canonical / `--lm-model`
    deprecated-alias reconciliation.
  - Record in changelog/history as the B1 fix from spec 0015. (AC9)

### Step 7 — Refactor (optional)
- If the deep-vs-lm reconciliation in `_settings_from_args` reads awkwardly, extract
  a small `_resolve_deep_model(args) -> str | None` helper (canonical `or` alias) so
  the precedence rule lives in one named place the D1 tests already cover. All tests
  still pass. Skip if the two-line `or` is clearer inline.

## Delegation

- Steps 1-2 (config defaults + drift guard) → config-focused implementer: isolated
  to `harpyja/config/{settings,test_settings}.py`, pure value flips + introspection
  test.
- Steps 3-4 (CLI plumbing + D1 reconciliation) → eval-harness implementer: contained
  to `harpyja/eval/swebench_eval.py` argparse/`_settings_from_args` seams; the
  both-orders D1 subtlety is the one place to get right.
- Step 5 (live smoke) → integration/ops-aware implementer: `/api/tags` three-way
  skip-not-fail branch mirrors existing `_socket_reachable` gating.

## Risk

- D1 both-orders reconciliation done via argparse shared-dest positional last-wins
  instead of distinct dests → the alias could win when listed last. Mitigation:
  distinct dests (`deep_model` vs `lm_model`) reconciled in `_settings_from_args`;
  `test_settings_from_args_deep_model_wins_over_lm_model_both_orders` asserts BOTH
  orders.
- AC6 drift guard written as a source grep instead of field-default introspection →
  brittle false positives on comments/fixtures. Mitigation: assert over
  `dataclasses.fields(Settings)` / `Settings()` values only.
- D2 blast radius: the global `lm_model` flip changes every bare `Settings()` caller
  (incl. MCP `mode=auto` Deep tier), and a llama.cpp operator relying on `"local"`
  regresses. Mitigation (accepted per D2): unchanged override precedence
  (toml/env/`--deep-model`) is the llama.cpp escape hatch; no test asserts a
  universal served guarantee (AC7 is instance-relative, skip-not-fail).
- AC7 passing trivially with the endpoint down → false green. Mitigation: POSITIVE
  `/api/tags` membership; endpoint-down is an explicit skip, missing-tag a
  diagnostic skip, old-tag-as-default a hard fail.
- Regressing existing precedence / alias tests. Mitigation: Steps flip VALUES only
  and ADD a distinct dest; `test_settings_from_args_applies_model_overrides` and the
  scout/lm precedence tests are re-run unchanged.
