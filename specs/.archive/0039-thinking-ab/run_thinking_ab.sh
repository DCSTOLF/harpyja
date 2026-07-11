#!/bin/sh
# Spec 0039 — thinking A/B operator driver (2026-07-10). Re-runnable, RESUMABLE.
# Stack: local Ollama, the PRE-REGISTERED qwen3:14b (frozen in
# PREREGISTERED_AB_CONFIG_0039 — never substitute a model under the hash).
#
# GATE FIRST (AC5): the upper-bound feasibility pre-check runs on committed
# 0036 evidence BEFORE any preflight or arm. On UNDER_POWERED_STOP the typed
# stop is the run's deliverable (exit 2, distinct from infra STOPs) — the live
# paired run is N/A-on-branch and ~4h of wall-clock is NOT spent.
#
# On PROCEED: STOP-AND-WARN preflight (served tag + two-call seed probe), then
# the resumable paired run (19 cases x 2 arms x K=2, per-cell ledger under
# eval_work/thinking_ab_0039/) via run_ab_paired, strict skip→hard-fail.
set -e
cd "$(dirname "$0")/../.."
BASE="http://localhost:11434"

echo "== AC5 gate: upper-bound feasibility pre-check (committed 0036 evidence) =="
GATE=$(uv run python -c "
import dataclasses, json
from harpyja.eval.think_ab import PREREGISTERED_AB_CONFIG_0039
from harpyja.eval.think_ab_precheck import run_precheck
outcome = run_precheck(PREREGISTERED_AB_CONFIG_0039)
print(json.dumps(dataclasses.asdict(outcome)))
")
echo "$GATE" | uv run python -m json.tool
OUTCOME=$(echo "$GATE" | uv run python -c "import json,sys; print(json.load(sys.stdin)['outcome'])")

if [ "$OUTCOME" = "under-powered-stop" ]; then
  echo "TYPED STOP: the pre-check fired UNDER_POWERED_STOP — the projected conceptual" >&2
  echo "upper bound cannot reach the frozen floor. The stop IS the deliverable;" >&2
  echo "next step: the 0036 pool-enlargement audited convert step. No arm fired." >&2
  exit 2
fi

MODEL=$(uv run python -c "from harpyja.eval.think_ab import PREREGISTERED_AB_CONFIG_0039 as c; print(c.lm_model)")
echo "== preflight: checking $BASE for pre-registered tag $MODEL =="
if ! curl -sf --max-time 10 "$BASE/api/tags" | grep -q "\"$MODEL\""; then
  echo "STOP: $MODEL not served at $BASE — start Ollama / pull the tag, then re-run." >&2
  echo "Do NOT substitute a model: the tag is pinned in the frozen config hash." >&2
  exit 1
fi

echo "== paired run (resumable; re-invoke until 'completed') =="
export HARPYJA_REQUIRE_LIVE_STACK=1
uv run python -c "
import json
from pathlib import Path
from harpyja.eval.think_ab import PREREGISTERED_AB_CONFIG_0039
from harpyja.eval.think_ab_run import run_ab_paired
root = Path('eval_work/thinking_ab_0039')
result = run_ab_paired(
    PREREGISTERED_AB_CONFIG_0039,
    out_dir=root / 'artifacts',
    ledger_path=root / 'ab_ledger.json',
    live=True,
)
print(json.dumps(result, indent=2, sort_keys=True))
(root / 'ab_result.json').write_text(json.dumps(result, indent=2, sort_keys=True))
"
echo "== done: result under eval_work/thinking_ab_0039/ab_result.json =="
