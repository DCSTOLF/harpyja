"""T26 — the BASELINE arm (reverted 0044 gate, current SUT: explorer_reactive_confirm=False).

Runs the frozen 33 cells through the 0041 exclusive-endpoint gate, resumable via
the ledger. Pre-config-freeze (no expected_sut_hash yet — the config is frozen at
T27, AFTER this arm yields per-model s->wc). Budget-bounded + resumable so a death
is lossless.
"""
import sys
from pathlib import Path

from harpyja.eval.reactive_run import run_reactive_cells

HERE = Path(__file__).resolve().parent
BUDGET_S = float(sys.argv[1]) if len(sys.argv) > 1 else 5400.0  # 90 min default

if __name__ == "__main__":
    result = run_reactive_cells(
        arm="baseline",
        ledger_path=HERE / "baseline_ledger.json",
        artifact_dir=HERE / "baseline_artifacts",
        include_optional=("qwen3:8b", "qwen3.5:4b"),
        live=True,
        budget_s=BUDGET_S,
    )
    print("STATUS:", result["status"])
    print("cells_remaining:", len(result["cells_remaining"]))
    for c in result["cells_remaining"]:
        print("  remaining:", c)
