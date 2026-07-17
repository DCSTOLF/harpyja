"""Spec 0048 — bake-off: CLI pool loader + report serialization (non-live).

The ~9h grid is the operator run; these pin the verifiable non-live pieces — the
pool loader ties the frozen config Ns (44/9) to the REAL 0047 fixture, and the
report payload serializes the typed outcome.
"""

from __future__ import annotations

from harpyja.eval.bakeoff_analysis import (
    BakeoffOutcome,
    ModelExclusion,
    assemble_bakeoff,
)
from harpyja.eval.bakeoff_cli import load_bakeoff_pool, report_payload
from harpyja.eval.bakeoff_config import PREREGISTERED_BAKEOFF_CONFIG_0048

_CFG = PREREGISTERED_BAKEOFF_CONFIG_0048


def test_load_bakeoff_pool_matches_frozen_ns():
    case_ids, reachability, cases_by_id = load_bakeoff_pool()
    assert len(case_ids) == 53
    conceptual = sum(1 for t in reachability.values() if t == "conceptual")
    lexical = sum(1 for t in reachability.values() if t == "lexical")
    # the REAL fixture ties exactly to the frozen config Ns (the powered claim's N)
    assert conceptual == _CFG.conceptual_n == 44
    assert lexical == _CFG.lexical_n == 9


def test_load_bakeoff_pool_carries_query_repo_and_gold_where_present():
    _ids, _reach, cases_by_id = load_bakeoff_pool()
    sample = cases_by_id["astropy__astropy-12907"]
    assert {"gold", "gold_withheld", "query", "repo"} <= set(sample)
    assert sample["query"] and sample["repo"]
    # gold resolved from the audited expected_spans source, normalized to the
    # run_verified_case shape (file/start_line/end_line).
    assert {"file", "start_line", "end_line"} <= set(sample["gold"])
    # the enlarged cases are unprovisioned -> gold None (an operator input, never
    # fabricated); only the resolved subset carries gold.
    with_gold = [c for c, v in cases_by_id.items() if v["gold"] is not None]
    without_gold = [c for c, v in cases_by_id.items() if v["gold"] is None]
    assert len(with_gold) == 19  # the resolved/provisioned subset
    assert without_gold  # the enlarged majority await provisioning


def test_report_payload_serializes_typed_outcome():
    rep = assemble_bakeoff(
        {}, surviving_models=("qwen3:14b",),
        exclusions=(ModelExclusion("qwen3:8b", "unservable"),
                    ModelExclusion("qwen3.5:4b", "replay-fail")),
    )
    assert rep.outcome is BakeoffOutcome.INFRASTRUCTURE_HALTED
    payload = report_payload(_CFG, rep)
    assert payload["outcome"] == "infrastructure-halted"
    assert payload["ranking"] is None
    assert {e["tag"] for e in payload["exclusions"]} == {"qwen3:8b", "qwen3.5:4b"}
    assert payload["provenance"]["pool_sha256"] == _CFG.pool_sha256
    assert payload["provenance"]["conceptual_n"] == 44
