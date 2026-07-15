"""Spec 0047 — enlargement: frozen config, sampling frame, power vocabulary,
variance predicate (unit; fakes only — no live model runs, no data acquisition).

These pin the freeze-before-run machinery that lands BEFORE any convert/author/tag
executes: the target-N arithmetic (raw pinned, output floats), the ≤3/repo sampling
frame, the five-member `PowerVerdict` committed before numbers, and the
expected-variance / single-draw-sufficiency predicate (OQ2→AC).
"""

from __future__ import annotations

import json
import math

import pytest

from harpyja.eval import enlargement as enl
from harpyja.eval.benchmark_fit import PREREGISTERED_CONFIG
from harpyja.eval.terse_dataset import _CONCEPTUAL_FLOOR_FULL

# ---- Step 1: frozen+hashed config, raw-vs-output pin (AC4) --------------------


def test_enlargement_config_pins_raw_convert_target_not_output():
    cfg = enl.PREREGISTERED_ENLARGEMENT_CONFIG_0047
    # The RAW convert count is the frozen literal AC4 pins; the OUTPUT is a design
    # goal that floats with measured attrition (reported, never frozen).
    assert isinstance(cfg.raw_convert_target, int)
    assert isinstance(cfg.target_conceptual_output_n, int)
    assert cfg.raw_convert_target > cfg.target_conceptual_output_n


def test_enlargement_config_floor_reuses_benchmark_fit_not_re_derived():
    cfg = enl.PREREGISTERED_ENLARGEMENT_CONFIG_0047
    assert cfg.conceptual_min_discordant == PREREGISTERED_CONFIG.MIN_DISCORDANT_PAIRS


def test_enlargement_config_conceptual_floor_reuses_terse_dataset():
    cfg = enl.PREREGISTERED_ENLARGEMENT_CONFIG_0047
    assert cfg.conceptual_reportability_floor == _CONCEPTUAL_FLOOR_FULL


def test_enlargement_config_target_n_is_not_a_round_number_and_carries_derivation():
    cfg = enl.PREREGISTERED_ENLARGEMENT_CONFIG_0047
    # RAW target is the STATED arithmetic, recomputed here (not a magic literal): only
    # the SHORTFALL to the target needs new raw (existing conceptual reused verbatim).
    conceptual_clean_per_raw = cfg.assumed_blind_clean_yield * cfg.assumed_conceptual_fraction
    shortfall = cfg.target_conceptual_output_n - cfg.existing_conceptual_n
    expected_raw = math.ceil(
        shortfall / conceptual_clean_per_raw * (1 + cfg.yield_uncertainty)
    )
    assert cfg.raw_convert_target == expected_raw
    # not a round number
    assert cfg.raw_convert_target % 10 != 0
    # the OUTPUT target clears the discordance floor with headroom
    bare = math.ceil(cfg.conceptual_min_discordant / cfg.realized_discordance_rate)
    assert cfg.target_conceptual_output_n >= bare
    assert cfg.target_conceptual_output_n > bare  # explicit headroom
    for field in (
        "raw_target_derivation",
        "conceptual_target_derivation",
        "floor_derivation",
        "coverage_min_derivation",
        "max_per_repo_derivation",
    ):
        assert getattr(cfg, field).strip()


def test_enlargement_config_relaxes_max_per_repo_to_eight():
    cfg = enl.PREREGISTERED_ENLARGEMENT_CONFIG_0047
    # ≤8/repo is the minimal relaxation of 0036's ≤3/repo that makes the target
    # attainable: n_repos × max_per_repo == the raw target (OQ3 resolved by data).
    assert cfg.max_per_repo == 8
    assert cfg.n_benchmark_repos * cfg.max_per_repo == cfg.raw_convert_target


def test_enlargement_config_hash_0047_is_stable():
    cfg = enl.PREREGISTERED_ENLARGEMENT_CONFIG_0047
    h = enl.enlargement_config_hash(cfg)
    assert h == enl.ENLARGEMENT_CONFIG_HASH_0047
    assert len(h) == 64 and all(c in "0123456789abcdef" for c in h)


# ---- Step 3: pinned sampling frame, ≤3/repo, deterministic selection (AC4) ----


def _frame_dict():
    return {
        "schema_version": enl.SAMPLING_FRAME_SCHEMA_VERSION,
        "hf_dataset_id": "princeton-nlp/SWE-bench_Verified",
        "hf_revision": "abc123def456",
        "hf_split": "test",
        "prior_raw_fixture_sha256": "0" * 64,
        "already_pinned_ids": ["astropy__astropy-12907"],
    }


def test_sampling_frame_schema_validates_loud():
    bad = _frame_dict()
    bad["schema_version"] = "bogus"
    with pytest.raises(enl.EnlargementError):
        enl.validate_sampling_frame(bad)
    missing = _frame_dict()
    del missing["hf_revision"]
    with pytest.raises(enl.EnlargementError):
        enl.validate_sampling_frame(missing)


def test_sampling_frame_pins_source_snapshot():
    frame = enl.validate_sampling_frame(_frame_dict())
    assert frame.hf_dataset_id == "princeton-nlp/SWE-bench_Verified"
    assert frame.hf_revision == "abc123def456"
    assert frame.hf_split == "test"
    assert frame.prior_raw_fixture_sha256 == "0" * 64


def _inst(iid: str, repo: str, *, new_file: bool = False, malformed: bool = False) -> dict:
    if malformed:
        return {"instance_id": iid, "repo": repo, "patch": "not a diff at all"}
    if new_file:
        patch = (
            f"diff --git a/{repo}/new.py b/{repo}/new.py\n"
            "new file mode 100644\n--- /dev/null\n+++ b/new.py\n@@ -0,0 +1,1 @@\n+x = 1\n"
        )
    else:
        patch = (
            "diff --git a/mod.py b/mod.py\n--- a/mod.py\n+++ b/mod.py\n"
            "@@ -10,3 +10,4 @@\n context\n-old\n+new\n more\n"
        )
    return {"instance_id": iid, "repo": repo, "patch": patch}


def test_select_candidates_excludes_already_pinned_fifty():
    cfg = enl.PREREGISTERED_ENLARGEMENT_CONFIG_0047
    rows = [
        _inst("astropy__astropy-12907", "astropy/astropy"),  # pinned
        _inst("astropy__astropy-99999", "astropy/astropy"),  # new, ok
        _inst("astropy__astropy-88888", "astropy/astropy", new_file=True),  # excluded
        _inst("astropy__astropy-77777", "astropy/astropy", malformed=True),  # excluded
    ]
    selected, exclusions = enl.select_candidates(
        rows, cfg, already_pinned_ids=("astropy__astropy-12907",)
    )
    sel_ids = {c["instance_id"] for c in selected}
    assert "astropy__astropy-12907" not in sel_ids
    assert "astropy__astropy-99999" in sel_ids
    reasons = {cid: reason for cid, reason in exclusions}
    assert reasons["astropy__astropy-12907"] == "already-pinned"
    assert reasons["astropy__astropy-88888"] == "new-file-only"
    assert reasons["astropy__astropy-77777"] == "malformed"


def test_select_candidates_caps_at_max_per_repo():
    cfg = enl.PREREGISTERED_ENLARGEMENT_CONFIG_0047
    n = cfg.max_per_repo + 2  # overflow the cap by two
    rows = [_inst(f"repo__repo-{i:03d}", "owner/repo") for i in range(n)]
    selected, exclusions = enl.select_candidates(rows, cfg, already_pinned_ids=())
    assert sum(1 for c in selected if c["repo"] == "owner/repo") == cfg.max_per_repo
    dropped = [cid for cid, reason in exclusions if reason == "per-repo-cap"]
    assert len(dropped) == n - cfg.max_per_repo


def test_select_candidates_is_deterministic_by_case_id_order():
    cfg = enl.PREREGISTERED_ENLARGEMENT_CONFIG_0047
    rows = [
        _inst("z__z-3", "z/z"),
        _inst("a__a-1", "a/a"),
        _inst("m__m-2", "m/m"),
    ]
    first, _ = enl.select_candidates(rows, cfg, already_pinned_ids=())
    second, _ = enl.select_candidates(list(reversed(rows)), cfg, already_pinned_ids=())
    assert [c["instance_id"] for c in first] == [c["instance_id"] for c in second]
    assert [c["instance_id"] for c in first] == sorted(
        c["instance_id"] for c in first
    )


# ---- Step 5: frozen PowerVerdict vocabulary + theoretical ceiling (AC5) --------


def test_power_verdict_values_are_exactly_the_five_committed():
    assert {v.value for v in enl.PowerVerdict} == {
        "powered",
        "still-under-powered",
        "discordance-still-insufficient",
        "insufficient-enlarged-coverage",
        "variance-requires-multi-draw",
    }


def test_theoretical_discordance_ceiling_is_conceptual_stratum_size():
    # Max possible discordance is the whole conceptual stratum — computable from
    # tag counts ALONE (no located sets, the AC6 scope fix).
    assert enl.theoretical_discordance_ceiling(40) == 40
    assert enl.theoretical_discordance_ceiling(3) == 3


def test_decide_bakeoff_power_types_powered_when_ceiling_clears_and_coverage_ok():
    cfg = enl.PREREGISTERED_ENLARGEMENT_CONFIG_0047
    assert enl.decide_bakeoff_power(cfg, conceptual_n=40, coverage=40) is enl.PowerVerdict.POWERED


def test_decide_bakeoff_power_types_still_under_powered_below_floor():
    cfg = enl.PREREGISTERED_ENLARGEMENT_CONFIG_0047
    v = enl.decide_bakeoff_power(cfg, conceptual_n=5, coverage=5)
    assert v is enl.PowerVerdict.STILL_UNDER_POWERED


def test_decide_bakeoff_power_types_insufficient_enlarged_coverage():
    cfg = enl.PREREGISTERED_ENLARGEMENT_CONFIG_0047
    # ceiling clears (conceptual_n >= floor) but coverage below the derived minimum
    v = enl.decide_bakeoff_power(cfg, conceptual_n=40, coverage=3)
    assert v is enl.PowerVerdict.INSUFFICIENT_ENLARGED_COVERAGE


def test_decide_bakeoff_power_types_discordance_still_insufficient():
    cfg = enl.PREREGISTERED_ENLARGEMENT_CONFIG_0047
    v = enl.decide_bakeoff_power(cfg, conceptual_n=40, coverage=40, observed_discordance=2)
    assert v is enl.PowerVerdict.DISCORDANCE_STILL_INSUFFICIENT


def test_power_verdict_predicate_order_frozen():
    cfg = enl.PREREGISTERED_ENLARGEMENT_CONFIG_0047
    # below floor AND below coverage min AND observed below floor → earliest wins.
    v = enl.decide_bakeoff_power(cfg, conceptual_n=2, coverage=1, observed_discordance=0)
    assert v is enl.PowerVerdict.STILL_UNDER_POWERED
    assert enl.POWER_VERDICT_PREDICATE_ORDER[0] is enl.PowerVerdict.STILL_UNDER_POWERED


# ---- Step 7: expected variance at N + single-draw sufficiency (OQ2→AC) ---------


def test_expected_variance_shrinks_with_n():
    assert enl.expected_variance_at_n(40) < enl.expected_variance_at_n(20)
    assert enl.expected_variance_at_n(20) < enl.expected_variance_at_n(10)


def test_single_draw_suffices_false_when_variance_exceeds_band():
    assert enl.single_draw_suffices(40, effect_band=0.02) is False
    cfg = enl.PREREGISTERED_ENLARGEMENT_CONFIG_0047
    v = enl.decide_ab_power(cfg, conceptual_n=40, coverage=40, effect_band=0.02)
    assert v is enl.PowerVerdict.VARIANCE_REQUIRES_MULTI_DRAW


def test_single_draw_suffices_true_when_variance_within_band():
    assert enl.single_draw_suffices(40, effect_band=0.1) is True
    cfg = enl.PREREGISTERED_ENLARGEMENT_CONFIG_0047
    v = enl.decide_ab_power(cfg, conceptual_n=40, coverage=40, effect_band=0.1)
    assert v is enl.PowerVerdict.POWERED


# ---- Steps 16-17: power re-check artifact (compute / validate / load) (AC5) ----


def _recheck_kwargs(**over):
    base = dict(
        lexical_n=20,
        conceptual_n=40,
        coverage=40,
        leaky_count=11,
        blind_ineligible_count=17,
        dropped_count=11,
        effect_band=0.1,
    )
    base.update(over)
    return base


def test_compute_power_recheck_matches_computed_truth():
    cfg = enl.PREREGISTERED_ENLARGEMENT_CONFIG_0047
    result = enl.compute_power_recheck(cfg, **_recheck_kwargs())
    # every per-question verdict equals the pure decider recomputed here
    assert result.schema_version == enl.POWER_RECHECK_SCHEMA_VERSION
    assert result.config_hash == enl.ENLARGEMENT_CONFIG_HASH_0047
    for _q, verdict in result.questions.items():
        assert verdict in {v.value for v in enl.PowerVerdict}
    bakeoff = [v for q, v in result.questions.items() if q.startswith("bakeoff:")]
    assert bakeoff  # a verdict per named pair
    assert all(v == enl.decide_bakeoff_power(cfg, 40, 40).value for v in bakeoff)
    assert result.questions["policy-baseline-variance"] == enl.decide_ab_power(
        cfg, conceptual_n=40, coverage=40, effect_band=0.1
    ).value


def test_power_recheck_round_trips_through_validate():
    cfg = enl.PREREGISTERED_ENLARGEMENT_CONFIG_0047
    result = enl.compute_power_recheck(cfg, **_recheck_kwargs())
    payload = enl.power_recheck_payload(result)
    revalidated = enl.validate_power_recheck(payload)
    assert revalidated == result


def test_power_recheck_types_still_under_powered_when_conceptual_short():
    cfg = enl.PREREGISTERED_ENLARGEMENT_CONFIG_0047
    result = enl.compute_power_recheck(cfg, **_recheck_kwargs(conceptual_n=5, coverage=5))
    bakeoff = [v for q, v in result.questions.items() if q.startswith("bakeoff:")]
    assert all(v == enl.PowerVerdict.STILL_UNDER_POWERED.value for v in bakeoff)


def test_validate_power_recheck_rejects_off_enum_verdict():
    cfg = enl.PREREGISTERED_ENLARGEMENT_CONFIG_0047
    payload = enl.power_recheck_payload(enl.compute_power_recheck(cfg, **_recheck_kwargs()))
    payload["questions"]["policy-baseline-variance"] = "not-a-verdict"
    with pytest.raises(enl.EnlargementError):
        enl.validate_power_recheck(payload)


def test_validate_power_recheck_rejects_unknown_schema():
    cfg = enl.PREREGISTERED_ENLARGEMENT_CONFIG_0047
    payload = enl.power_recheck_payload(enl.compute_power_recheck(cfg, **_recheck_kwargs()))
    payload["schema_version"] = "0047/power/999"
    with pytest.raises(enl.EnlargementError):
        enl.validate_power_recheck(payload)


def test_load_committed_power_recheck_prefers_archive(tmp_path):
    archive = tmp_path / "specs" / ".archive" / "0047-enlargement"
    live = tmp_path / "specs" / "0047-enlargement"
    archive.mkdir(parents=True)
    live.mkdir(parents=True)
    cfg = enl.PREREGISTERED_ENLARGEMENT_CONFIG_0047
    arch_payload = enl.power_recheck_payload(enl.compute_power_recheck(cfg, **_recheck_kwargs()))
    arch_payload["lexical_n"] = 999  # tag the archive copy
    (archive / "power_recheck.json").write_text(json.dumps(arch_payload), encoding="utf-8")
    live_payload = enl.power_recheck_payload(enl.compute_power_recheck(cfg, **_recheck_kwargs()))
    (live / "power_recheck.json").write_text(json.dumps(live_payload), encoding="utf-8")
    loaded = enl.load_committed_power_recheck(root=tmp_path)
    assert loaded.lexical_n == 999  # archive won


def test_power_recheck_reuses_pool_pairs_and_floor_by_identity():
    # T19: the theoretical re-check REUSES the 0040 named pairs + the 0023/benchmark_fit
    # floor by identity (never re-derived); it does NOT route through pool_precheck's
    # located-set arithmetic (that is the empirical bake-off, out of scope).
    from harpyja.eval.pool_precheck import PREREGISTERED_POOL_CONFIG_0040

    cfg = enl.PREREGISTERED_ENLARGEMENT_CONFIG_0047
    result = enl.compute_power_recheck(cfg, **_recheck_kwargs())
    for model_a, model_b in PREREGISTERED_POOL_CONFIG_0040.pairs:
        assert f"bakeoff:{model_a}-vs-{model_b}" in result.questions
    assert cfg.conceptual_min_discordant is PREREGISTERED_CONFIG.MIN_DISCORDANT_PAIRS


def test_load_committed_power_recheck_falls_back_to_live(tmp_path):
    live = tmp_path / "specs" / "0047-enlargement"
    live.mkdir(parents=True)
    cfg = enl.PREREGISTERED_ENLARGEMENT_CONFIG_0047
    payload = enl.power_recheck_payload(enl.compute_power_recheck(cfg, **_recheck_kwargs()))
    (live / "power_recheck.json").write_text(json.dumps(payload), encoding="utf-8")
    loaded = enl.load_committed_power_recheck(root=tmp_path)
    assert loaded.conceptual_n == 40
