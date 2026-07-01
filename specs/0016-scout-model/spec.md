---
id: "0016"
title: "scout_model"
status: closed
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

**INVARIANT (plumbing, not capability):** no change to tier *logic*, the classifier,
the citation format, or the gate's **algorithm**. This spec changes two **defaults**
and adds two **CLI override flags** so the eval reaches a served model. It does not
claim any model is *good* — only that the default is *served* (see the "served"
clarification below), and that any served model can be named from the CLI without
editing source.

**Gate-coupling caveat (stated, not hidden).** `scout_model` does **double duty**: it
is Scout-tier's retrieval model AND — because `verify_method="scout_model"` is the
only shipped gate backend (`settings.py:83-94`, `_VERIFY_METHODS`) — the model the
Verification Gate calls to score citations. Flipping `scout_model`'s value therefore
changes the **model the gate scores with**, from an unserved (broken) tag to a served
one. This is defensible as *plumbing* (broken→served), and it is deliberately
**distinct** from B2, the out-of-scope gate-quality problem, which changes the gate's
*judging logic*. This spec changes only *which served model the gate calls*; it does
not touch how the gate judges. The next OQ2 run must attribute any gate-behavior delta
to this served-model change, not conflate it with a (future) B2 fix.

**"Served" is instance-relative, not universal.** A model tag is "served" only
relative to a particular local Ollama instance. The claim here is narrow: the new
defaults name tags in the **documented required local Ollama set** (repo memory /
README), replacing a tag that is served **nowhere** in that set. The skip-not-fail
smoke (AC7) proves the default avoids the known-bad tag and matches the served set on
the eval host — not a universal out-of-box guarantee.

**Air-gap note.** All `hf.co/...` strings here are **local Ollama model tags**, not a
license to fetch from Hugging Face at Harpyja runtime. The change touches model
*tags*, never endpoints; the runtime air-gap (Model Gateway → localhost only) is
untouched.

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
  This is an intentional **global** default flip (see Decision D2): it is a `Settings`
  default, so it affects **every bare `Settings()` caller**, including the MCP server's
  `mode=auto` Deep tier — not only the eval CLI. Its blast radius and the llama.cpp
  trade-off are enumerated in D2; per-request/toml/env/CLI override remains the escape
  hatch for a llama.cpp operator.
- **Add `--scout-model`** to the shared `_add_model_flags` group (so both `run` and
  `sweep` gain it) and thread it through `_settings_from_args` as a `scout_model`
  override.
- **Add `--deep-model`** as the **canonical** name for the Deep model override,
  mapping to the `lm_model` setting; **`--lm-model` is retained as a deprecated
  back-compat alias** (see Decision D1 for the both-supplied precedence).

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
   setting; `--lm-model` is retained as a deprecated alias to the same setting. Per
   Decision D1, `--deep-model` wins **regardless of CLI order** when both are supplied
   (reconciled in `_settings_from_args`, not via argparse positional last-wins). A test
   asserts: each flag alone resolves to `lm_model`; both-supplied (in *both* orders)
   resolves to the `--deep-model` value; neither → the new default from AC2.
5. **[unit]** Override precedence for BOTH new flags: an explicit
   `--scout-model`/`--deep-model` beats the new default; no flag → the new default;
   the base `Settings()` is not mutated (frozen-replace contract). One `[unit]` test
   pins this for each flag.
6. **[unit]** Drift guard, by **field-default introspection, not text grep**: assert
   `Settings()` (or `dataclasses.fields(Settings)` defaults) no longer carries the old
   unserved scout tag (`mitkox/…RL-Q4_K_M`) nor `"local"` for `lm_model`. Inspecting
   resolved field values (never a source scan) is what keeps docstrings, comments,
   tests, and historical fixtures (e.g. `scout/fixtures/fc_citation_false_raw_samples.txt`)
   from tripping a false positive.
7. **[integration]** Skip-not-fail live smoke: `swebench_eval run`/`sweep` invoked with
   **no** model flags reaches a Scout model that is **present in the local Ollama served
   set** — a *positive* membership check against Ollama's `/api/tags` for the resolved
   `scout_model`, so the test cannot pass trivially when the endpoint is down. It
   distinguishes the three cases — **missing Ollama** (skip), **missing tag** (skip
   with a diagnostic), and **the old unserved tag** (would fail) — and asserts the
   default is not the old tag. Env-gated; skips (never fails) when Ollama is absent.
8. **[integration]** `run --help` and `sweep --help` each list `--scout-model` and
   `--deep-model`, with `--lm-model` shown as the deprecated alias. A `[unit]`-level
   parser-introspection test suffices (no live process).
9. **[doc]** Every doc consumer of the flipped defaults is made consistent in this
   change (blast-radius convention): the `settings.py` `scout_model` comment, the
   README model guidance (name the served Q8 default; note the Deep default is
   provisional / "for now"), AND the `_settings_from_args` docstring at
   `swebench_eval.py:796` (which currently asserts the `lm_model` default is `"local"`
   — factually wrong after the flip). Recorded in changelog/history as the B1 fix from
   spec 0015.

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

## Decisions (resolved in review)

- **D1 — `--deep-model` canonical, `--lm-model` deprecated alias; `--deep-model` wins
  regardless of order.** Adopt `--deep-model` as the canonical Deep-model flag and keep
  `--lm-model` as a **deprecated back-compat alias** (no break). When both are supplied,
  `--deep-model` wins **irrespective of command-line order** — so the two flags get
  **distinct argparse dests** reconciled in `_settings_from_args` (canonical beats
  alias), NOT a shared dest with argparse positional last-wins. AC4 pins both orders.
- **D2 — the Deep `lm_model` flip is intentional and global; blast radius accepted.**
  `lm_model` is a `Settings` default, so flipping it changes **every bare `Settings()`
  caller**: the eval `run`/`sweep` drivers AND the MCP server's `mode=auto` Deep tier.
  This global flip is intended ("for now"). **Trade-off accepted:** against an Ollama
  backend the old `"local"` placeholder is unserved anyway, so the global default is
  already broken there; against a **llama.cpp `llama-server`** endpoint, `"local"` is a
  benign don't-care and the Ollama-style Qwen tag will **not** resolve — so a llama.cpp
  operator relying on the default would regress. The mitigation is the unchanged
  override precedence (toml/env/`--deep-model`): a llama.cpp operator sets `lm_model`
  explicitly. This trade-off is accepted rather than scoped-to-eval because the primary
  supported backend for this eval arc is Ollama, and the default must be *served there*.

## Open questions

_none — D1 and D2 resolved above during review._
