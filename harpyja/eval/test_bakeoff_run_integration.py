"""Spec 0048 — bake-off: integration wiring (AC1 preflight, AC2 ledger + durable
artifact, AC4/AC5/AC6 report).

Marked ``@pytest.mark.integration`` (skip-not-fail). The verdict-shaping LOGIC is
exercised here with injected fakes (no live stack); the ~9h live grid is the
operator run of T22.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harpyja.eval.bakeoff_analysis import BakeoffOutcome, PairOutcome
from harpyja.eval.bakeoff_config import (
    BAKEOFF_CONFIG_HASH_0048,
    PREREGISTERED_BAKEOFF_CONFIG_0048,
)
from harpyja.eval.bakeoff_run import (
    BakeoffLedger,
    BakeoffPreflightObservations,
    BakeoffPreflightOutcome,
    BakeoffRunError,
    adjudicate_bakeoff_preflight,
    bakeoff_preflight,
    build_bakeoff_artifact,
    build_bakeoff_report,
    probe_served_membership,
    reproducibility_replay_probe,
)
from harpyja.eval.exclusivity_gate import build_exclusivity_record, validate_exclusivity_record
from harpyja.eval.locate_accuracy import LocateBucket

pytestmark = pytest.mark.integration

_CFG = PREREGISTERED_BAKEOFF_CONFIG_0048
C = LocateBucket.CORRECT
E = LocateBucket.EMPTY


# ---- AC1 preflight -----------------------------------------------------------


def test_preflight_routes_through_assert_local_first():
    log: list[str] = []

    def fake_assert(api_base, **kw):
        log.append("assert_local")

    def fake_tags(api_base):
        log.append("api_tags")
        return list(_CFG.model_tags)

    membership = probe_served_membership(
        _CFG, api_base="http://localhost:11434",
        assert_local_fn=fake_assert, tags_reader=fake_tags,
    )
    assert log == ["assert_local", "api_tags"]  # loopback gate FIRST
    assert all(membership.values())


def test_preflight_positive_api_tags_membership_per_tag():
    # a down endpoint returns no served tags -> nothing passes trivially
    down = probe_served_membership(
        _CFG, api_base="x", assert_local_fn=lambda *a, **k: None,
        tags_reader=lambda a: [],
    )
    assert down == {t: False for t in _CFG.model_tags}
    # one tag missing -> only it is False
    partial = probe_served_membership(
        _CFG, api_base="x", assert_local_fn=lambda *a, **k: None,
        tags_reader=lambda a: ["qwen3:14b", "qwen3:8b"],
    )
    assert partial["qwen3.5:4b"] is False
    assert partial["qwen3:14b"] is True


def test_preflight_config_tags_asserted_present():
    membership = probe_served_membership(
        _CFG, api_base="x", assert_local_fn=lambda *a, **k: None,
        tags_reader=lambda a: list(_CFG.model_tags),
    )
    assert set(membership) == set(_CFG.model_tags)


def test_preflight_excludes_model_on_coherence_or_tool_call_fail():
    obs = {
        "qwen3:14b": BakeoffPreflightObservations(True, True, True, "reproducible"),
        "qwen3:8b": BakeoffPreflightObservations(True, False, True, "reproducible"),
        "qwen3.5:4b": BakeoffPreflightObservations(True, True, False, "reproducible"),
    }
    outcomes, exclusions = bakeoff_preflight(_CFG, observations=obs)
    assert outcomes["qwen3:14b"] is BakeoffPreflightOutcome.PREFLIGHT_PASS
    assert outcomes["qwen3:8b"] is BakeoffPreflightOutcome.COHERENCE_FAIL
    assert outcomes["qwen3.5:4b"] is BakeoffPreflightOutcome.TOOL_CALL_MALFORMED
    excluded = {e.tag for e in exclusions}
    assert excluded == {"qwen3:8b", "qwen3.5:4b"}  # not scored zero — excluded


def test_reproducibility_replay_excludes_on_bucket_mismatch():
    stable = {"a__a-1": [C, C], "a__a-2": [E, E], "a__a-3": [C, C]}
    flaky = {"a__a-1": [C, C], "a__a-2": [E, C], "a__a-3": [C, C]}

    def _runner(table):
        return lambda case_id, run_ix: table[case_id][run_ix]

    assert reproducibility_replay_probe(_runner(stable), list(stable)) == "reproducible"
    assert reproducibility_replay_probe(_runner(flaky), list(flaky)) == "replay-fail"

    # a replay-fail observation EXCLUDES via REPLAY_FAIL
    obs = {
        t: BakeoffPreflightObservations(True, True, True, "replay-fail")
        for t in _CFG.model_tags
    }
    outcomes, exclusions = bakeoff_preflight(_CFG, observations=obs)
    assert all(o is BakeoffPreflightOutcome.REPLAY_FAIL for o in outcomes.values())
    assert len(exclusions) == 3


def test_adjudicate_bakeoff_preflight_precedence():
    # unservable is most-fundamental; replay is the last excluding gate
    assert adjudicate_bakeoff_preflight(
        BakeoffPreflightObservations(False, False, False, "replay-fail")
    ) is BakeoffPreflightOutcome.UNSERVABLE
    assert adjudicate_bakeoff_preflight(
        BakeoffPreflightObservations(True, True, True, "reproducible")
    ) is BakeoffPreflightOutcome.PREFLIGHT_PASS


# ---- AC2 resumable ledger + durable artifact ---------------------------------


def _exclusivity():
    check = {"label": "start", "timestamp": "2026-07-15T00:00:00+00:00", "clean": True,
             "residents": ["qwen3:14b"], "foreign": []}
    return build_exclusivity_record(checks=[check], model_set=_CFG.model_tags)


def test_bakeoff_ledger_resumable_keyed_to_config_hash(tmp_path: Path):
    path = tmp_path / "ledger.json"
    led = BakeoffLedger(path, config_hash=BAKEOFF_CONFIG_HASH_0048)
    assert not led.has("a__a-1", "qwen3:14b")
    led.record("a__a-1", "qwen3:14b", {"bucket": "correct"})
    assert led.get("a__a-1", "qwen3:14b") == {"bucket": "correct"}

    # reopened under the SAME hash resumes
    reopened = BakeoffLedger(path, config_hash=BAKEOFF_CONFIG_HASH_0048)
    assert reopened.has("a__a-1", "qwen3:14b")

    # a DIFFERENT config hash is not resumable — loud
    with pytest.raises(BakeoffRunError):
        BakeoffLedger(path, config_hash="deadbeef")

    # an unknown schema_version is rejected
    path.write_text('{"schema_version": "9999/9", "config_hash": "x", "entries": {}}')
    with pytest.raises(BakeoffRunError):
        BakeoffLedger(path, config_hash="x")


def test_bakeoff_artifact_carries_full_schema():
    art = build_bakeoff_artifact(
        _CFG, case_id="django__django-14315", model="qwen3:14b",
        bucket=LocateBucket.CORRECT, tools={"symbols": 2, "grep": 3},
        symbols_adopted=True, reasoning_tokens=812, submitted=True, surviving=True,
        found_but_unsubmitted=False, serving_transport="ollama-openai",
        sut_hash="sut-abc123", exclusivity_record=_exclusivity(),
        heavy_repo_degrade=False, degrade=None,
    )
    for key in (
        "case_id", "model", "bucket", "tools", "symbols_adopted", "reasoning_tokens",
        "submitted", "surviving", "found_but_unsubmitted", "model_identity",
        "serving_transport", "decoding", "pool_sha256", "sut_hash", "exclusivity",
        "heavy_repo_degrade",
    ):
        assert key in art, f"artifact missing {key}"
    assert art["decoding"] == {"temperature": 0.0, "top_p": 1.0, "seed": 0}
    assert art["pool_sha256"] == _CFG.pool_sha256
    validate_exclusivity_record(art["exclusivity"])  # a valid 0041 proof


def test_bakeoff_artifact_records_heavy_repo_degrade_rate():
    degraded = build_bakeoff_artifact(
        _CFG, case_id="astropy__astropy-12907", model="qwen3.5:4b",
        bucket=None, tools={}, symbols_adopted=False, reasoning_tokens=0,
        submitted=False, surviving=False, found_but_unsubmitted=False,
        serving_transport="ollama-openai", sut_hash="s", exclusivity_record=_exclusivity(),
        heavy_repo_degrade=True, degrade="heavy-repo-timeout",
    )
    assert degraded["heavy_repo_degrade"] is True
    assert degraded["degrade"] == "heavy-repo-timeout"


# ---- AC4/AC5/AC6 report ------------------------------------------------------


def _entries(spec):
    out = {}
    for case_id, per_model in spec.items():
        for model, val in per_model.items():
            out[f"{case_id}::{model}"] = {"bucket": val.value}
    return out


def test_report_splits_by_reachability_no_pooled_headline():
    # 36 conceptual cases each 14b-located / 8b-not -> a separating-ish pair, plus lexical
    reach = {}
    spec = {}
    for i in range(38):
        cid = f"repoX__repoX-{i}"
        reach[cid] = "conceptual"
        spec[cid] = {"qwen3:14b": C, "qwen3:8b": E, "qwen3.5:4b": E}
    reach["lex__lex-1"] = "lexical"
    spec["lex__lex-1"] = {"qwen3:14b": C, "qwen3:8b": E, "qwen3.5:4b": E}

    rep = build_bakeoff_report(_CFG, _entries(spec), reach)
    assert rep.conceptual_pair_results  # per-pair conceptual verdicts present
    assert "qwen3:14b" in rep.lexical_stats  # lexical descriptive per model
    field_names = {f.name for f in __import__("dataclasses").fields(type(rep))}
    assert not any("average" in n or "pooled" in n for n in field_names)


def test_report_flags_repo_concentrated_on_separating_pairs():
    # all 38 discordant cases in ONE repo -> dropping it collapses -> concentrated
    reach = {}
    spec = {}
    for i in range(38):
        cid = f"onerepo__onerepo-{i}"
        reach[cid] = "conceptual"
        spec[cid] = {"qwen3:14b": C, "qwen3:8b": E, "qwen3.5:4b": C}
    rep = build_bakeoff_report(_CFG, _entries(spec), reach)
    p14_8 = next(r for r in rep.conceptual_pair_results if r.pair == ("qwen3:14b", "qwen3:8b"))
    if p14_8.outcome is PairOutcome.PAIR_SEPARATES:
        assert p14_8.repo_concentrated is True
    assert rep.per_repo_distribution  # per-repo b-c distribution reported


def test_report_symbols_adoption_and_found_but_unsubmitted_per_model():
    reach = {"a__a-1": "conceptual"}
    spec = {"a__a-1": {"qwen3:14b": C, "qwen3:8b": E, "qwen3.5:4b": E}}
    rep = build_bakeoff_report(
        _CFG, _entries(spec), reach,
        symbols_adoption={"qwen3:14b": 0.77, "qwen3:8b": 0.5, "qwen3.5:4b": 0.4},
        found_but_unsubmitted={"qwen3:14b": 1, "qwen3:8b": 3, "qwen3.5:4b": 2},
    )
    assert rep.symbols_adoption["qwen3:14b"] == 0.77
    assert rep.found_but_unsubmitted["qwen3:8b"] == 3


def test_report_aggregates_adoption_and_fu_from_entries_when_not_passed():
    # per-model artifact fields on the ledger entries are aggregated when the
    # caller does not supply the dicts explicitly.
    reach = {"a__a-1": "conceptual", "a__a-2": "conceptual"}
    entries = {
        "a__a-1::qwen3:14b": {
            "bucket": "correct", "symbols_adopted": True, "found_but_unsubmitted": False,
        },
        "a__a-2::qwen3:14b": {
            "bucket": "empty", "symbols_adopted": False, "found_but_unsubmitted": True,
        },
        "a__a-1::qwen3:8b": {
            "bucket": "empty", "symbols_adopted": True, "found_but_unsubmitted": True,
        },
    }
    rep = build_bakeoff_report(_CFG, entries, reach)
    assert rep.symbols_adoption["qwen3:14b"] == 0.5  # 1 of 2 cells adopted
    assert rep.found_but_unsubmitted["qwen3:14b"] == 1
    assert rep.found_but_unsubmitted["qwen3:8b"] == 1


def test_report_outcome_is_typed_member():
    rep = build_bakeoff_report(_CFG, {}, {})
    assert isinstance(rep.outcome, BakeoffOutcome)
