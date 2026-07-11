"""Spec 0039 — AC6: resumable ledger, STOP-AND-WARN preflight, seed probe."""

from __future__ import annotations

import json

import pytest

from harpyja.eval import locate_probe
from harpyja.eval.think_ab import AB_CONFIG_HASH_0039, PREREGISTERED_AB_CONFIG_0039
from harpyja.eval.think_ab_run import (
    AB_LEDGER_SCHEMA_VERSION,
    AbLedger,
    AbRunError,
    ab_preflight,
    require_live_stack,
    seed_honoring_probe,
)

_CFG = PREREGISTERED_AB_CONFIG_0039


def test_ab_ledger_resumes_completed_cases(tmp_path):
    # The run outlasts one invocation: a re-opened ledger skips recorded cells.
    path = tmp_path / "ab_ledger.json"
    ledger = AbLedger(path, config_hash=AB_CONFIG_HASH_0039)
    assert not ledger.has("case1", "on", 0)
    ledger.record(
        "case1", "on", 0, {"bucket": "correct", "artifact": "/tmp/a.json"}
    )
    reopened = AbLedger(path, config_hash=AB_CONFIG_HASH_0039)
    assert reopened.has("case1", "on", 0)
    assert not reopened.has("case1", "off", 0)
    assert not reopened.has("case1", "on", 1)


def test_ab_ledger_schema_validates_loud(tmp_path):
    path = tmp_path / "ab_ledger.json"
    path.write_text(
        json.dumps({"schema_version": "9999/9", "config_hash": "x", "entries": {}}),
        encoding="utf-8",
    )
    with pytest.raises(AbRunError):
        AbLedger(path, config_hash=AB_CONFIG_HASH_0039)
    # A ledger written under a DIFFERENT frozen config is not resumable — loud.
    good = tmp_path / "other.json"
    good.write_text(
        json.dumps(
            {
                "schema_version": AB_LEDGER_SCHEMA_VERSION,
                "config_hash": "not-the-frozen-hash",
                "entries": {},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(AbRunError):
        AbLedger(good, config_hash=AB_CONFIG_HASH_0039)


def test_driver_preflight_stops_when_model_tag_unserved():
    # The frozen model tag must be SERVED before any arm fires (the default
    # lm_model tag is NOT servable — the 0036 lesson): STOP-AND-WARN, loud.
    with pytest.raises(AbRunError) as err:
        ab_preflight(_CFG, served_tags=["qwen3:4b-instruct"], seed_probe="honored")
    assert "qwen3:14b" in str(err.value)


def test_seed_honoring_probe_two_call_identical_completion():
    # Two same-request+same-seed calls returning identical completions →
    # the endpoint honors `seed` and the config claim may be upgraded.
    calls: list[int] = []

    def fake_call(seed: int) -> str:
        calls.append(seed)
        return "identical completion"

    assert seed_honoring_probe(fake_call, seed=1039) == "honored"
    assert calls == [1039, 1039]


def test_seed_probe_negative_keeps_config_claim_unverified():
    # Differing completions → the claim STAYS "unverified" (the 0037 lesson:
    # never record provenance an endpoint may silently drop) — and the
    # preflight result records the downgrade rather than faking pairing.
    responses = iter(["completion A", "completion B"])

    def fake_call(seed: int) -> str:
        return next(responses)

    assert seed_honoring_probe(fake_call, seed=1039) == "unverified"
    result = ab_preflight(
        _CFG, served_tags=["qwen3:14b", "qwen3:4b-instruct"], seed_probe="unverified"
    )
    assert result["seed_honoring"] == "unverified"
    assert result["model_served"] is True


def test_fold_repeats_any_success():
    # The frozen K-fold rule: McNemar needs ONE binary outcome per case+arm, so
    # K repeats collapse via any-success — the folded bucket is the best across
    # repeats (repeats never become pseudo-independent samples).
    from harpyja.eval.locate_accuracy import LocateBucket
    from harpyja.eval.think_ab_run import fold_repeats

    bucket, degrade = fold_repeats(
        [LocateBucket.EMPTY, LocateBucket.RIGHT_FILE_WRONG_SPAN], [None, None]
    )
    assert bucket is LocateBucket.RIGHT_FILE_WRONG_SPAN and degrade is None
    # One clean repeat beats one degraded repeat (any-success).
    bucket, degrade = fold_repeats([None, LocateBucket.CORRECT], ["wall-clock", None])
    assert bucket is LocateBucket.CORRECT and degrade is None
    # ALL repeats degraded → the cell is a typed degrade, never silently empty.
    bucket, degrade = fold_repeats([None, None], ["wall-clock", "wall-clock"])
    assert bucket is None and degrade == "wall-clock"


def test_strict_run_skip_is_hard_fail():
    # The deliverable run posture reuses the committed locate_probe helper:
    # under HARPYJA_REQUIRE_LIVE_STACK a missing stack FAILS, never skips.
    assert require_live_stack is locate_probe.require_live_stack
    assert require_live_stack(False, env={"HARPYPA_X": "0"}) == "skip"
    assert (
        require_live_stack(False, env={"HARPYJA_REQUIRE_LIVE_STACK": "1"}) == "fail"
    )
