"""spec 0044 T21 — the committed submission re-measurement driver (operator
tooling, AC6/AC7; the 0040/0041/0042/0043 run_*.py shape).

Re-measures the COMMITTED 0042 pinned pilot cells under the ONE 0044 lever
(the 0043 unconditional sentence REMOVED + the confidence-conditioned
mid-loop nudge ADDED; params byte-frozen) through ``run_gated_pool_pilot``
(0041 exclusive-endpoint gate: start + per-block checks, no bypass),
resumable via ``PoolPilotLedger`` at ``0041/pilot/2`` keyed by
``SUBMISSION_CONFIG_HASH_0044``. Model coverage is CONSUMED from the frozen
config: required (``qwen3:14b``) always; optional (``qwen3:8b``,
``qwen3.5:4b``) only via ``--optional`` / ``--all-optional``.

The stage-2 freeze is enforced HERE: the driver loads the COMMITTED
``submission_config.json``, verifies its recorded config hash against the
in-code frozen object AND its recorded post-lever SUT hash against the
working tree — a drift on either is a typed STOP (exit 2) before any cell
runs (``run_submission_cells`` re-checks the SUT hash internally).

The summary joins AFTER (this run) against BEFORE (the config-pinned,
sha256-verified committed 0040/0042 pre-nudge table) with the IDENTICAL
detector version, and reports per-model conversions / regressions / NET /
firing rate, found-but-unsubmitted per side, all true conditions, and the
total pure five-member AC8 verdict.

STOP-AND-WARN, never a silent skip. Exit codes:
  0 = all requested-coverage cells clean-complete; ledger + per-case
      trajectory-verified artifacts + machine-readable summary persisted here.
  2 = typed stop (exclusive-endpoint-contended / endpoint unreachable /
      unserved pinned model / config-or-SUT drift) — refusal is loud; the
      only sanctioned unblock is changing the environment (or re-freezing).
  3 = stopped with work remaining (budget stop or fresh typed degrades due a
      bounded re-run) — re-invoke to resume; clean cells never re-run.

Budget per invocation from SUBMISSION_BUDGET_S (default 480s — headroom under
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

from harpyja.eval.exclusivity_gate import ExclusiveEndpointContended  # noqa: E402
from harpyja.eval.pool_pilot import PoolRunError  # noqa: E402
from harpyja.eval.submission_config import (  # noqa: E402
    PREREGISTERED_SUBMISSION_CONFIG_0044,
    SUBMISSION_CONFIG_HASH_0044,
    compute_sut_hash,
)
from harpyja.eval.submission_run import (  # noqa: E402
    build_submission_run_summary,
    run_submission_cells,
)

CFG = PREREGISTERED_SUBMISSION_CONFIG_0044
HERE = Path(__file__).parent
COMMITTED_CONFIG = HERE.parent / "submission_config" / "submission_config.json"
LEDGER = HERE / "submission_results.json"
ARTIFACT_DIR = HERE / "artifacts"
SUMMARY = HERE / "submission_summary.json"
BUDGET_S = float(os.environ.get("SUBMISSION_BUDGET_S", "480"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Gated 0044 confidence-conditioned-nudge re-measurement over the "
            "pinned 0042 pilot cells (STOP-AND-WARN; resumable; no bypass exists)"
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

    # Stage-2 freeze enforcement: the COMMITTED artifact is the freeze; the
    # in-code config and the working-tree SUT must both match it exactly.
    if not COMMITTED_CONFIG.is_file():
        print(
            f"STOP-AND-WARN: committed config missing at {COMMITTED_CONFIG} — "
            "the stage-2 freeze artifact must be committed BEFORE any live call",
            file=sys.stderr,
        )
        return 2
    committed = json.loads(COMMITTED_CONFIG.read_text(encoding="utf-8"))
    if committed.get("config_hash") != SUBMISSION_CONFIG_HASH_0044:
        print(
            "STOP-AND-WARN: committed config hash "
            f"{committed.get('config_hash', '')[:12]}… != computed "
            f"{SUBMISSION_CONFIG_HASH_0044[:12]}… — the frozen config drifted",
            file=sys.stderr,
        )
        return 2
    committed_sut = committed.get("config", {}).get("sut_hash")
    live_sut = compute_sut_hash()
    if live_sut != committed_sut:
        print(
            f"STOP-AND-WARN: working-tree SUT hash {live_sut[:12]}… != frozen "
            f"{str(committed_sut)[:12]}… — the AFTER cells would not run on "
            "the pinned SUT",
            file=sys.stderr,
        )
        return 2
    print(
        f"coverage (frozen, hash {SUBMISSION_CONFIG_HASH_0044[:12]}…): "
        f"required={list(CFG.required_models)} optional={list(include_optional)} "
        f"lever={list(CFG.levers_under_test)} sut={live_sut[:12]}…"
    )

    try:
        result = run_submission_cells(
            ledger_path=LEDGER,
            artifact_dir=ARTIFACT_DIR,
            include_optional=include_optional,
            live=True,
            budget_s=args.budget_s,
            expected_sut_hash=committed_sut,
        )
    except ExclusiveEndpointContended as e:
        print(f"STOP-AND-WARN: {e}", file=sys.stderr)
        print(f"refusal proof recorded at {LEDGER}", file=sys.stderr)
        return 2
    except PoolRunError as e:
        print(f"STOP-AND-WARN: {e}", file=sys.stderr)
        return 2

    summary = build_submission_run_summary(LEDGER)
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
                    "conversions",
                    "regressions",
                    "net",
                    "per_model",
                    "conditions_true",
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
    print(f"submission run complete; ledger: {LEDGER}; artifacts: {ARTIFACT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
