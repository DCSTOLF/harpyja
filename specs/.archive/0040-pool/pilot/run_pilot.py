"""spec 0040 T18 — the committed three-model pilot driver (operator tooling).

RESUMABLE, STOP-AND-WARN: gates on the COMMITTED preflight result (a model
with an EXCLUDING outcome never enters the pilot — the 16B-gibberish lesson;
its pairs will type PAIR_NOT_EVALUATED_MODEL_EXCLUDED), then drives every
pinned case x preflight-passing model through ``run_verified_case`` at
``explorer_think=None`` (arm parity, frozen in config) via the resumable
``PoolPilotLedger``.

Exit codes: 0 = pilot complete (ledger full), 3 = budget exhausted while work
remains (re-invoke to resume), non-zero otherwise. Budget per invocation from
POOL_PILOT_BUDGET_S (default 480s — headroom under a 600s invocation cap).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from harpyja.eval.pool_pilot import run_pool_pilot  # noqa: E402
from harpyja.eval.pool_precheck import (  # noqa: E402
    PREREGISTERED_POOL_CONFIG_0040,
    PreflightOutcome,
    is_excluding,
)
from harpyja.eval.pool_preflight_result import (  # noqa: E402
    load_committed_pool_preflight_result,
)

CFG = PREREGISTERED_POOL_CONFIG_0040
LEDGER = Path(__file__).parent / "pilot_results.json"
OUT_DIR = REPO_ROOT / "eval_work" / "live_artifacts" / "pilot_0040"
BUDGET_S = float(os.environ.get("POOL_PILOT_BUDGET_S", "480"))


def main() -> int:
    preflight = load_committed_pool_preflight_result()
    pilot_models = [
        tag
        for tag in CFG.model_tags
        if not is_excluding(PreflightOutcome(preflight["models"][tag]["outcome"]))
    ]
    excluded = [t for t in CFG.model_tags if t not in pilot_models]
    if excluded:
        print(f"preflight-excluded (typed, recorded): {excluded}")
    if not pilot_models:
        raise SystemExit("STOP-AND-WARN: no model passed preflight — nothing to pilot")

    result = run_pool_pilot(
        CFG,
        out_dir=OUT_DIR,
        ledger_path=LEDGER,
        pilot_models=pilot_models,
        live=True,
        budget_s=BUDGET_S,
    )
    if result["status"] == "in-progress":
        print(
            f"budget exhausted, {result['cells_remaining']} cells remain — "
            f"re-invoke to resume"
        )
        return 3
    print(json.dumps(result["conceptual_locate_counts"], indent=2))
    print(f"pilot complete; ledger: {result['ledger_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
