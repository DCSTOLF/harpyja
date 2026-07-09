# Domain requirement archive

Verbatim superseded requirement text demoted from a domain file by spec consolidation. Append-only.

## config | spec 0025 | MODIFY
- `lm_model` (Deep's Tier-2 explorer model) defaults to the served `hf.co/Qwen/Qwen3-8B-GGUF:latest` (provisional, "for now"), flipped from the llama.cpp placeholder `"local"`; this is a global `Settings` default so it affects every bare `Settings()` caller (the eval `run`/`sweep` drivers AND the MCP server's `mode=auto` Deep tier), and a llama.cpp operator (for whom the Ollama-style tag will not resolve) must set `lm_model` explicitly via toml/env/`--deep-model`. (spec 0016)

