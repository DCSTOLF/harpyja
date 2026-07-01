---
id: "0016"
title: "scout_model"
status: draft
created: 2026-07-01
authors: [claude]
packages: [harpyja/config, harpyja/eval]
related-specs: ["0008", "0013", "0015"]
---

# Spec 0016 — scout_model

## Why

Spec 0015 (OQ2) could not run out of the box: the default `scout_model` names a
model that **is not served** by the local Ollama, so every Scout call 404s. This is
the B1 blocker recorded in `specs/0015-oq2/live-run-findings.md` (D1) — an
**infrastructure** failure masquerading as model-quality failure.

Two concrete facts, both source-verified:

1. **Wrong default (`harpyja/config/settings.py:77`).**
   `scout_model = "hf.co/mitkox/FastContext-1.0-4B-RL-Q4_K_M-GGUF:latest"` is not in
   the served set (served: `hf.co/dstolf/…Q8_0` RL/SFT, `hf.co/mitkox/…SFT` Q4/Q5 —
   *not* `mitkox RL-Q4`). A live call returns HTTP 404 → Scout `backend-error` → a
   fully-degraded run for a non-model reason. The README already flags recommended-Q4
   as non-functional; this is worse — it isn't even pulled.
2. **No CLI escape hatch.** The `run`/`sweep` parsers thread `--lm-model` (Deep),
   `--lm-api-base`, and `--deep-max-subqueries` via `_add_model_flags`
   (`harpyja/eval/swebench_eval.py:881`) and `_settings_from_args` (`:793`), but there
   is **no `--scout-model` flag**, so an operator cannot override the broken default
   from the CLI. The 0015 run had to work around this through a Python entrypoint.

This spec makes the out-of-the-box eval *reach a served model* — a prerequisite for
re-attempting OQ2 — by flipping both defaults to served tags and adding the missing
CLI overrides. It is a **serving/plumbing** fix, not a model-quality or gate change.

Ref: 0015 (B1 / live-run-findings D1), 0008 (`verify_method` / no-false-capability),
0013 (the `dstolf` FastContext fork the Q8 tag is built from).

## What

**INVARIANT (plumbing, not capability):** no change to tier logic, the gate, the
classifier, or the citation format. This spec changes two **defaults** and adds two
**CLI override flags** so the eval reaches a served model. It does not claim any
model is *good* — only that the default is *served*, and that any served model can be
named from the CLI without editing source.

**INVARIANT (precedence preserved):** the layered settings precedence
(defaults < `harpyja.toml` < `HARPYJA_*` env < per-request) is unchanged. A CLI flag
maps to a per-request-style override built via `dataclasses.replace` on a fresh
`Settings()` — never mutation of a shared base (mirrors the existing `lm_model`
override contract at `_settings_from_args`).

Scope:

- **Flip the scout default** (`settings.py::Settings.scout_model`) from the unserved
  `hf.co/mitkox/FastContext-1.0-4B-RL-Q4_K_M-GGUF:latest` to the served
  `hf.co/dstolf/FastContext-1.0-4B-RL-Q8_0-GGUF:latest`. Update the paired test
  constant (`test_settings.py::_FC_GGUF`); the `scout_model != lm_model` invariant
  still holds (Q8 Scout ≠ Qwen Deep).
- **Flip the Deep default** (`settings.py::Settings.lm_model`) from the llama.cpp
  placeholder `"local"` to the served `hf.co/Qwen/Qwen3-8B-GGUF:latest` ("for now" —
  a provisional served default, not a claim it is the right long-term Deep model).
- **Add `--scout-model`** to the shared `_add_model_flags` group (so both `run` and
  `sweep` gain it) and thread it through `_settings_from_args` as a `scout_model`
  override.
- **Add `--deep-model`** as the canonical name for the Deep model override, mapping to
  the same `lm_model` setting the existing `--lm-model` writes (reconciliation of the
  two names resolved in plan; back-compat for `--lm-model` preserved).

## Acceptance criteria

`[unit]` = fakes/no network; `[integration]` = operator-run / `@pytest.mark.integration`,
skip-not-fail; `[doc]` = documentation.

1. **[unit]** `Settings().scout_model == "hf.co/dstolf/FastContext-1.0-4B-RL-Q8_0-GGUF:latest"`.
   The paired constant `test_settings.py::_FC_GGUF` is updated to the new value and the
   default-assertion test passes against it. The existing `scout_model != lm_model`
   invariant test still holds.
2. **[unit]** `Settings().lm_model == "hf.co/Qwen/Qwen3-8B-GGUF:latest"` (flipped from
   `"local"`). The settings **precedence** tests (toml/env/per-request beat default;
   base not mutated) still pass unchanged — only the default value moved.
3. **[unit]** Both the `run` and the `sweep` parsers accept `--scout-model NAME`, and
   `_settings_from_args` maps it to a `scout_model` override built via `replace` on a
   fresh `Settings()` (never mutation). A test asserts:
   `_settings_from_args(ns(scout_model="x")).scout_model == "x"`, and that **omitting**
   the flag yields the new default from AC1.
4. **[unit]** Both `run` and `sweep` accept `--deep-model NAME` writing the `lm_model`
   setting; `--lm-model` is retained as a back-compat alias to the same destination.
   A test asserts both flags resolve to `lm_model`, and the precedence between them
   (when both/neither are supplied) is deterministic per the plan's decision.
5. **[unit]** Override precedence for BOTH new flags: an explicit
   `--scout-model`/`--deep-model` beats the new default; no flag → the new default;
   the base `Settings()` is not mutated (frozen-replace contract). One `[unit]` test
   pins this for each flag.
6. **[unit]** Drift guard: no live default in `harpyja/` still names the old unserved
   scout tag (`mitkox/…RL-Q4_K_M`) or the `"local"` `lm_model` placeholder as a
   `Settings` default. (Historical fixture data, e.g.
   `scout/fixtures/fc_citation_false_raw_samples.txt`, is captured sample text, not a
   default, and is explicitly excluded.)
7. **[integration]** Skip-not-fail live smoke: `swebench_eval run`/`sweep` invoked with
   **no** model flags reaches a **served** Scout model — the out-of-box call does not
   404 on Scout for an unserved-model reason. (Env-gated; skips when Ollama/served tags
   are absent — never fails the suite.)
8. **[doc]** The `settings.py` `scout_model` comment and the README model guidance name
   the served Q8 default (and note the Deep default is provisional / "for now"). The
   change is recorded in changelog/history as the B1 fix from spec 0015.

The load-bearing ACs are **1, 3, and 4**: AC1 makes the default *reach a served model*
(the actual B1 fix); AC3/AC4 give the operator a CLI escape hatch so a future
served-model change never again requires a source edit or a Python workaround.

## Out of scope

- **B2 — gate-as-judge false-escalation** (the FastContext finder reused as a relevance
  judge rejecting correct citations). Separate gate-quality spec.
- **B3 — model gateway `urlopen` has no HTTP timeout** (runs wedge indefinitely).
  Separate reliability spec.
- **Re-attempting the OQ2 measurement.** A fresh spec, after B1/B2/B3 are fixed.
- Validating the Q8 memory footprint / the 8 GB-Q4 hardware floor.
- Choosing the *permanent* Deep model — the Qwen3-8B default is provisional ("for now").
- Flipping any other `Settings` default (gate threshold, top_n, verify_method).

## Open questions

1. **(resolve-in-plan)** `--deep-model` vs the existing `--lm-model`: adopt
   `--deep-model` as canonical with `--lm-model` as a back-compat alias to the same
   `lm_model` dest, or rename outright? Default proposal: **alias** (no break). Fix the
   both-supplied precedence (argparse last-wins on a shared dest) explicitly so AC4 is
   deterministic.
2. **(resolve-in-plan)** Flipping `lm_model`'s default changes the **global** Deep
   default (it affects the MCP server's `mode=auto`, not only the eval CLI). Confirm
   this global flip is intended ("for now"), vs. scoping the Deep-served default to the
   eval driver only. Default proposal: **global flip** — the placeholder `"local"` is
   not served by Ollama either, so the global default is already broken against the
   documented Ollama backend.
