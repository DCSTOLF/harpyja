#!/bin/sh
# Spec 0034 evidence probes (2026-07-09) — re-runnable. Stack: local Ollama, qwen3:14b.
# A: /v1 max_tokens=20 enforcement + reasoning-first consumption
# B: native options.num_predict=20 equivalence
# C: /v1 WITHOUT think — default-on reasoning (the hidden variable)
set -e
OUT="$(dirname "$0")"
curl -s --max-time 60 http://localhost:11434/v1/chat/completions -d '{
  "model": "qwen3:14b",
  "messages": [{"role": "user", "content": "Count from 1 to 100 slowly, one number per line."}],
  "max_tokens": 20, "stream": false
}' > "$OUT/probe_a_v1_max_tokens_20.json"
curl -s --max-time 60 http://localhost:11434/api/chat -d '{
  "model": "qwen3:14b",
  "messages": [{"role": "user", "content": "Count from 1 to 100 slowly, one number per line."}],
  "options": {"num_predict": 20}, "stream": false
}' > "$OUT/probe_b_native_num_predict_20.json"
curl -s --max-time 120 http://localhost:11434/v1/chat/completions -d '{
  "model": "qwen3:14b",
  "messages": [{"role": "user", "content": "Find where the ls function is defined. Use the grep tool."}],
  "tools": [{"type": "function", "function": {"name": "grep", "description": "search files for a pattern", "parameters": {"type": "object", "properties": {"pattern": {"type": "string"}, "scope": {"type": "string"}}, "required": ["pattern"]}}}],
  "stream": false
}' > "$OUT/probe_c_v1_default_no_think.json"
echo "probes written to $OUT"
