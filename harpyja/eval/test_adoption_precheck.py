"""Spec 0042 — adoption: frozen pre-registered measurement config + the total
pure typed-outcome decider over per-case paired buckets (never marginals)."""

from __future__ import annotations

import dataclasses
import inspect
import json

import pytest

from harpyja.eval.adoption_precheck import (
    ADOPTION_CONFIG_HASH_0042,
    ADOPTION_CONFIG_SCHEMA_VERSION,
    PREREGISTERED_ADOPTION_CONFIG_0042,
    AdoptionCell,
    AdoptionOutcome,
    adoption_config_hash,
    build_adoption_cells,
    build_adoption_config_artifact,
    committed_adoption_config_path,
    decide_adoption_outcome,
    load_committed_0040_pilot_ledger,
    load_committed_adoption_config,
)
from harpyja.eval.locate_accuracy import LocateBucket
from harpyja.eval.pool_precheck import (
    POOL_CONFIG_HASH_0040,
    PREREGISTERED_POOL_CONFIG_0040,
)

_CFG = PREREGISTERED_ADOPTION_CONFIG_0042

_RFWS = LocateBucket.RIGHT_FILE_WRONG_SPAN
_EXACT = LocateBucket.CORRECT


# ---- frozen config + hash (AC5) -----------------------------------------------


def test_adoption_config_hash_is_stable():
    assert ADOPTION_CONFIG_HASH_0042 == adoption_config_hash(_CFG)
    assert len(ADOPTION_CONFIG_HASH_0042) == 64
    # Frozen dataclass — a mutable config is not a freeze.
    with pytest.raises(dataclasses.FrozenInstanceError):
        _CFG.min_rfws_denominator = 1  # type: ignore[misc]


def test_adoption_config_pins_all_outcome_shaping_fields():
    # Baseline is THE committed 0040 pilot ledger — pinned by spec id, schema
    # version AND the 0040 frozen config hash the ledger itself cites.
    assert _CFG.baseline_spec == "0040"
    assert _CFG.baseline_ledger_schema_version == "0040/pilot/1"
    assert _CFG.baseline_config_hash == POOL_CONFIG_HASH_0040
    # The pilot case set is CONSUMED from the 0040 freeze, not re-selected.
    assert _CFG.pilot_case_ids == PREREGISTERED_POOL_CONFIG_0040.pilot_case_ids
    # Model coverage pinned PRE-RUN: "wall-clock allows" can never shrink
    # below required; optional models are recorded-if-run.
    assert _CFG.required_models == ("qwen3:14b",)
    assert _CFG.optional_models == ("qwen3:8b", "qwen3.5:4b")
    # Bucket constants ride the committed LocateBucket by IDENTITY (one-oracle
    # rule) — never re-typed literals.
    assert _CFG.rfws_bucket == LocateBucket.RIGHT_FILE_WRONG_SPAN.value
    assert _CFG.exact_bucket == LocateBucket.CORRECT.value
    # The power floor and the committed precedence order.
    assert _CFG.min_rfws_denominator == 3
    assert _CFG.outcome_precedence == tuple(o.value for o in AdoptionOutcome)


def test_adoption_precheck_reuses_committed_locate_bucket_oracle():
    # One-oracle reuse, identity-asserted (the 0032 pattern).
    from harpyja.eval import adoption_precheck, locate_accuracy

    assert adoption_precheck.LocateBucket is locate_accuracy.LocateBucket


# ---- the total pure decider (AC5) -----------------------------------------------


def _grid_cells(
    *,
    adopted: bool,
    rfws_n: int,
    conversions: int,
    regressions: int,
    model: str = "qwen3:14b",
) -> list[AdoptionCell]:
    """Per-case cells realizing one grid corner: `rfws_n` baseline-RFWS cells
    of which the first `conversions` flip to exact; `regressions` cells flip
    exact→RFWS; one neutral cell. Symbols invoked in every clean cell iff
    `adopted`."""
    inv = 3 if adopted else 0
    cells = [
        AdoptionCell(
            case_id=f"rfws{i}",
            model=model,
            baseline_bucket=_RFWS,
            rerun_bucket=_EXACT if i < conversions else _RFWS,
            symbols_invocations=inv,
        )
        for i in range(rfws_n)
    ]
    cells += [
        AdoptionCell(
            case_id=f"reg{i}",
            model=model,
            baseline_bucket=_EXACT,
            rerun_bucket=_RFWS,
            symbols_invocations=inv,
        )
        for i in range(regressions)
    ]
    cells.append(
        AdoptionCell(
            case_id="neutral",
            model=model,
            baseline_bucket=LocateBucket.EMPTY,
            rerun_bucket=LocateBucket.EMPTY,
            symbols_invocations=inv,
        )
    )
    return cells


def test_decide_adoption_outcome_grid_totality():
    # The full cross of {adoption zero/nonzero} x {rfws denominator below/at
    # the floor} x {conversions 0/1+} x {regressions 0/1+}: EXACTLY one of the
    # four committed outcomes for every corner — no gap, no overlap, no
    # exception (total pure function).
    outcomes = set(AdoptionOutcome)
    for adopted in (False, True):
        for rfws_n in (2, 4):  # floor is 3: one side below, one side at/above
            for conversions in (0, 1):
                for regressions in (0, 2):
                    cells = _grid_cells(
                        adopted=adopted,
                        rfws_n=rfws_n,
                        conversions=conversions,
                        regressions=regressions,
                    )
                    decision = decide_adoption_outcome(_CFG, cells)
                    assert decision.outcome in outcomes
                    # The committed precedence, corner by corner.
                    if not adopted:
                        expected = AdoptionOutcome.STILL_NOT_ADOPTED
                    elif conversions >= 1:
                        expected = AdoptionOutcome.ADOPTED_AND_CONVERTS
                    elif rfws_n < _CFG.min_rfws_denominator:
                        expected = AdoptionOutcome.ADOPTED_UNDER_POWERED
                    else:
                        expected = AdoptionOutcome.ADOPTED_NO_CONVERSION
                    assert decision.outcome is expected
                    # The decision always carries the frozen hash it was
                    # decided under.
                    assert decision.config_hash == ADOPTION_CONFIG_HASH_0042


def test_adoption_boundary_still_not_adopted_iff_zero_clean_cell_symbols():
    # Zero clean-cell symbols invocations → STILL_NOT_ADOPTED, even when a
    # noise flip (rfws→exact WITHOUT symbols) is present.
    cells = _grid_cells(adopted=False, rfws_n=3, conversions=1, regressions=0)
    decision = decide_adoption_outcome(_CFG, cells)
    assert decision.outcome is AdoptionOutcome.STILL_NOT_ADOPTED
    assert decision.adoption_count == 0
    # Symbols invoked ONLY in a degraded (non-clean) re-run cell does not
    # count: the boundary is CLEAN-cell invocations.
    degraded_only = [
        AdoptionCell(
            case_id="deg",
            model="qwen3:14b",
            baseline_bucket=_RFWS,
            rerun_bucket=None,  # degraded re-run — not a clean cell
            symbols_invocations=5,
        ),
        AdoptionCell(
            case_id="clean",
            model="qwen3:14b",
            baseline_bucket=_RFWS,
            rerun_bucket=_RFWS,
            symbols_invocations=0,
        ),
    ]
    decision = decide_adoption_outcome(_CFG, degraded_only)
    assert decision.outcome is AdoptionOutcome.STILL_NOT_ADOPTED
    # ...and ANY nonzero clean-cell invocation disproves "structurally
    # unreachable": never STILL_NOT_ADOPTED (iff, other direction).
    one_use = _grid_cells(adopted=True, rfws_n=4, conversions=0, regressions=0)
    decision = decide_adoption_outcome(_CFG, one_use)
    assert decision.outcome is not AdoptionOutcome.STILL_NOT_ADOPTED
    assert decision.adoption_count > 0


def test_conversion_predicate_is_bidirectional_from_paired_buckets():
    # 1 rfws→exact conversion (symbols invoked) alongside 2 exact→rfws
    # regressions, rfws denominator 3 (at the floor): the label carries the
    # signal (ADOPTED_AND_CONVERTS), the record carries the honesty (net -1).
    cells = _grid_cells(adopted=True, rfws_n=3, conversions=1, regressions=2)
    decision = decide_adoption_outcome(_CFG, cells)
    assert decision.outcome is AdoptionOutcome.ADOPTED_AND_CONVERTS
    assert decision.conversions == 1
    assert decision.regressions == 2
    assert decision.net == -1
    assert decision.rfws_denominator == 3
    assert decision.under_powered is False
    # The signature takes per-case records ONLY — marginal counts are
    # structurally impossible to pass.
    params = list(inspect.signature(decide_adoption_outcome).parameters)
    assert params == ["config", "cells"]
    # A flip in a case where symbols was NOT invoked is retained in the
    # conversion count but is not an adoption-caused signal: with zero
    # clean-cell invocations the boundary wins (never CONVERTS).
    noise = _grid_cells(adopted=False, rfws_n=3, conversions=1, regressions=0)
    assert (
        decide_adoption_outcome(_CFG, noise).outcome
        is AdoptionOutcome.STILL_NOT_ADOPTED
    )


def test_under_powered_gated_by_min_rfws_denominator():
    # No conversion at denominator 2 (a 14b-only run, by construction) →
    # ADOPTED_UNDER_POWERED, never a refutation claim.
    two = _grid_cells(adopted=True, rfws_n=2, conversions=0, regressions=0)
    decision = decide_adoption_outcome(_CFG, two)
    assert decision.outcome is AdoptionOutcome.ADOPTED_UNDER_POWERED
    assert decision.rfws_denominator == 2
    assert decision.under_powered is True
    # At the floor (3+): the honest null — ADOPTED_NO_CONVERSION.
    three = _grid_cells(adopted=True, rfws_n=3, conversions=0, regressions=0)
    decision = decide_adoption_outcome(_CFG, three)
    assert decision.outcome is AdoptionOutcome.ADOPTED_NO_CONVERSION
    assert decision.under_powered is False
    # A conversion signal fires even under the floor, but the decision record
    # carries the under-powered caveat (AC7: a signal, not an inferential
    # claim).
    signal_under = _grid_cells(adopted=True, rfws_n=2, conversions=1, regressions=0)
    decision = decide_adoption_outcome(_CFG, signal_under)
    assert decision.outcome is AdoptionOutcome.ADOPTED_AND_CONVERTS
    assert decision.under_powered is True


def test_partial_model_coverage_uses_per_model_denominator():
    # Cells from a 14b-only re-run are typed against 14b's OWN clean-cell
    # universe — never the pooled 33-cell / 0-of-28 baseline it never had.
    ledger = load_committed_0040_pilot_ledger()
    entries = ledger["entries"]
    # A fake 14b-only re-run mirroring the baseline buckets, symbols invoked
    # once per clean cell.
    rerun = {
        key: {
            "bucket": cell.get("bucket"),
            "degrade": cell.get("degrade"),
            "symbols_invocations": 1,
        }
        for key, cell in entries.items()
        if key.endswith("::qwen3:14b")
    }
    cells = build_adoption_cells(entries, rerun, models=("qwen3:14b",))
    decision = decide_adoption_outcome(_CFG, cells)
    # 14b's committed clean-cell universe: 10 clean of 11 (one degrade).
    assert decision.adoption_denominator == 10
    assert decision.adoption_count == 10
    assert decision.adoption_by_model == (("qwen3:14b", 10, 10),)
    # 14b's own RFWS universe: exactly 2 committed clean RFWS cells
    # (astropy__astropy-12907, psf__requests-1766) → under-powered by
    # construction for a no-conversion result.
    assert decision.rfws_denominator == 2
    assert decision.outcome is AdoptionOutcome.ADOPTED_UNDER_POWERED
    # Required coverage satisfied: 14b ran.
    assert decision.missing_required == ()
    # An 8b-only run records the missing REQUIRED model — the pinned coverage
    # can never quietly shrink below required.
    rerun_8b = {
        key: {
            "bucket": cell.get("bucket"),
            "degrade": cell.get("degrade"),
            "symbols_invocations": 1,
        }
        for key, cell in entries.items()
        if key.endswith("::qwen3:8b")
    }
    cells_8b = build_adoption_cells(entries, rerun_8b, models=("qwen3:8b",))
    decision_8b = decide_adoption_outcome(_CFG, cells_8b)
    assert decision_8b.missing_required == ("qwen3:14b",)
    assert decision_8b.rfws_denominator == 1  # pallets__flask-5014 only


# ---- committed frozen-config artifact + archive-first loader (AC5) -------------


def test_committed_adoption_config_artifact_matches_computed_truth():
    obj = load_committed_adoption_config()
    assert obj["schema_version"] == ADOPTION_CONFIG_SCHEMA_VERSION
    assert obj["config_hash"] == ADOPTION_CONFIG_HASH_0042
    # The committed values equal the frozen in-code config (json round-trip
    # normalizes tuples to lists).
    truth = json.loads(json.dumps(dataclasses.asdict(_CFG)))
    assert obj["config"] == truth
    # ...and the artifact builder is the one oracle for the committed shape.
    assert obj == json.loads(json.dumps(build_adoption_config_artifact()))


def test_adoption_config_loader_pins_archive_first(tmp_path):
    # The evidence-path convention: pin specs/.archive/... FIRST from
    # authoring, live specs/0042-adoption/ fallback.
    archived = (
        tmp_path
        / "specs"
        / ".archive"
        / "0042-adoption"
        / "precheck"
        / "adoption_config.json"
    )
    live = tmp_path / "specs" / "0042-adoption" / "precheck" / "adoption_config.json"
    for path, marker in ((archived, "from-archive"), (live, "from-live")):
        path.parent.mkdir(parents=True, exist_ok=True)
        artifact = build_adoption_config_artifact()
        artifact["marker"] = marker
        path.write_text(json.dumps(artifact), encoding="utf-8")
    # Both present → archive wins.
    assert committed_adoption_config_path(root=tmp_path) == archived
    assert load_committed_adoption_config(root=tmp_path)["marker"] == "from-archive"
    # Archive absent → live fallback.
    archived.unlink()
    assert committed_adoption_config_path(root=tmp_path) == live
    assert load_committed_adoption_config(root=tmp_path)["marker"] == "from-live"
