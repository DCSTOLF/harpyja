# Config domain

Consolidated, current requirements for layered settings and config discovery.
Each line carries its originating spec(s) as provenance.

- Settings resolve with precedence profile defaults < `harpyja.toml` < `HARPYJA_*` env < per-request override (lowest to highest). (spec 0001)
- `harpyja.toml` discovery order is explicit `--config <path>` > cwd `harpyja.toml` > repo-root `harpyja.toml`. (spec 0001)
- Scout budgets are `Settings`-configurable: `scout_seed_top_n` (default 5), `scout_max_citations` (default 20, clamped to `min(scout_max_citations, max_results)`), `scout_max_span_lines` (default 200). (spec 0005)
- Deep budgets are `Settings`-configurable: `deep_seed_top_n` (5), `deep_max_citations` (20, clamped to `min(deep_max_citations, max_results)`), `deep_max_span_lines` (200), `deep_max_depth` (3), `deep_max_subqueries` (8), `deep_max_tool_calls` (200), `deep_token_ceiling` (32000), `deep_wall_clock_ms` (60000). (spec 0006)
- `scout_model` selects the Scout/FastContext fine-tune (default the Ollama GGUF), distinct from Deep's `lm_model`, with standard precedence (defaults < `harpyja.toml` < `HARPYJA_*` < per-request). (spec 0007)
- Verification Gate settings (appended last with defaults, standard precedence): `verify_method` (default `"scout_model"`, the only supported value — an unsupported value is rejected loudly at `Settings` load with a typed error, never a silent fall-through), `verify_threshold` (provisional `0.6`), `verify_top_n` (provisional `3`). (spec 0008)
