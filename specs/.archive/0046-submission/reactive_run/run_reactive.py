"""Spec 0046 — the committed dual-hash STOP-AND-WARN driver (T27).

Runs one arm of the two-arm re-measurement through the 0041 exclusive-endpoint
gate. Re-verifies BOTH the committed config hash AND the working-tree SUT hash at
every invocation (typed STOP on drift). Resumable via the arm ledger.

    python run_reactive.py <baseline|new> [budget_s]

Exit codes: 0 complete, 3 work-remaining (budget), 2 exclusive-endpoint contended
or a typed STOP (SUT/config drift, endpoint unreachable).
"""
import json
import sys
from pathlib import Path

from harpyja.eval.pool_pilot import PoolRunError
from harpyja.eval.reactive_config import (
    PREREGISTERED_REACTIVE_CONFIG_0046,
    REACTIVE_CONFIG_HASH_0046,
    compute_sut_hash,
)
from harpyja.eval.reactive_run import run_reactive_cells

HERE = Path(__file__).resolve().parent
_COMMITTED = HERE / "reactive_config.json"


def _stop(msg: str, code: int) -> None:
    print(f"STOP-AND-WARN: {msg}", file=sys.stderr)
    raise SystemExit(code)


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in ("baseline", "new"):
        _stop("usage: run_reactive.py <baseline|new> [budget_s]", 2)
    arm = sys.argv[1]
    budget_s = float(sys.argv[2]) if len(sys.argv) > 2 else 5400.0

    # Dual-hash verify: the committed config (config hash + frozen SUT hash) must
    # match the in-code config AND the working-tree SUT — else the freeze aged.
    if not _COMMITTED.is_file():
        _stop(f"committed config {_COMMITTED} absent — freeze it (T27) first", 2)
    committed = json.loads(_COMMITTED.read_text())
    if committed.get("config_hash") != REACTIVE_CONFIG_HASH_0046:
        _stop(
            f"committed config_hash {committed.get('config_hash')} != in-code "
            f"{REACTIVE_CONFIG_HASH_0046} — the config drifted after freeze",
            2,
        )
    frozen_sut = committed.get("sut_hash")
    live_sut = compute_sut_hash()
    if frozen_sut != live_sut:
        _stop(
            f"working-tree SUT hash {live_sut} != committed {frozen_sut} — the "
            "SUT drifted after the stage-2 freeze; restore or re-freeze",
            2,
        )

    try:
        result = run_reactive_cells(
            arm=arm,
            ledger_path=HERE / f"{arm}_ledger.json",
            artifact_dir=HERE / f"{arm}_artifacts",
            include_optional=tuple(PREREGISTERED_REACTIVE_CONFIG_0046.optional_models),
            live=True,
            budget_s=budget_s,
            expected_sut_hash=frozen_sut,
        )
    except PoolRunError as e:
        _stop(str(e), 2)

    print("STATUS:", result["status"], "arm:", arm)
    remaining = result["cells_remaining"]
    print("cells_remaining:", len(remaining))
    raise SystemExit(0 if not remaining else 3)


if __name__ == "__main__":
    main()
