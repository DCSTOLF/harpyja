"""RED (0046 T17/T18, AC7): PREREGISTERED_REACTIVE_CONFIG_0046 (stage-2 freeze).

The FIVE-sided predicate + verdict precedence are frozen in the reviewed spec
BEFORE the numbers (committed at T22). This object names the frozen choice as
DATA — the SUT hash (covering the gate + reactive_policy + confirm + signals),
the sanity band, the baseline-relative threshold DERIVATION RULE — and is hashed
+ committed (T27) AFTER the SUT lever lands and the baseline arm yields the
derived literals, BEFORE any new-arm spend.
"""

from __future__ import annotations

import dataclasses

from harpyja.eval.reactive_config import (
    PREREGISTERED_REACTIVE_CONFIG_0046,
    REACTIVE_CONFIG_HASH_0046,
    ReactiveConfig,
    compute_sut_hash,
    reactive_config_hash,
)


def test_config_is_frozen_dataclass():
    assert dataclasses.is_dataclass(ReactiveConfig)
    with_ = PREREGISTERED_REACTIVE_CONFIG_0046
    import pytest

    with pytest.raises(dataclasses.FrozenInstanceError):
        with_.config_id = "x"  # type: ignore[misc]


def test_config_hash_is_stable():
    assert REACTIVE_CONFIG_HASH_0046 == reactive_config_hash(PREREGISTERED_REACTIVE_CONFIG_0046)
    assert len(REACTIVE_CONFIG_HASH_0046) == 64


def test_sut_hash_covers_gate_reactive_confirm_and_signals():
    files = PREREGISTERED_REACTIVE_CONFIG_0046.sut_files
    for rel in (
        "harpyja/scout/confidence_gate.py",
        "harpyja/scout/confidence_signals.py",
        "harpyja/scout/reactive_policy.py",
        "harpyja/scout/confirm.py",
    ):
        assert rel in files
    # the hash is computed over the current SUT bytes
    assert PREREGISTERED_REACTIVE_CONFIG_0046.sut_hash == compute_sut_hash()


def test_baseline_band_is_1_to_3_frozen():
    assert PREREGISTERED_REACTIVE_CONFIG_0046.baseline_band == (1, 3)


def test_flagged_wrong_emitted_ceiling_is_baseline_relative_fraction_below_one():
    frac = PREREGISTERED_REACTIVE_CONFIG_0046.flagged_wrong_emitted_ceiling_fraction
    assert 0 < frac < 1  # the relabel-tolerance RULE is frozen (< 1)
    # the DERIVED absolute literals are committed at T27 (post-baseline) — None now.
    assert PREREGISTERED_REACTIVE_CONFIG_0046.flagged_wrong_emitted_ceiling is None


def test_flag_rate_range_derivation_rule_frozen():
    # the flag-rate range is a derived config literal committed at T27 — None now,
    # but its derivation rule (an upper bound on the flagged fraction) is named.
    assert PREREGISTERED_REACTIVE_CONFIG_0046.flag_rate_max is None
    assert "flag" in PREREGISTERED_REACTIVE_CONFIG_0046.flag_rate_rule.lower()


def test_named_cells_pinned():
    named = PREREGISTERED_REACTIVE_CONFIG_0046.named_cells
    assert "pallets__flask-5014" in " ".join(named)
    assert "django__django-14315::qwen3:8b" in named
    assert "pytest-dev__pytest-10081::qwen3:14b" in named


def test_thirty_three_cells_consumed_from_frozen_pool():
    cfg = PREREGISTERED_REACTIVE_CONFIG_0046
    n_models = len(cfg.required_models) + len(cfg.optional_models)
    assert len(cfg.pilot_case_ids) * n_models == 33
    assert cfg.inert_model == "qwen3.5:4b"
    assert cfg.beneficiary_model == "qwen3:14b"


def test_three_member_precedence_encoded():
    assert PREREGISTERED_REACTIVE_CONFIG_0046.verdict_precedence == (
        "under-powered",
        "trades-again",
        "dissolves-trade",
        "no-effect",
    )


# --- Spec 0046 (T27): the committed config-freeze artifact pin -----------------
def test_committed_reactive_config_matches_computed_truth():
    """The committed reactive_config.json matches the in-code truth: the stable
    config hash (over the frozen None-literal config) and the working-tree SUT
    hash. The derived flagged-wrong-emitted ceiling = the frozen fraction x the
    measured baseline s->wc (recorded as audit data; the config literal stays
    None so the hash is stable)."""
    import json
    from pathlib import Path

    # Evidence-path convention: specs/.archive first, live specs/ fallback.
    root = Path(__file__).resolve().parents[2]
    rel = "reactive_run/reactive_config.json"
    archived = root / "specs" / ".archive" / "0046-submission" / rel
    live = root / "specs" / "0046-submission" / rel
    path = archived if archived.is_file() else live
    committed = json.loads(path.read_text())
    assert committed["config_hash"] == REACTIVE_CONFIG_HASH_0046
    assert committed["sut_hash"] == compute_sut_hash()
    derived = committed["derived_thresholds"]
    assert derived["flagged_wrong_emitted_ceiling"] == int(
        PREREGISTERED_REACTIVE_CONFIG_0046.flagged_wrong_emitted_ceiling_fraction
        * derived["baseline_swc"]
    )
    # the frozen config literal is still None (stable hash), the number is audit.
    assert PREREGISTERED_REACTIVE_CONFIG_0046.flagged_wrong_emitted_ceiling is None
