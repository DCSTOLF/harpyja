"""Spec 0039 — AC7: the committed typed-verdict claim, pinned to computed truth."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

from harpyja.eval.think_ab import (
    AB_CONFIG_HASH_0039,
    AB_REPORT_OUTCOMES,
    PRECHECK_STOP,
    PREREGISTERED_AB_CONFIG_0039,
)
from harpyja.eval.think_ab_claim import (
    committed_ab_claim_path,
    load_committed_ab_claim,
)
from harpyja.eval.think_ab_precheck import (
    ab_power_precheck,
    load_committed_pilot_ledger,
)


# spec 0047 enlarged the live terse fixture; 0039's committed claim is about the 19-case
# pool, re-verified against the snapshot 0047 preserved (see test_think_ab_precheck).
def _snapshot_path() -> Path:
    # archive-first (the 0036 pilot-ledger convention): 0047's dir moves to .archive on close.
    root = Path(__file__).resolve().parents[2]
    name = "pre_enlargement_terse_snapshot.jsonl"
    arch = root / "specs" / ".archive" / "0047-enlargement" / name
    return arch if arch.is_file() else root / "specs" / "0047-enlargement" / name


_TERSE_SNAPSHOT_PRE_0047 = _snapshot_path()


def _snapshot_precheck(cfg):
    reach = {
        row["case_id"]: row["reachability"]
        for row in (
            json.loads(x)
            for x in _TERSE_SNAPSHOT_PRE_0047.read_text(encoding="utf-8").splitlines()
            if x.strip()
        )
    }
    return ab_power_precheck(load_committed_pilot_ledger(), reach, cfg, full_conceptual_n=15)


def test_committed_ab_claim_matches_computed_verdict():
    # The committed claim must EQUAL the verdict recomputed from committed
    # evidence — a claim that drifts from computed truth fails loudly. On the
    # gated branch the computed truth is the AC5 pre-check outcome.
    claim = load_committed_ab_claim()
    assert claim["config_hash"] == AB_CONFIG_HASH_0039
    computed = _snapshot_precheck(PREREGISTERED_AB_CONFIG_0039)
    if claim["status"] == "gated-under-powered-stop":
        assert computed.outcome == PRECHECK_STOP
        assert claim["precheck"] == dataclasses.asdict(computed)
    else:
        # A completed-run claim must carry the split report (checked below);
        # its verdict recomputation runs from the committed pair records.
        assert claim["status"] == "completed"
        assert claim["report"]["strata"]


def test_claim_artifact_path_pins_archive_first():
    # The evidence-path convention (79f7bf2): pins target specs/.archive first;
    # the live spec dir is the explicit fallback while the spec is unarchived.
    path = committed_ab_claim_path()
    archived = "specs/.archive/0039-thinking-ab" in str(path).replace("\\", "/")
    live = "specs/0039-thinking-ab" in str(path).replace("\\", "/")
    assert archived or live
    assert path.is_file()


def test_findings_cites_n2_as_motivation_only():
    # AC8 pin: the causation stance is machine-checkable — the think-experiment
    # N=2 is MOTIVATION only, and no default flip is decided by this spec.
    from harpyja.eval.think_ab_claim import committed_findings_path

    text = committed_findings_path().read_text(encoding="utf-8").lower()
    assert "motivation only" in text
    assert "no default" in text and "flip" in text


def test_claim_split_by_reachability_not_whole_set_average():
    claim = load_committed_ab_claim()
    # The headline is TYPED — one of the unified report taxonomy — and on any
    # branch it is never a whole-set average.
    assert claim["headline"] in AB_REPORT_OUTCOMES or claim["headline"].startswith(
        "conceptual:"
    )
    assert "whole_set_accuracy" not in claim
    assert "average" not in claim
    if claim["status"] == "completed":
        assert set(claim["report"]["strata"]) == {"conceptual", "lexical"}
