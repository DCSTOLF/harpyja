"""Eval-only configuration + repeated-run aggregation (AC5, D6).

`EvalConfig` is deliberately SEPARATE from the production frozen `Settings`: K
(repeated-run count), the proximity window, the N-floor, and the catch-rate bar
are eval-only knobs, inert to every tier/gate/matrix branch. The only `Settings`
fields the harness touches are `verify_threshold` / `verify_top_n`, overridden via
`dataclasses.replace` in the sweep — never these. Keeping the two disjoint is the
INVARIANT guard (asserted by `test_eval_config_is_independent_of_settings`).

All three magnitudes are **provisional** (parity with the spec's provisional 0.90
catch-rate bar) — tunable once the seed-set N grows.
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class EvalConfig:
    """Eval harness knobs (provisional defaults; never reach the system under test)."""

    k_runs: int = 5
    proximity_window_lines: int = 50
    n_floor: int = 30
    catch_rate_bar: float = 0.90


def aggregate_runs(values: Sequence[float]) -> dict[str, float | None]:
    """Reduce K per-run metric values to `{mean, spread}` (spread = `pstdev`, D3).

    An empty input yields `{"mean": None, "spread": 0.0}` (no runs to average);
    a single run yields spread 0.0.
    """
    if not values:
        return {"mean": None, "spread": 0.0}
    return {"mean": statistics.mean(values), "spread": statistics.pstdev(values)}
