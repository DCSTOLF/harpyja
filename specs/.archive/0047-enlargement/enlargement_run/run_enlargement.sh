#!/usr/bin/env bash
# Spec 0047 — enlargement: the ONE command the operator runs.
#
# Orchestrates the whole audited chain end-to-end on the dev host:
#   convert (HF SWE-bench_Verified) → blind author (Claude) / verify (Codex)
#   → tag (reachability mechanical + concept-vs-patch model hand-label)
#   → assemble enlarged fixtures → power re-check → 20-case audit sample.
#
# RESUMABLE: the driver is ledger-backed. If it stops (interruption, a StopAndWarn
# drift-guard, a flaky model call), just RUN THIS SAME COMMAND AGAIN — it skips every
# completed phase and every already-authored/tagged case and continues. Nothing is
# redone, nothing is partially committed.
#
# It runs DETACHED (nohup) so it survives your terminal closing (~130 cases × 2 model
# calls is long). Progress streams to the log file printed below; tail it to watch.
#
# The author and verifier MUST be different backends (blindness); the driver enforces it
# and defaults the verifier to the complement of the author.
#   --author {claude,codex}    (default claude)
#   --verifier {claude,codex}  (default: the other backend)
#   --claude-model <tag>       (optional Claude model tag)
#
# Prereqs on the dev host:
#   - `uv` env with `datasets` installed (uv add datasets) + network to HuggingFace
#   - BOTH the `claude` and `codex` CLIs installed + authenticated (the two arms).
#     Sanity-check them first (fast, no convert):  ./run_enlargement.sh --check-arms
#
# Usage:
#   ./run_enlargement.sh                          # author=claude, verifier=codex
#   ./run_enlargement.sh --author codex           # author=codex, verifier=claude
#   ./run_enlargement.sh --check-arms             # preflight both CLIs and exit
#   # then audit: cat harpyja/eval/fixtures/audit_sample.json  (20 cases)

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/../../.." && pwd)"
LOG="$HERE/run_enlargement.$(date +%Y%m%d_%H%M%S).log"

ARGS=("$@")
cd "$REPO_ROOT"

# --check-arms runs in the FOREGROUND (fast; you want to see the result now).
if printf '%s\n' "${ARGS[@]:-}" | grep -q -- '--check-arms'; then
  exec uv run python "$HERE/run_enlargement.py" "${ARGS[@]}"
fi

echo "[run_enlargement] repo=$REPO_ROOT"
echo "[run_enlargement] ledger=$HERE/ledger.json  (delete it to start over; keep it to resume)"
echo "[run_enlargement] detaching; log → $LOG"
echo "[run_enlargement] monitor:  tail -f '$LOG'"
echo "[run_enlargement] resume after any stop:  ./run_enlargement.sh ${ARGS[*]:-}"
echo "[run_enlargement] (sanity-check the CLIs first with: ./run_enlargement.sh --check-arms)"

# Detach: survives the terminal; re-run this script to resume from the ledger.
nohup uv run python "$HERE/run_enlargement.py" \
  --fixtures harpyja/eval/fixtures \
  --out-dir  harpyja/eval/fixtures \
  --work-dir eval_work \
  "${ARGS[@]}" \
  > "$LOG" 2>&1 &
PID=$!
disown "$PID" 2>/dev/null || true
echo "[run_enlargement] started pid=$PID"
echo "[run_enlargement] when it finishes: audit harpyja/eval/fixtures/audit_sample.json (20 cases),"
echo "[run_enlargement] then review specs/0047-enlargement/power_recheck.json + findings.md"
