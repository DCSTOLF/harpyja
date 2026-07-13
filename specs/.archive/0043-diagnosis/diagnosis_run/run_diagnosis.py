"""spec 0043 T17 — the committed diagnosis re-measurement driver (operator
tooling, AC5; the 0040/0041/0042 run_gate.py/run_pilot.py/run_adoption.py
shape).

Re-measures the COMMITTED 0042 pinned pilot cells under the T13 lever (the
submit-early prompt nudge — the ONLY deliberate SUT delta; params byte-frozen)
through ``run_gated_pool_pilot`` (0041 exclusive-endpoint gate: start +
per-block checks, no bypass), resumable via ``PoolPilotLedger`` at
``0041/pilot/2`` keyed by ``DIAGNOSIS_CONFIG_HASH_0043``. Model coverage is
CONSUMED from the frozen config: required (``qwen3:14b``) always; optional
(``qwen3:8b``, ``qwen3.5:4b``) only via ``--optional`` / ``--all-optional``.

The summary joins AFTER (this run) against BEFORE (the committed T9 covered
subset) with the IDENTICAL detector version, reports found-but-unsubmitted
per side, per-side detector-inconclusive counts, bidirectional net movement,
and the total pure AC6 verdict.

STOP-AND-WARN, never a silent skip. Exit codes:
  0 = all requested-coverage cells clean-complete; ledger + per-case
      trajectory-verified artifacts + machine-readable summary persisted here.
  2 = typed stop (exclusive-endpoint-contended / endpoint unreachable /
      unserved pinned model) — refusal is loud; contention proof is in the
      ledger; the only sanctioned unblock is changing the environment.
  3 = stopped with work remaining (budget stop or fresh typed degrades due a
      bounded re-run) — re-invoke to resume; clean cells never re-run.

Budget per invocation from DIAGNOSIS_BUDGET_S (default 480s — headroom under
a 600s invocation cap; for the full closure run use the detached nohup wrapper
loop, the 0042 T12 lesson: harness background tasks die at ~20 min).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from harpyja.eval.diagnosis_config import (  # noqa: E402
    DIAGNOSIS_CONFIG_HASH_0043,
    PREREGISTERED_DIAGNOSIS_CONFIG_0043,
    compute_sut_hash,
)
from harpyja.eval.diagnosis_run import (  # noqa: E402
    build_diagnosis_run_summary,
    run_diagnosis_cells,
)
from harpyja.eval.exclusivity_gate import ExclusiveEndpointContended  # noqa: E402
from harpyja.eval.pool_pilot import PoolRunError  # noqa: E402

CFG = PREREGISTERED_DIAGNOSIS_CONFIG_0043
HERE = Path(__file__).parent
LEDGER = HERE / "diagnosis_results.json"
ARTIFACT_DIR = HERE / "artifacts"
SUMMARY = HERE / "diagnosis_summary.json"
BUDGET_S = float(os.environ.get("DIAGNOSIS_BUDGET_S", "480"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Gated 0043 submission-gap re-measurement over the pinned 0042 "
            "pilot cells (STOP-AND-WARN; resumable; no bypass exists)"
        )
    )
    parser.add_argument(
        "--optional",
        action="append",
        default=[],
        choices=list(CFG.optional_models),
        metavar="TAG",
        help=(
            "include a frozen OPTIONAL model (recorded-if-run); repeatable: "
            f"{list(CFG.optional_models)}"
        ),
    )
    parser.add_argument(
        "--all-optional",
        action="store_true",
        help="include every frozen optional model (full three-model coverage)",
    )
    parser.add_argument(
        "--budget-s",
        type=float,
        default=BUDGET_S,
        help="wall-clock budget for this invocation (stop-and-resume, exit 3)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    include_optional = (
        tuple(CFG.optional_models)
        if args.all_optional
        else tuple(dict.fromkeys(args.optional))
    )
    # The SUT pin: the config froze the post-lever surface hash; a drifted
    # working tree at run time would make the AFTER cells unattributable.
    live_sut = compute_sut_hash()
    if live_sut != CFG.sut_hash:
        print(
            "STOP-AND-WARN: working-tree SUT hash "
            f"{live_sut[:12]}… != frozen {CFG.sut_hash[:12]}… — the AFTER "
            "cells would not run on the pinned SUT",
            file=sys.stderr,
        )
        return 2
    print(
        f"coverage (frozen, hash {DIAGNOSIS_CONFIG_HASH_0043[:12]}…): "
        f"required={list(CFG.required_models)} optional={list(include_optional)} "
        f"lever={list(CFG.levers_under_test)} sut={CFG.sut_hash[:12]}…"
    )

    try:
        result = run_diagnosis_cells(
            ledger_path=LEDGER,
            artifact_dir=ARTIFACT_DIR,
            include_optional=include_optional,
            live=True,
            budget_s=args.budget_s,
        )
    except ExclusiveEndpointContended as e:
        print(f"STOP-AND-WARN: {e}", file=sys.stderr)
        print(f"refusal proof recorded at {LEDGER}", file=sys.stderr)
        return 2
    except PoolRunError as e:
        print(f"STOP-AND-WARN: {e}", file=sys.stderr)
        return 2

    summary = build_diagnosis_run_summary(LEDGER)
    SUMMARY.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                k: summary[k]
                for k in (
                    "found_unsubmitted_before",
                    "found_unsubmitted_after",
                    "inconclusive_before",
                    "inconclusive_after",
                    "conversions",
                    "regressions",
                    "net",
                    "verdict",
                )
            },
            indent=2,
        )
    )
    print(f"summary: {SUMMARY}")

    if result["status"] == "in-progress" or result["cells_remaining"]:
        print(
            f"stopped with {len(result['cells_remaining'])} cells remaining "
            f"({result['status']}) — re-invoke to resume"
        )
        return 3
    print(f"diagnosis run complete; ledger: {LEDGER}; artifacts: {ARTIFACT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
