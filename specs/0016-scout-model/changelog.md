# Spec 0016 — scout_model — changelog

Fixes **B1** from spec 0015 (`live-run-findings.md` D1): the out-of-box eval could not
reach a served model.

## What shipped

- **Served scout default** — `Settings.scout_model` (`config/settings.py`) flipped from
  the **unserved** `hf.co/mitkox/FastContext-1.0-4B-RL-Q4_K_M-GGUF:latest` (HTTP 404 on
  every Scout call) to the served `hf.co/dstolf/FastContext-1.0-4B-RL-Q8_0-GGUF:latest`.
  Because `verify_method="scout_model"`, this also changes the model the Verification
  Gate scores with — *broken→served plumbing*, distinct from the B2 gate-logic problem.
- **Served Deep default** — `Settings.lm_model` flipped from the llama.cpp placeholder
  `"local"` to `hf.co/Qwen/Qwen3-8B-GGUF:latest` (provisional, "for now"). This is a
  **global** `Settings` default (D2): affects every bare `Settings()` caller including
  the MCP server's `mode=auto` Deep tier. A llama.cpp operator sets `lm_model`
  explicitly (toml/env/`--deep-model`).
- **CLI overrides** — `run`/`sweep` gain `--scout-model` and the canonical
  `--deep-model` (`swebench_eval.py::_add_model_flags`); `--lm-model` retained as a
  deprecated alias. Distinct argparse dests reconciled in `_settings_from_args` so
  `--deep-model` wins regardless of CLI order (D1), never mutating the frozen base.
- **Docs** — `settings.py` comments + module-docstring toml example, the
  `_settings_from_args` docstring (no longer claims the Deep default is `"local"`), and
  the README model-guidance callout all name the served defaults + the override flags.

## Tests

- `config/test_settings.py`: `_FC_GGUF`→Q8; `test_settings_lm_model_default`;
  `test_settings_defaults_drop_unserved_tags` (field-default introspection, AC6).
- `eval/test_swebench_eval.py`: 9 new tests — run/sweep accept both flags, scout
  override, deep→lm mapping + alias, `--deep-model` wins **both CLI orders** (D1),
  scout+deep frozen-replace precedence (AC5), `--help` lists flags + deprecated alias.
- `eval/test_swebench_integration.py`:
  `test_scout_model_default_present_in_ollama_served_set` — positive `/api/tags`
  membership, three-way skip-not-fail (AC7). Validated live: the Q8 default IS served.

## Out of scope (unchanged)

B2 (gate-as-judge false-escalation) and B3 (gateway `urlopen` no timeout) remain
separate specs; re-attempting the OQ2 measurement is a fresh spec after B1/B2/B3.
