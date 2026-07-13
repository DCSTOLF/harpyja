"""spec 0045 T23 — the committed refinement re-measurement driver (operator
tooling, AC5/AC6; the 0040/0041/0042/0043/0044 run_*.py shape).

Re-measures the COMMITTED 0042 pinned pilot cells under the ONE 0045 lever
(the REFINED require-corroboration confidence gate; params byte-frozen) through
``run_gated_pool_pilot`` (0041 exclusive-endpoint gate: start + per-block
checks, no bypass), resumable via ``PoolPilotLedger`` at ``0041/pilot/2`` keyed
by ``REFINEMENT_CONFIG_HASH_0045``. Model coverage is CONSUMED from the frozen
config: required (``qwen3:14b``) always; optional (``qwen3:8b``, ``qwen3.5:4b``)
only via ``--optional`` / ``--all-optional``.

The stage-2 freeze is enforced HERE by the DUAL-HASH gate: the driver loads the
COMMITTED ``refinement_config.json``, verifies its recorded config hash against
the in-code frozen object AND its recorded SUT hash against the working tree —
a drift on EITHER is a typed STOP (exit 2) before any cell runs
(``run_refinement_cells`` re-checks BOTH internally).

STOP-AND-WARN, never a silent skip. Exit codes:
  0 = all requested-coverage cells clean-complete; ledger + per-case verified
      artifacts + machine-readable summary persisted here.
  2 = typed stop (exclusive-endpoint-contended / endpoint unreachable /
      unserved pinned model / config-or-SUT drift) — refusal is loud.
  3 = stopped with work remaining (budget stop) — re-invoke to resume.

Budget per invocation from REFINEMENT_BUDGET_S (default 480s — headroom under a
600s invocation cap; for the full closure run use the detached nohup wrapper
loop, the 0042/0043/0044 lesson: harness background tasks die at ~20 min).
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
from harpyja.eval.refinement_config import (  # noqa: E402
    PREREGISTERED_REFINEMENT_CONFIG_0045,
    REFINEMENT_CONFIG_HASH_0045,
    compute_sut_hash,
)
from harpyja.eval.refinement_run import (  # noqa: E402
    build_refinement_run_summary,
    run_refinement_cells,
)

CFG = PREREGISTERED_REFINEMENT_CONFIG_0045
HERE = Path(__file__).parent
COMMITTED_CONFIG = HERE.parent / "refinement_config" / "refinement_config.json"
LEDGER = HERE / "refinement_results.json"
ARTIFACT_DIR = HERE / "artifacts"
SUMMARY = HERE / "refinement_summary.json"
BUDGET_S = float(os.environ.get("REFINEMENT_BUDGET_S", "480"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Gated 0045 refined-confidence-gate re-measurement over the pinned "
            "0042 pilot cells (STOP-AND-WARN; resumable; no bypass exists)"
        )
    )
    parser.add_argument(
        "--optional", action="append", default=[],
        choices=list(CFG.optional_models), metavar="TAG",
        help=f"include a frozen OPTIONAL model; repeatable: {list(CFG.optional_models)}",
    )
    parser.add_argument(
        "--all-optional", action="store_true",
        help="include every frozen optional model (full three-model coverage)",
    )
    parser.add_argument(
        "--budget-s", type=float, default=BUDGET_S,
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

    # DUAL-HASH stage-2 freeze enforcement.
    if not COMMITTED_CONFIG.is_file():
        print(
            f"STOP-AND-WARN: committed config missing at {COMMITTED_CONFIG} — "
            "the stage-2 freeze artifact must be committed BEFORE any live call",
            file=sys.stderr,
        )
        return 2
    committed = json.loads(COMMITTED_CONFIG.read_text(encoding="utf-8"))
    if committed.get("config_hash") != REFINEMENT_CONFIG_HASH_0045:
        print(
            "STOP-AND-WARN: committed config hash "
            f"{str(committed.get('config_hash', ''))[:12]}… != computed "
            f"{REFINEMENT_CONFIG_HASH_0045[:12]}… — the frozen config drifted",
            file=sys.stderr,
        )
        return 2
    committed_sut = committed.get("config", {}).get("sut_hash")
    live_sut = compute_sut_hash()
    if live_sut != committed_sut:
        print(
            f"STOP-AND-WARN: working-tree SUT hash {live_sut[:12]}… != frozen "
            f"{str(committed_sut)[:12]}… — the AFTER cells would not run on the "
            "pinned SUT",
            file=sys.stderr,
        )
        return 2
    print(
        f"coverage (frozen, hash {REFINEMENT_CONFIG_HASH_0045[:12]}…): "
        f"required={list(CFG.required_models)} optional={list(include_optional)} "
        f"lever={CFG.refined_rule_key} sut={live_sut[:12]}…"
    )

    try:
        result = run_refinement_cells(
            ledger_path=LEDGER, artifact_dir=ARTIFACT_DIR,
            include_optional=include_optional, live=True, budget_s=args.budget_s,
            expected_sut_hash=committed_sut,
            expected_config_hash=committed.get("config_hash"),
        )
    except ExclusiveEndpointContended as e:
        print(f"STOP-AND-WARN: {e}", file=sys.stderr)
        print(f"refusal proof recorded at {LEDGER}", file=sys.stderr)
        return 2
    except PoolRunError as e:
        print(f"STOP-AND-WARN: {e}", file=sys.stderr)
        return 2

    summary = build_refinement_run_summary(LEDGER)
    SUMMARY.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        k: summary[k]
        for k in ("verdict", "conditions_true", "ledger_four_sided", "head_to_head")
    }, indent=2))
    print(f"summary: {SUMMARY}")

    if result["status"] == "in-progress":
        print(f"stopped with work remaining ({result['status']}) — re-invoke to resume")
        return 3
    print(f"refinement run complete; ledger: {LEDGER}; artifacts: {ARTIFACT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
