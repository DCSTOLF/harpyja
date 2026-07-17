#!/usr/bin/env bash
# Spec 0048 — bake-off: DETACHED live-run launcher (T22, OPERATOR step).
#
# The full grid is 3 models × 53 cases × ~200s ≈ 9h — it MUST outlive one shell
# and survive the harness's ~20-min background-task cap (repo memory:
# detach-long-live-runs). This wrapper launches the run under nohup + disown and
# tails the log; the run is resumable through the BakeoffLedger keyed to the
# frozen 0048 config hash, so a mid-run interruption resumes rather than restarts.
#
# Pre-run: evict any foreign resident from the exclusive endpoint (0041) and pin
# the three tags (qwen3:14b / qwen3:8b / qwen3.5:4b) with keep_alive per the dev
# Ollama posture. This script does NOT run in-session; an operator runs it.
set -euo pipefail

LOG="${BAKEOFF_LOG:-/tmp/bakeoff_0048.log}"
LEDGER="${BAKEOFF_LEDGER:-/tmp/bakeoff_0048_ledger.json}"

echo "spec 0048 bake-off — detached launch"
echo "  log:    $LOG"
echo "  ledger: $LEDGER (resumable, keyed to the frozen 0048 config hash)"

nohup uv run python -m harpyja.eval.bakeoff_cli \
  --ledger "$LEDGER" \
  >>"$LOG" 2>&1 &
disown
echo "  pid:    $!  (detached; tail -f $LOG to monitor)"
