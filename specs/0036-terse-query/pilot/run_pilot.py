"""spec 0036 T15+T17 — live pilot run (two arms) + the AC4 gate. RESUMABLE.

For each authored pilot case (the tagged 0036/1 fixture) and each arm of
`PREREGISTERED_AC8_CONFIG_0036` (qwen3:14b vs qwen3:4b-instruct), runs
`run_verified_case` against the case's provisioned worktree and persists the
verifier artifact durably via the 0035 `live_artifact_dir` home
(VERIFIER_SCHEMA_VERSION 0034/1). Arm-major order (all cases on arm A, then
arm B) to minimize model swaps.

Degrade posture (AC5): a typed environment degrade (no-trajectory ValueError,
or a verifier_status != PASSED) gets ONE bounded re-run; if it degrades again
it is RECORDED BY CAUSE in the ledger and excluded from the pairs — never
counted clean, never silent. STOP-AND-WARN on unreachable infra.

Resumability: every (case, arm) outcome is written to pilot_results.json
immediately; completed entries are skipped on re-invocation; the script exits
3 while work remains (re-invoke), 0 when the pilot is complete — at which
point it applies `decide_ac8` under the frozen 0036 config and writes
gate_report.json (config hash cited) beside the ledger.

Gold span: the FIRST expected_span of the pinned raw case (single-span golds
for 8/10 cases; within-case pairing means both arms score against the same
gold either way).
"""

from __future__ import annotations

import dataclasses
import json
import sys
import time
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from harpyja.config.settings import Settings  # noqa: E402
from harpyja.eval.ac8_pilot import (  # noqa: E402
    AC8_CONFIG_HASH_0036,
    PREREGISTERED_AC8_CONFIG_0036,
)
from harpyja.eval.live_artifacts import live_artifact_dir  # noqa: E402
from harpyja.eval.live_verifier import run_verified_case  # noqa: E402
from harpyja.eval.locate_accuracy import LocateBucket  # noqa: E402
from harpyja.eval.pilot_runner import PilotCaseOutcome, gate_report  # noqa: E402
from harpyja.gateway.gateway import ModelGateway  # noqa: E402

FIXTURES = REPO_ROOT / "harpyja" / "eval" / "fixtures"
RAW = FIXTURES / "swebench_verified.raw.jsonl"
TERSE = FIXTURES / "swebench_verified.terse.jsonl"
WORKTREES = REPO_ROOT / "eval_work" / "worktrees"
LEDGER = Path(__file__).parent / "pilot_results.json"
GATE_OUT = Path(__file__).parent / "gate_report.json"

CFG = PREREGISTERED_AC8_CONFIG_0036
ARMS = (CFG.reference_model_a, CFG.reference_model_b)
BUDGET_S = 400  # leave headroom under the 600s invocation cap
MAX_ATTEMPTS = 2  # one bounded re-run per (case, arm)


def _preflight() -> None:
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=10) as r:
            served = {m["name"] for m in json.loads(r.read())["models"]}
    except Exception as e:  # noqa: BLE001
        raise SystemExit(f"STOP-AND-WARN: Ollama unreachable: {e}")
    missing = set(ARMS) - served
    if missing:
        raise SystemExit(f"STOP-AND-WARN: pilot arms not servable: {sorted(missing)}")


def _load_ledger() -> dict:
    if LEDGER.exists():
        return json.loads(LEDGER.read_text())
    return {"config_hash": AC8_CONFIG_HASH_0036, "entries": {}}


def _save_ledger(ledger: dict) -> None:
    LEDGER.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _settings(arm: str) -> Settings:
    return dataclasses.replace(
        Settings(),
        lm_api_base="http://127.0.0.1:11434/v1",
        lm_model=arm,
        scout_max_turns=10,
        scout_wall_clock_s=240.0,
        lm_http_timeout_s=300.0,
    )


def _run_one(case_id: str, query: str, gold: dict, arm: str) -> dict:
    settings = _settings(arm)
    gateway = ModelGateway(api_base=settings.lm_api_base, model=settings.lm_model)
    out_dir = live_artifact_dir(f"pilot_0036/{arm.replace(':', '_')}")
    try:
        result, artifact_path = run_verified_case(
            case_name=case_id,
            settings=settings,
            gateway=gateway,
            gold_span=gold,
            out_dir=out_dir,
            repo_path=str(WORKTREES / case_id),
            query=query,
        )
    except ValueError as e:
        return {"bucket": None, "degrade": f"no-trajectory: {e}", "artifact": None}
    with open(artifact_path) as f:
        artifact = json.load(f)
    if result.status != "PASSED":
        return {
            "bucket": None,
            "degrade": f"verifier:{result.failure_reason}",
            "artifact": str(artifact_path),
        }
    return {
        "bucket": artifact["terminal_bucket"],
        "degrade": None,
        "artifact": str(artifact_path),
    }


def main() -> None:
    _preflight()
    terse_rows = [json.loads(l) for l in TERSE.read_text().splitlines() if l.strip()]
    if any(r.get("query_provenance") == "placeholder-pending-offline-authoring" for r in terse_rows):
        raise SystemExit("STOP-AND-WARN: fixture still holds placeholder rows — run T12 first")
    raw_index = {
        json.loads(l)["case_id"]: json.loads(l)
        for l in RAW.read_text().splitlines()
        if l.strip()
    }
    ledger = _load_ledger()
    entries = ledger["entries"]
    start = time.monotonic()

    for arm in ARMS:  # arm-major: one model swap total
        for row in terse_rows:
            key = f"{row['case_id']}::{arm}"
            done = entries.get(key)
            if done and (done["bucket"] is not None or done["attempts"] >= MAX_ATTEMPTS):
                continue
            if time.monotonic() - start > BUDGET_S:
                print("budget reached — resumable, re-invoke to continue")
                _save_ledger(ledger)
                raise SystemExit(3)
            attempts = (done or {}).get("attempts", 0) + 1
            sp = raw_index[row["case_id"]]["expected_spans"][0]
            gold = {"file": sp["path"], "start_line": sp["start_line"], "end_line": sp["end_line"]}
            t0 = time.monotonic()
            outcome = _run_one(row["case_id"], row["query"], gold, arm)
            outcome["attempts"] = attempts
            entries[key] = outcome
            _save_ledger(ledger)
            print(
                f"  {key}: bucket={outcome['bucket']} degrade={outcome['degrade']} "
                f"attempt={attempts} ({time.monotonic() - t0:.0f}s)"
            )

    # Anything still degraded after MAX_ATTEMPTS is a recorded exclusion.
    outcomes: list[PilotCaseOutcome] = []
    for row in terse_rows:
        a = entries[f"{row['case_id']}::{ARMS[0]}"]
        b = entries[f"{row['case_id']}::{ARMS[1]}"]
        outcomes.append(
            PilotCaseOutcome(
                case_id=row["case_id"],
                bucket_a=LocateBucket(a["bucket"]) if a["bucket"] else None,
                bucket_b=LocateBucket(b["bucket"]) if b["bucket"] else None,
                degrade_a=a["degrade"],
                degrade_b=b["degrade"],
            )
        )
    report = gate_report(outcomes)
    payload = {
        "outcome": report["outcome"].value,
        "config_hash": report["config_hash"],
        "arms": list(ARMS),
        "pairs_run": report["pairs_run"],
        "signal_discordant": report["signal_discordant"],
        "excluded": report["excluded"],
        "next_step": report["outcome"].next_step(),
    }
    GATE_OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
