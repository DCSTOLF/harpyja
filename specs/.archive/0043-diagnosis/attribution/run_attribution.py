"""Spec 0043 T9 — the OFFLINE attribution run (AC1, AC3). Operator driver.

Runs AFTER the T8 stage-1 lever-table freeze (the choosing rule is committed
before these numbers exist) and spends NO model compute: it is a pure
projection over the persisted machine-local trajectories in
``eval_work/live_artifacts/{pilot_0040,adoption_0042}/`` plus the two
committed run ledgers.

Output: ``specs/0043-diagnosis/attribution/attribution_table.json`` — the
COMMITTED derived table (sources pinned by filename + sha256), the 4b
inversion finding, the derived lever signals, and the mechanically selected
lever decision.

Usage: uv run python specs/0043-diagnosis/attribution/run_attribution.py
"""

from __future__ import annotations

import dataclasses
import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from harpyja.eval.adoption_run import load_pinned_adoption_cases  # noqa: E402
from harpyja.eval.clock_attribution import (  # noqa: E402
    TRAJECTORY_MISSING,
    attribute_cell,
    attribute_inversion,
    build_attribution_table,
    case_timing_estimates,
)
from harpyja.eval.lever_table import (  # noqa: E402
    LEVER_TABLE_HASH_0043,
    derive_signals,
    select_lever,
)
from harpyja.eval.submission_gap import (  # noqa: E402
    DETECTOR_VERSION,
    classify_submission,
)
from harpyja.server.types import CodeSpan  # noqa: E402

# The runs' actual loop settings (pool_pilot.py / adoption_run driver): the
# 0040/0042 cells ran at scout_max_turns=10, scout_wall_clock_s=240,
# lm_http_timeout_s=300 — max_turns here MUST match the run, not the default.
RUN_MAX_TURNS = 10

RUNS = {
    "pilot_0040": REPO / "specs/.archive/0040-pool/pilot/pilot_results.json",
    "adoption_0042": REPO
    / "specs/.archive/0042-adoption/adoption_run/adoption_results.json",
}
ARTIFACT_ROOT = REPO / "eval_work/live_artifacts"
MODELS = ("qwen3:14b", "qwen3:8b", "qwen3.5:4b")


def _model_dir(model: str) -> str:
    return model.replace(":", "_").replace(".", "_")


def main() -> int:
    cases = load_pinned_adoption_cases(REPO)
    gold_by_case = {
        c["case_id"]: (
            CodeSpan(
                path=c["gold"]["file"],
                start_line=c["gold"]["start_line"],
                end_line=c["gold"]["end_line"],
            ),
        )
        for c in cases
    }

    present_rows = []
    degraded_cells = []
    timing = {}
    inversion_samples: dict[str, dict[str, list[float]]] = {
        m: {"turns": [], "tool_bytes": [], "prompt_chars": []} for m in MODELS
    }
    degrade_counts: Counter[str] = Counter()

    for run, ledger_path in RUNS.items():
        ledger = json.loads(ledger_path.read_text())["entries"]
        for model in MODELS:
            stamps = []
            for case_id in gold_by_case:
                entry = ledger.get(f"{case_id}::{model}", {})
                degrade = entry.get("degrade")
                if degrade:
                    degrade_counts[model] += 1
                path = (
                    ARTIFACT_ROOT
                    / run
                    / _model_dir(model)
                    / f"{case_id}_verifier_artifact.json"
                )
                record = attribute_cell(
                    path,
                    gold_by_case[case_id],
                    max_turns=RUN_MAX_TURNS,
                    degrade=degrade,
                )
                record["run"] = run
                record["bucket"] = entry.get("bucket")
                record["ledger_degrade"] = degrade
                if record["degrade"] == TRAJECTORY_MISSING:
                    degraded_cells.append(
                        {"run": run, "case": case_id, "model": model, **record}
                    )
                    continue

                traj = json.loads(path.read_text())
                record["submission_outcome"] = classify_submission(
                    traj, gold_by_case[case_id]
                ).value
                stamps.append((case_id, traj["timestamp"]))

                # Inversion evidence samples (per available trajectory).
                turns = traj.get("model_turns", [])
                inversion_samples[model]["turns"].append(record["assistant_turns"])
                inversion_samples[model]["tool_bytes"].append(
                    sum(
                        len(t.get("content") or "")
                        for t in turns
                        if t.get("role") == "tool"
                    )
                )
                inversion_samples[model]["prompt_chars"].append(
                    sum(len(str(t.get("content") or "")) for t in turns)
                )

                present_rows.append(
                    {
                        "case": case_id,
                        "model": model,
                        "source_path": path,
                        "record": record,
                    }
                )
            stamps.sort(key=lambda cs: cs[1])
            timing[f"{run}::{model}"] = case_timing_estimates(stamps)

    evidence = {
        m: {
            "degrade_count": degrade_counts.get(m, 0),
            "mean_turns": (
                sum(s["turns"]) / len(s["turns"]) if s["turns"] else None
            ),
            "mean_tool_result_bytes": (
                sum(s["tool_bytes"]) / len(s["tool_bytes"])
                if s["tool_bytes"]
                else None
            ),
            "mean_prompt_chars": (
                sum(s["prompt_chars"]) / len(s["prompt_chars"])
                if s["prompt_chars"]
                else None
            ),
        }
        for m, s in inversion_samples.items()
    }
    inversion = attribute_inversion(evidence)

    # Lever signals derive from the CURRENT-SUT (post-0042) records — the
    # lever will change that surface, so 0040's pre-adoption behavior is
    # reference only. The choosing rule was frozen at T8, before these numbers.
    adoption_records = [
        r["record"] for r in present_rows if r["record"]["run"] == "adoption_0042"
    ]
    signals = derive_signals(adoption_records)
    decision = select_lever(signals)

    table = build_attribution_table(present_rows)
    table["run_max_turns"] = RUN_MAX_TURNS
    table["run_wall_clock_s"] = 240.0
    table["run_http_timeout_s"] = 300.0
    table["detector_version"] = DETECTOR_VERSION
    table["lever_table_hash"] = LEVER_TABLE_HASH_0043
    table["degraded_cells"] = degraded_cells
    table["timing_estimates"] = timing
    table["inversion_evidence"] = evidence
    table["inversion_finding"] = dataclasses.asdict(inversion)
    table["lever_signals"] = dataclasses.asdict(signals)
    table["lever_decision"] = dataclasses.asdict(decision)

    # Headline aggregates (per run × model): the loss class made countable.
    summary: dict[str, dict[str, object]] = {}
    for run in RUNS:
        for model in MODELS:
            recs = [
                r["record"]
                for r in present_rows
                if r["record"]["run"] == run and r["model"] == model
            ]
            key = f"{run}::{model}"
            summary[key] = {
                "cells": len(recs),
                "located": sum(1 for r in recs if r["turns_to_locate"] is not None),
                "found_unsubmitted": sum(
                    1 for r in recs if r["submission_outcome"] == "found-unsubmitted"
                ),
                "submission_outcomes": dict(
                    Counter(r["submission_outcome"] for r in recs)
                ),
                "terminal_causes": dict(Counter(r["terminal_cause"] for r in recs)),
            }
    table["summary"] = summary

    out = Path(__file__).parent / "attribution_table.json"
    out.write_text(json.dumps(table, indent=2, sort_keys=True) + "\n")
    print(f"wrote {out}")
    print(json.dumps(summary, indent=2, sort_keys=True))
    print("inversion:", table["inversion_finding"])
    print("signals:", table["lever_signals"])
    print("lever:", table["lever_decision"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
