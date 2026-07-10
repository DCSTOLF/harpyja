#!/bin/sh
# Spec 0038 evidence probe (2026-07-10) — re-runnable. Stack: local Ollama, qwen3:14b.
# Question: which transport path genuinely HONORS the think toggle at generation level?
# Candidate: native /api/chat (0037's proven control). Two-factor discrimination per arm:
#   - tiny-cap technique: options.num_predict=60 — a thinking model exhausts the cap
#     reasoning-first (empty content, done_reason=length); a genuinely-off model produces
#     content / done_reason!=length within the cap;
#   - eval_count (the native completion_tokens source under test) comparison across arms;
#   - <think>-in-content leak scan on the off arm (adjudicated from the raw outputs).
# Arms 1-3 OBSERVE all three think states natively (default/on never inferred from the
# 0037 false-control arm). Arm 4 scopes the MIGRATION COST: native tool-calling shape
# (tool_call_id present?), usage field names, reasoning field name. Arms 5-6 re-check the
# /v1 passthrough (OQ1): 0037's top-level-think finding re-confirmed on this server
# version, plus the served version itself.
# STOP-AND-WARN: any curl failure on a native arm aborts loudly — never a silent skip.
# (/v1 VARIANT arms tolerate non-2xx: a rejected variant is evidence, not a stack failure.)
set -e
OUT="$(dirname "$0")"
BASE="http://localhost:11434"
MODEL="qwen3:14b"

echo "preflight: checking $BASE for $MODEL ..."
if ! curl -sf --max-time 10 "$BASE/api/tags" | grep -q "\"$MODEL\""; then
  echo "STOP: $MODEL not served at $BASE — start Ollama / pull the model, then re-run." >&2
  exit 1
fi
curl -sf --max-time 10 "$BASE/api/version" > "$OUT/probe_server_version.json"

PROMPT="What is 17 * 23? Answer with just the number."

echo "arm 1/6: native /api/chat think:true (tiny cap) ..."
curl -sf --max-time 180 "$BASE/api/chat" -d '{
  "model": "'"$MODEL"'",
  "messages": [{"role": "user", "content": "'"$PROMPT"'"}],
  "options": {"num_predict": 60}, "stream": false, "think": true
}' > "$OUT/probe_arm_native_think_true.json"

echo "arm 2/6: native /api/chat think:false (tiny cap) ..."
curl -sf --max-time 180 "$BASE/api/chat" -d '{
  "model": "'"$MODEL"'",
  "messages": [{"role": "user", "content": "'"$PROMPT"'"}],
  "options": {"num_predict": 60}, "stream": false, "think": false
}' > "$OUT/probe_arm_native_think_false.json"

echo "arm 3/6: native /api/chat think omitted (tiny cap) ..."
curl -sf --max-time 180 "$BASE/api/chat" -d '{
  "model": "'"$MODEL"'",
  "messages": [{"role": "user", "content": "'"$PROMPT"'"}],
  "options": {"num_predict": 60}, "stream": false
}' > "$OUT/probe_arm_native_omitted.json"

echo "arm 4/6: native /api/chat TOOL-CALLING shape (migration-cost scoping) ..."
curl -sf --max-time 300 "$BASE/api/chat" -d '{
  "model": "'"$MODEL"'",
  "messages": [{"role": "user", "content": "Use the grep tool to find the string TODO in the repository. Call the tool."}],
  "tools": [{"type": "function", "function": {
    "name": "grep",
    "description": "Search the repository for a pattern.",
    "parameters": {"type": "object", "properties": {
      "pattern": {"type": "string", "description": "the pattern to search for"}
    }, "required": ["pattern"]}
  }}],
  "options": {"num_predict": 1024}, "stream": false
}' > "$OUT/probe_arm_native_tools.json"

echo "arm 5/6 (variant re-check, tolerant): /v1 top-level think:false (tiny cap) ..."
HTTP=$(curl -s --max-time 180 -w "%{http_code}" -o "$OUT/probe_arm_v1_think_false.json" \
  "$BASE/v1/chat/completions" -d '{
  "model": "'"$MODEL"'",
  "messages": [{"role": "user", "content": "'"$PROMPT"'"}],
  "max_tokens": 60, "stream": false, "think": false
}')
echo "  /v1 think:false -> HTTP $HTTP"

echo "arm 6/6 (variant re-check, tolerant): /v1 reasoning_effort:none (tiny cap) ..."
HTTP=$(curl -s --max-time 180 -w "%{http_code}" -o "$OUT/probe_arm_v1_reasoning_effort.json" \
  "$BASE/v1/chat/completions" -d '{
  "model": "'"$MODEL"'",
  "messages": [{"role": "user", "content": "'"$PROMPT"'"}],
  "max_tokens": 60, "stream": false, "reasoning_effort": "none"
}')
echo "  /v1 reasoning_effort:none -> HTTP $HTTP"

echo "arm 7/8 (variant two-factor ON arm): /v1 reasoning_effort:high (tiny cap) ..."
HTTP=$(curl -s --max-time 180 -w "%{http_code}" -o "$OUT/probe_arm_v1_reasoning_effort_high.json" \
  "$BASE/v1/chat/completions" -d '{
  "model": "'"$MODEL"'",
  "messages": [{"role": "user", "content": "'"$PROMPT"'"}],
  "max_tokens": 60, "stream": false, "reasoning_effort": "high"
}')
echo "  /v1 reasoning_effort:high -> HTTP $HTTP"

echo "arm 8/8 (variant tool-calling): /v1 tools + reasoning_effort:none ..."
HTTP=$(curl -s --max-time 300 -w "%{http_code}" -o "$OUT/probe_arm_v1_tools_effort_none.json" \
  "$BASE/v1/chat/completions" -d '{
  "model": "'"$MODEL"'",
  "messages": [{"role": "user", "content": "Use the grep tool to find the string TODO in the repository. Call the tool."}],
  "tools": [{"type": "function", "function": {
    "name": "grep",
    "description": "Search the repository for a pattern.",
    "parameters": {"type": "object", "properties": {
      "pattern": {"type": "string", "description": "the pattern to search for"}
    }, "required": ["pattern"]}
  }}],
  "max_tokens": 1024, "stream": false, "reasoning_effort": "none"
}')
echo "  /v1 tools + reasoning_effort:none -> HTTP $HTTP"

echo "arm 9/9 (variant two-factor DEFAULT arm): /v1 reasoning_effort omitted (tiny cap) ..."
HTTP=$(curl -s --max-time 180 -w "%{http_code}" -o "$OUT/probe_arm_v1_omitted.json" \
  "$BASE/v1/chat/completions" -d '{
  "model": "'"$MODEL"'",
  "messages": [{"role": "user", "content": "'"$PROMPT"'"}],
  "max_tokens": 60, "stream": false
}')
echo "  /v1 omitted -> HTTP $HTTP"

echo "probe arms written to $OUT — adjudicate into probe_result.json (typed outcome, schema 0038/1)"
