"""spec 0041 T19 — the committed gated-run driver (operator tooling, AC8).

The exclusive-endpoint gate, live: start check + a re-check before each model
block, every check recorded into a ``0041/pilot/2`` proof ledger. A contended
endpoint is the typed stop ``exclusive-endpoint-contended`` — non-zero exit,
zero cells, no bypass (the only sanctioned unblock is changing the
environment). This driver runs the gate-proof pass (no pilot cells — the
enlargement/bake-off specs pass their own ``run_cell`` through
``run_gated_pool_pilot``); it is also the AC6 enforced consumer: preflight
mechanically asserts the live opt-in selection works before anything fires.

Probe-first (AC4): the driver REFUSES to declare a residency mechanism until
the committed probe outcome exists; the wiring tripwire fails loudly on any
wiring↔evidence drift.

Exit codes: 0 = gate passed, proof recorded; 2 = typed stop (contended /
probe missing / selection contract violated); non-zero otherwise.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from harpyja.eval.exclusivity_gate import ExclusiveEndpointContended  # noqa: E402
from harpyja.eval.gate_run import run_gated_pool_pilot  # noqa: E402
from harpyja.eval.live_test_selection import (  # noqa: E402
    LiveSelectionError,
    assert_live_optin_selection,
)
from harpyja.eval.pool_precheck import PREREGISTERED_POOL_CONFIG_0040  # noqa: E402
from harpyja.eval.residency_probe import (  # noqa: E402
    ResidencyProbeError,
    assert_residency_wiring_matches_committed_outcome,
    load_committed_residency_probe_result,
)

CFG = PREREGISTERED_POOL_CONFIG_0040
LEDGER = Path(__file__).parent / "gate_proof.json"


def main() -> int:
    # AC6 enforced consumer: the opt-in selection is proven mechanically
    # before any live traffic — never documentation-only.
    try:
        counts = assert_live_optin_selection(REPO_ROOT)
    except LiveSelectionError as e:
        print(f"STOP-AND-WARN: {e}", file=sys.stderr)
        return 2
    print(
        f"selection contract: {counts['optin']} live tests opt-in reachable, "
        f"{counts['live_in_default']} in the default selection"
    )

    # Probe-first: the residency mechanism is whatever the committed evidence
    # says it is — refuse to run gated live work before the probe is committed.
    try:
        probe = load_committed_residency_probe_result()
    except ResidencyProbeError as e:
        print(
            f"STOP-AND-WARN: no committed residency probe ({e}) — run "
            "specs/0041-gates/residency_probe/run_residency_probe.py first",
            file=sys.stderr,
        )
        return 2
    touch_enabled = probe["outcome"] == "touch-rebounds"
    assert_residency_wiring_matches_committed_outcome(
        touch_enabled=touch_enabled, committed=probe
    )
    print(f"residency mechanism (probe-proven): {probe['outcome']}")

    if LEDGER.is_file():
        LEDGER.unlink()  # each gate-proof pass records its own fresh proof
    try:
        result = run_gated_pool_pilot(
            CFG,
            ledger_path=LEDGER,
            pilot_models=list(CFG.model_tags),
            cases=[],  # gate-proof pass: checks + proof, no pilot cells
            run_cell=lambda case, model: (_ for _ in ()).throw(
                RuntimeError("gate-proof pass runs no cells")
            ),
            live=True,
        )
    except ExclusiveEndpointContended as e:
        print(f"STOP-AND-WARN: {e}", file=sys.stderr)
        print(f"refusal proof recorded at {LEDGER}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    print(f"gate PASSED; proof ledger: {LEDGER}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
