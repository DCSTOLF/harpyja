"""Spec 0045 — stage-1 discriminator-selection table (AC1, T2).

STAGE 1 of the two-stage freeze. This module encodes the CANDIDATE ranking
rules and their selecting antecedents over a CLOSED candidate signal set, and
is frozen + hashed + committed (T3) BEFORE the per-cell (b)/(c) attribution is
computed (T7). It does NOT encode the actual per-cell values — ``select_ranking_rule``
is a pure function of an attribution SHAPE that is applied post-freeze.

Full blindness is unattainable and recorded: 0044's committed outcome already
published the headline attributions (5/6 fired-on-wrong-span are 8b
empty->wrong-file; the never-fired cell is ``pytest-10081::qwen3:14b``;
fired-but-ignored 1), so those live here AS DATA. What the table freezes OVER —
declared not-yet-computed — is the per-cell (b)/(c) observability detail.

The closed candidate set is the spec's OQ1 hypothesis space: a symbols-derived
exact span, a grep hit inside a symbol span (containment), convergent evidence
(>=2 tools), and weak/singleton evidence. The typed ``NO_DISCRIMINATOR_SEPARATES``
row is the honest exit (the 0043 lever-table totality posture).
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from collections.abc import Mapping
from typing import Any

# The CLOSED candidate signal set (spec OQ1). No open-ended addition.
CANDIDATE_SIGNALS = frozenset({
    "symbols-exact-span",
    "grep-hit-inside-symbol-containment",
    "convergent-evidence",
    "weak-singleton",
})

# The typed honest-exit sentinel (0043 lever-table totality posture).
NO_DISCRIMINATOR_SEPARATES = "no-discriminator-separates"


@dataclasses.dataclass(frozen=True)
class SelectionRow:
    """One candidate ranking rule: the antecedent that selects it, and which
    signals it credits (adds a firing route) vs demotes (removes one)."""

    rule_key: str
    antecedent: str
    credits: tuple[str, ...]
    demotes: tuple[str, ...]
    asserts_refinement: bool


@dataclasses.dataclass(frozen=True)
class DiscriminatorTable:
    table_id: str
    candidate_signals: tuple[str, ...]
    rows: tuple[SelectionRow, ...]
    # 0044's already-public facts, carried AS DATA (partial sightedness).
    headline_facts_0044: Mapping[str, Any]
    # The per-cell (b)/(c) detail the table freezes OVER — computed in T7.
    per_cell_bc_detail_computed: bool
    # OQ2 as a frozen row: single gate by default; per-model only under a
    # named condition.
    per_model_gate_branch: Mapping[str, str]


_ROWS: tuple[SelectionRow, ...] = (
    SelectionRow(
        rule_key="require-corroboration",
        antecedent=(
            "the fired-on-wrong-span cells are uniformly weak-singleton (no "
            "convergence, no grep-inside-symbol containment) AND the "
            "never-fired found-unsubmitted cell carried corroborated evidence "
            "the 0044 gate did not credit"
        ),
        # Credit the corroboration routes; demote the bare uncorroborated span.
        credits=("convergent-evidence", "grep-hit-inside-symbol-containment"),
        demotes=("weak-singleton",),
        asserts_refinement=True,
    ),
    SelectionRow(
        rule_key="restrict-to-symbols-derivation",
        antecedent=(
            "the fired-on-wrong-span cells fired on a NON-symbols-derived "
            "trigger (a bare grep hit) while symbols-derived spans predicted "
            "correctly"
        ),
        credits=("symbols-exact-span",),
        demotes=("weak-singleton",),
        asserts_refinement=True,
    ),
    SelectionRow(
        rule_key=NO_DISCRIMINATOR_SEPARATES,
        antecedent=(
            "the fired-on-wrong-span cells' (b)/(c) shape is indistinguishable "
            "from the never-fired/correct cells within the closed set — no rule "
            "separates; the refinement is NOT asserted"
        ),
        credits=(),
        demotes=(),
        asserts_refinement=False,
    ),
)


DISCRIMINATOR_SELECTION_TABLE_0045 = DiscriminatorTable(
    table_id="0045/discriminator-table/1",
    candidate_signals=tuple(sorted(CANDIDATE_SIGNALS)),
    rows=_ROWS,
    headline_facts_0044={
        "fired_on_wrong_span_total": 6,
        "fired_on_wrong_span_8b": 5,
        "never_fired_found_unsubmitted_cell": "pytest-dev__pytest-10081::qwen3:14b",
        "fired_but_ignored_total": 1,
        "source": "0044 committed submission_results.json / per-cell artifacts",
    },
    per_cell_bc_detail_computed=False,
    per_model_gate_branch={
        "default": "single-gate-refined-ranking",
        "per_model_only_if": (
            "same-signal-splits-by-model: the SAME signal predicts correctly "
            "for 14b and wrongly for 8b (else a per-model bar adds a knob and a "
            "generalization risk for no measured cause)"
        ),
    },
)


def select_ranking_rule(attribution: Mapping[str, Any]) -> SelectionRow:
    """Pure: given the POST-FREEZE attribution shape, return the selected row.

    Applied in T7 over the committed 0044 firing data. Total — the honest-exit
    row is the terminal else, so every attribution shape selects exactly one row.

    Selection keys on the FIRED-ON-WRONG-SPAN shape (direction (a)): if those
    cells are uniformly weak-singleton (no convergence, no containment), the
    require-corroboration rule is selected — a bare bounded symbols span no
    longer fires; convergence/containment become the firing routes. Whether the
    never-fired cell (direction (b)) is ALSO rescued is recorded separately as
    attribution DATA (``never_fired_cell_had_corroboration``); it does not gate
    the rule choice, because a rule that fixes (a) is selected on (a)'s evidence.
    ``NO_DISCRIMINATOR_SEPARATES`` is reached only when the wrong-span cells are
    NOT uniformly weak-singleton and no other closed-set rule applies.
    """
    rows = {r.rule_key: r for r in DISCRIMINATOR_SELECTION_TABLE_0045.rows}
    if attribution.get("wrong_span_all_weak_singleton"):
        return rows["require-corroboration"]
    if attribution.get("wrong_span_fired_on_non_symbols"):
        return rows["restrict-to-symbols-derivation"]
    return rows[NO_DISCRIMINATOR_SEPARATES]


def discriminator_table_hash(table: DiscriminatorTable) -> str:
    payload = json.dumps(dataclasses.asdict(table), sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


DISCRIMINATOR_TABLE_HASH_0045 = discriminator_table_hash(
    DISCRIMINATOR_SELECTION_TABLE_0045
)
