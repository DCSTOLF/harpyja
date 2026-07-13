"""RED (0045 T1, AC1): the stage-1 discriminator-selection table.

The two-stage freeze's STAGE 1 (spec 0045 §Two-stage freeze): a table mapping
attribution SHAPES -> a refined ranking rule, frozen + hashed + committed
BEFORE the per-cell (b)/(c) attribution is computed. The table encodes the
CANDIDATE rules and their selecting antecedents over a CLOSED candidate signal
set; it does NOT encode the actual per-cell values (those are computed in T7,
after the freeze). Full blindness is unattainable and recorded as such: the
0044 headline facts are already public and carried here AS DATA, while the
per-cell (b)/(c) detail the table freezes OVER is declared not-yet-computed.

A typed ``NO_DISCRIMINATOR_SEPARATES`` row is the honest exit (the 0043
lever-table totality posture): if the attribution fails to separate the
fired-on-wrong-span cells from the never-fired cell within the closed set, the
refinement is not asserted.
"""

import dataclasses
import json
from pathlib import Path

import pytest

from harpyja.eval.discriminator_table import (
    CANDIDATE_SIGNALS,
    DISCRIMINATOR_SELECTION_TABLE_0045,
    DISCRIMINATOR_TABLE_HASH_0045,
    NO_DISCRIMINATOR_SEPARATES,
    discriminator_table_hash,
    select_ranking_rule,
)

_T = DISCRIMINATOR_SELECTION_TABLE_0045
_ROOT = Path(__file__).resolve().parents[2]
_COMMITTED = (
    _ROOT
    / "specs/0045-refinement/discriminator_table/discriminator_table.json"
)


def test_discriminator_table_is_frozen_dataclass():
    assert dataclasses.is_dataclass(_T)
    assert _T.table_id == "0045/discriminator-table/1"
    with pytest.raises(dataclasses.FrozenInstanceError):
        _T.table_id = "mutated"


def test_discriminator_table_hash_is_stable():
    assert discriminator_table_hash(_T) == DISCRIMINATOR_TABLE_HASH_0045
    assert discriminator_table_hash(_T) == discriminator_table_hash(_T)


def test_candidate_signal_set_is_closed():
    # Exactly the four spec-named classes; no open-ended addition.
    assert CANDIDATE_SIGNALS == frozenset({
        "symbols-exact-span",
        "grep-hit-inside-symbol-containment",
        "convergent-evidence",
        "weak-singleton",
    })
    assert set(_T.candidate_signals) == CANDIDATE_SIGNALS


def test_table_carries_no_discriminator_separates_row():
    # The typed honest-exit row exists among the rows and as the sentinel.
    keys = {r.rule_key for r in _T.rows}
    assert NO_DISCRIMINATOR_SEPARATES in keys
    row = next(r for r in _T.rows if r.rule_key == NO_DISCRIMINATOR_SEPARATES)
    assert row.asserts_refinement is False


def test_every_selectable_rule_names_a_signal_in_the_closed_set():
    for row in _T.rows:
        if row.rule_key == NO_DISCRIMINATOR_SEPARATES:
            continue
        # A selectable rule credits and/or demotes signals from the closed set.
        named = set(row.credits) | set(row.demotes)
        assert named
        assert named <= CANDIDATE_SIGNALS


def test_table_records_0044_headline_facts_as_data():
    # Partial sightedness recorded: what 0044's committed outcome already
    # published enters the table AS DATA, not as a selection input.
    facts = _T.headline_facts_0044
    assert facts["fired_on_wrong_span_total"] == 6
    assert facts["fired_on_wrong_span_8b"] == 5
    assert facts["never_fired_found_unsubmitted_cell"] == "pytest-dev__pytest-10081::qwen3:14b"
    assert facts["fired_but_ignored_total"] == 1


def test_table_declares_per_cell_bc_detail_uncomputed():
    # The per-cell (b)/(c) values the table freezes OVER are declared
    # not-yet-computed at freeze time (the attribution is T7, post-freeze).
    assert _T.per_cell_bc_detail_computed is False


def test_table_carries_per_model_gate_branch_explicitly():
    # OQ2 as a FROZEN row: lean single gate; a per-model bar is taken ONLY if
    # the same signal predicts correctly for 14b and wrongly for 8b. The choice
    # is frozen here, not post-hoc.
    branch = _T.per_model_gate_branch
    assert branch["default"] == "single-gate-refined-ranking"
    assert "same-signal-splits-by-model" in branch["per_model_only_if"]


def test_select_ranking_rule_requires_corroboration_when_wrong_spans_are_weak_singletons():
    # SELECTION (applied in T7, post-freeze): the rule is chosen on the
    # FIRED-ON-WRONG-SPAN shape — when those cells are uniformly weak singletons
    # (no convergence, no containment), require-corroboration is selected
    # (demote weak-singleton; credit convergence and containment). Selection is
    # invariant to the never-fired corroboration flag (recorded as DATA, below).
    for corrob in (True, False):
        row = select_ranking_rule({
            "wrong_span_all_weak_singleton": True,
            "never_fired_cell_had_corroboration": corrob,
        })
        assert row.rule_key == "require-corroboration"
        assert "weak-singleton" in row.demotes
        assert "convergent-evidence" in row.credits
        assert "grep-hit-inside-symbol-containment" in row.credits
        assert row.asserts_refinement is True


def test_select_ranking_rule_falls_to_no_separation_when_wrong_spans_not_weak():
    # Honest exit: if the wrong-span cells are NOT uniformly weak-singleton (they
    # fired on something corroborated, so demoting weak-singleton would not stop
    # them) and no other closed-set rule applies, no rule separates.
    row = select_ranking_rule({
        "wrong_span_all_weak_singleton": False,
        "never_fired_cell_had_corroboration": False,
    })
    assert row.rule_key == NO_DISCRIMINATOR_SEPARATES
    assert row.asserts_refinement is False


def test_committed_discriminator_table_matches_computed_truth():
    # STAGE-1 freeze pin: the committed artifact equals the in-code table, and
    # records the frozen hash. Committed BEFORE any per-cell attribution — the
    # artifact declares per_cell_bc_detail_computed False.
    assert _COMMITTED.is_file()
    art = json.loads(_COMMITTED.read_text(encoding="utf-8"))
    assert art["table_hash"] == DISCRIMINATOR_TABLE_HASH_0045
    # JSON round-trips tuples to lists; compare through the same normalization.
    normalized = json.loads(json.dumps(dataclasses.asdict(_T)))
    assert art["table"] == normalized
    assert art["table"]["per_cell_bc_detail_computed"] is False
