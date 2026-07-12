"""spec 0041 T18 — the committed residency-probe driver (operator tooling, AC7).

Probe-first (the 0038 discipline): NO gated live run wires the bounded-touch
mechanism before this probe's typed outcome is committed. One bounded
``keep_alive`` native touch against a resident model; the outcome is judged
ONLY from observed ``/api/ps`` ``expires_at`` movement (sent ≠ honored, the
0037 lesson) and persisted as ``probe_result.json`` (``0041/residency-probe/1``).

Exit codes: 0 = typed outcome recorded; non-zero otherwise (unreachable stack,
no resident model to probe, non-conforming result — loud, never defaulted).

Env: RESIDENCY_PROBE_MODEL (optional tag; default = first resident),
RESIDENCY_BOUND_S (default 300 — pinned into the frozen config by the
consuming run spec, per OQ1).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from harpyja.eval.residency_probe import (  # noqa: E402
    ResidencyProbeError,
    run_residency_probe,
)

OUT = Path(__file__).parent / "probe_result.json"


def main() -> int:
    try:
        result = run_residency_probe(
            model=os.environ.get("RESIDENCY_PROBE_MODEL") or None,
            keep_alive_bound_s=float(os.environ.get("RESIDENCY_BOUND_S", "300")),
        )
    except ResidencyProbeError as e:
        print(f"STOP-AND-WARN: {e}", file=sys.stderr)
        return 2
    except OSError as e:
        print(f"STOP-AND-WARN: live stack unreachable: {e}", file=sys.stderr)
        return 2
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(f"outcome: {result['outcome']} (recorded at {OUT})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
