---
spec: "0016"
---

# Tasks

- [x] T1 — [unit][RED] Pin flipped config defaults: update `_FC_GGUF` (AC1), add `test_settings_lm_model_default` (AC2), add `test_settings_defaults_drop_unserved_tags` introspection guard (AC6) in `harpyja/config/test_settings.py`
- [x] T2 — [unit][GREEN] Flip `Settings.scout_model` (settings.py:77 → Q8, AC1) and `Settings.lm_model` (settings.py:43 → Qwen, AC2/D2)
- [x] T3 — [unit][RED] Add CLI + reconciliation tests in `harpyja/eval/test_swebench_eval.py`: run/sweep accept `--scout-model`/`--deep-model` (AC3/AC4), scout override (AC3), deep-model maps to lm_model + alias (AC4), deep-model wins both orders (AC4/D1), scout+deep precedence frozen-replace (AC5), run/sweep --help list flags with deprecated alias (AC8)
- [x] T4 — [unit][GREEN] Implement `_add_model_flags` (`--scout-model`, canonical `--deep-model`, deprecated `--lm-model`, distinct dests) and `_settings_from_args` (thread `scout_model`, reconcile `deep_model or lm_model`) in `harpyja/eval/swebench_eval.py`
- [x] T5 — [integration][skip-not-fail] Add `test_scout_model_default_present_in_ollama_served_set` `/api/tags` positive-membership three-way guard in `harpyja/eval/test_swebench_integration.py` (AC7) — validated live: Q8 default IS served
- [x] T6 — [doc][GREEN] Make all doc consumers consistent: settings.py scout+lm comments + module-docstring toml example, README (Q8 default + provisional Deep), `_settings_from_args` docstring (swebench_eval.py:796), changelog B1-fix note (AC9)
- [x] T7 — [refactor][optional] SKIPPED — the D1 reconciliation is a clean two-line `deep_model or lm_model`; a `_resolve_deep_model` helper would add indirection for no behavioral gain (locked by the both-orders test)
