#!/bin/sh
# Spec 0037 evidence probe (2026-07-10) — re-runnable. Stack: local Ollama, qwen3:14b, /v1 path.
# Question: does the native `think` request param actually TOGGLE generation-level thinking
# on this endpoint? Three-factor discrimination (per the spec's effectiveness invariant):
#   - tiny-cap technique (0034 probe-A): max_tokens=60 — a thinking model exhausts the cap
#     reasoning-first (empty content, finish_reason=length); a genuinely-off model produces
#     content / finish_reason!=length within the cap;
#   - completion_tokens comparison across arms;
#   - <think>-in-content leak scan on the off arm (adjudicated from the raw outputs).
# Arms: think:true / think:false / omitted (+ a supplementary chat_template_kwargs arm for
# adjudication evidence if the native param proves non-effective).
# STOP-AND-WARN: any curl failure or missing model aborts loudly — never a silent skip.
set -e
OUT="$(dirname "$0")"
BASE="http://localhost:11434"
MODEL="qwen3:14b"

echo "preflight: checking $BASE for $MODEL ..."
if ! curl -sf --max-time 10 "$BASE/api/tags" | grep -q "\"$MODEL\""; then
  echo "STOP: $MODEL not served at $BASE — start Ollama / pull the model, then re-run." >&2
  exit 1
fi

PROMPT="What is 17 * 23? Answer with just the number."

echo "arm 1/4: think:true (tiny cap) ..."
curl -sf --max-time 120 "$BASE/v1/chat/completions" -d '{
  "model": "'"$MODEL"'",
  "messages": [{"role": "user", "content": "'"$PROMPT"'"}],
  "max_tokens": 60, "stream": false, "think": true
}' > "$OUT/probe_arm_think_true.json"

echo "arm 2/4: think:false (tiny cap) ..."
curl -sf --max-time 120 "$BASE/v1/chat/completions" -d '{
  "model": "'"$MODEL"'",
  "messages": [{"role": "user", "content": "'"$PROMPT"'"}],
  "max_tokens": 60, "stream": false, "think": false
}' > "$OUT/probe_arm_think_false.json"

echo "arm 3/4: think omitted (tiny cap) ..."
curl -sf --max-time 120 "$BASE/v1/chat/completions" -d '{
  "model": "'"$MODEL"'",
  "messages": [{"role": "user", "content": "'"$PROMPT"'"}],
  "max_tokens": 60, "stream": false
}' > "$OUT/probe_arm_omitted.json"

echo "arm 4/4 (supplementary): chat_template_kwargs enable_thinking:false (tiny cap) ..."
curl -sf --max-time 120 "$BASE/v1/chat/completions" -d '{
  "model": "'"$MODEL"'",
  "messages": [{"role": "user", "content": "'"$PROMPT"'"}],
  "max_tokens": 60, "stream": false,
  "chat_template_kwargs": {"enable_thinking": false}
}' > "$OUT/probe_arm_chat_template_disabled.json"

echo "probe arms written to $OUT — adjudicate into probe_result.json (typed outcome)"
