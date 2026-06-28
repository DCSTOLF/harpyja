"""RED (spec 0008, T05): planning matrix — all 12 rows (AC3).

The matrix is the single source of truth for routing:
(mode × classification × index_ready) → the planned tier ladder. `index_ready`
false drops the leading 0 (seed skipped, model tier runs query-only).
"""

import pytest

from harpyja.orchestrator.matrix import plan_ladder

# (mode, classification, index_ready) -> planned ladder, verbatim from the spec.
MATRIX_ROWS = [
    ("auto", "point", True, [0, 1, 2]),
    ("auto", "point", False, [1, 2]),
    ("auto", "broad", True, [0, 2]),
    ("auto", "broad", False, [2]),
    ("fast", "point", True, [0, 1]),
    ("fast", "point", False, [1]),
    ("fast", "broad", True, [0, 1]),
    ("fast", "broad", False, [1]),
    ("deep", "point", True, [0, 2]),
    ("deep", "point", False, [2]),
    ("deep", "broad", True, [0, 2]),
    ("deep", "broad", False, [2]),
]


@pytest.mark.parametrize("mode, classification, index_ready, expected", MATRIX_ROWS)
def test_matrix_all_twelve_rows(mode, classification, index_ready, expected):
    assert plan_ladder(mode, classification, index_ready) == expected


def test_matrix_index_not_ready_drops_leading_zero():
    ready = plan_ladder("auto", "point", True)
    not_ready = plan_ladder("auto", "point", False)
    assert ready[0] == 0
    assert not_ready == ready[1:]  # seed skipped, rest identical


def test_matrix_fast_broad_is_zero_one_not_deep():
    # fast wins over broad: the ceiling is Tier-1, never Deep.
    assert plan_ladder("fast", "broad", True) == [0, 1]
    assert 2 not in plan_ladder("fast", "broad", True)


def test_matrix_covers_exactly_twelve_rows():
    combos = {(m, c, i) for (m, c, i, _) in MATRIX_ROWS}
    assert len(combos) == 12
