"""RED (0045 T6, AC1): per-cell attribution over 0044's COMMITTED firing data.

AC1 diagnoses from 0044's committed per-cell artifacts (no new compute first):
per fired-on-wrong-span cell, the triggering signal is named and its weakness
attributed; for the never-fired found-unsubmitted cell (``pytest-10081::14b``),
the evidence the 0044 gate failed to credit is named. The result feeds the
FROZEN stage-1 table's ``select_ranking_rule`` (T7), justifying the refinement.

The (b)/(c) recompute path delegates to the moved scout helpers BY IDENTITY
(one definition, no drift); the primary diagnosis reads the committed fields.
"""

from pathlib import Path

from harpyja.eval.discriminator_table import NO_DISCRIMINATOR_SEPARATES
from harpyja.eval.refinement_attribution import (
    ATTRIBUTION_SOURCE_DIR,
    ATTRIBUTION_SOURCE_SHA256,
    attribution_source_sha256,
    build_attribution_shape,
    diagnose_fired_on_wrong_span,
    diagnose_never_fired,
    load_0044_firing_cells,
    recompute_signals,
    select_refined_rule,
)

_ROOT = Path(__file__).resolve().parents[2]


def test_attribution_over_0044_committed_firing_artifacts():
    cells = load_0044_firing_cells()
    assert len(cells) == 32
    # Keyed "case::model".
    assert "django__django-14315::qwen3:8b" in cells
    assert "pytest-dev__pytest-10081::qwen3:14b" in cells


def test_attribution_pinned_to_committed_firing_data_by_sha256():
    assert (_ROOT / ATTRIBUTION_SOURCE_DIR).is_dir()
    assert attribution_source_sha256() == ATTRIBUTION_SOURCE_SHA256


def test_fired_on_wrong_span_cells_name_triggering_signal():
    rows = diagnose_fired_on_wrong_span(load_0044_firing_cells())
    # 6 fired-on-wrong-span cells (5 on 8b) — the committed headline.
    assert len(rows) == 6
    assert sum(1 for r in rows if r["model"] == "qwen3:8b") == 5
    for r in rows:
        # Every one fired on symbols-exact-span, uncorroborated → weak singleton.
        assert r["triggering_signal"] == "symbols-exact-span"
        assert r["grep_hits_inside_symbol_spans"] == 0
        assert r["convergent_evidence"] is False
        assert r["is_weak_singleton"] is True


def test_never_fired_cell_names_unrecognised_evidence():
    diag = diagnose_never_fired(load_0044_firing_cells())
    assert diag["cell"] == "pytest-dev__pytest-10081::qwen3:14b"
    assert diag["confidence_fired"] is False
    assert diag["submission_outcome"] == "found-unsubmitted"
    # The 0044 gate did not credit its evidence; here it was uncorroborated.
    assert diag["had_corroboration"] is False
    assert diag["unrecognised_evidence"]  # a non-empty named reason


def test_attribution_shape_selects_require_corroboration():
    shape = build_attribution_shape(load_0044_firing_cells())
    assert shape["wrong_span_all_weak_singleton"] is True
    # The rule the frozen table selects on this shape.
    row = select_refined_rule()
    assert row.rule_key == "require-corroboration"
    assert row.rule_key != NO_DISCRIMINATOR_SEPARATES


def test_recompute_signals_uses_scout_helpers_by_identity():
    # One-definition: the recompute path IS the moved scout helpers.
    from harpyja.scout import confidence_signals as sig

    assert recompute_signals.__wrapped_containment__ is sig.grep_hits_inside_symbol_spans
    assert recompute_signals.__wrapped_convergence__ is sig.convergent_evidence
    # And it actually computes over a trajectory.
    traj = {"model_turns": [
        {"role": "assistant", "content": "",
         "tool_calls": [{"id": "c1", "function": {"name": "grep", "arguments": "{}"}}]},
        {"role": "tool", "tool_call_id": "c1",
         "content": "[CodeSpan(path='m.py', start_line=10, end_line=20, "
                    "symbol=None, language=None, kind=None)]"},
        {"role": "assistant", "content": "",
         "tool_calls": [{"id": "c2", "function": {"name": "read_span", "arguments": "{}"}}]},
        {"role": "tool", "tool_call_id": "c2",
         "content": "[CodeSpan(path='m.py', start_line=18, end_line=30, "
                    "symbol=None, language=None, kind=None)]"},
    ]}
    sigs = recompute_signals(traj)
    assert sigs["convergent_evidence"] is True
