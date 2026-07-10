#!/bin/sh
# Spec 0038 AC3 closure driver (2026-07-10) — re-runnable. Stack: local Ollama, qwen3:14b.
# Runs the live per-mode two-factor effectiveness test on the RECONCILED path
# (test_live_reconciled_think_knob_effectiveness) in STRICT posture: for this
# closure run a skip is a hard STOP, not a pass — the deliverable is three
# durable, verifier-clean per-mode artifacts under eval_work/live_artifacts/
# (reconciled_think_on / _off / _default), and they cannot exist if the test
# skipped. STOP-AND-WARN: preflight failures abort loudly, never silently.
set -e
cd "$(dirname "$0")/../.."
BASE="http://localhost:11434"
MODEL="qwen3:14b"

echo "preflight: checking $BASE for $MODEL ..."
if ! curl -sf --max-time 10 "$BASE/api/tags" | grep -q "\"$MODEL\""; then
  echo "STOP: $MODEL not served at $BASE — start Ollama / pull the model, then re-run." >&2
  exit 1
fi

OUT=$(mktemp)
set +e
uv run pytest \
  "harpyja/eval/test_live_verifier_integration.py::test_live_reconciled_think_knob_effectiveness" \
  -m integration -rs -v 2>&1 | tee "$OUT"
STATUS=$?
set -e

if [ $STATUS -ne 0 ]; then
  echo "STOP: effectiveness test FAILED — the knob is not toggling generation on the wired path." >&2
  exit 1
fi
if grep -q "SKIPPED" "$OUT"; then
  echo "STOP: effectiveness test SKIPPED — strict closure run requires a live PASS (see reasons above)." >&2
  exit 1
fi
echo "AC3 closure PASS: per-mode artifacts under eval_work/live_artifacts/reconciled_think_{on,off,default}/"
