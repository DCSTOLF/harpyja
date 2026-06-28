"""Live eval entrypoints (AC7, AC8) — the thin glue over the real stack.

`run_live_eval` drives the seed set once through the live `mode=auto` stack;
`run_live_sweep` runs the OQ2 grid and emits the trade-off table + a recommended
`(verify_threshold, verify_top_n)`. Neither flips a `Settings` default — the
recommendation is the deliverable (B1). Both write artifacts **outside** the
indexed repo.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from harpyja.config.settings import Settings
from harpyja.eval.config import EvalConfig
from harpyja.eval.dataset import load_dataset
from harpyja.eval.runner import build_live_stack, run_dataset
from harpyja.eval.sweep import run_sweep

# The grid the OQ2 sweep enumerates by default (provisional; centered on the
# spec-0008 incumbent 0.6 / 3).
DEFAULT_THRESHOLDS = (0.5, 0.6, 0.7)
DEFAULT_TOP_NS = (1, 3, 5)


def default_seed_path() -> Path:
    """The versioned seed fixture shipped with the package."""
    return Path(__file__).parent / "fixtures" / "seed.jsonl"


def run_live_eval(
    repo: str,
    *,
    settings: Settings,
    eval_config: EvalConfig,
    out_dir,
    seed_path=None,
    repo_revision: str = "unknown",
    timestamp: str = "1970-01-01T00:00:00Z",
    write: bool = True,
) -> dict:
    """Run the seed set once through the live auto stack; emit a report."""
    cases = load_dataset(seed_path or default_seed_path())
    stack = build_live_stack(settings, repo)
    return run_dataset(
        cases, settings, eval_config,
        repo_path=repo, stack=stack, out_dir=out_dir, write=write,
        repo_revision=repo_revision, timestamp=timestamp,
    )


def run_live_sweep(
    repo: str,
    *,
    base_settings: Settings,
    eval_config: EvalConfig,
    out_dir,
    thresholds: Sequence[float] = DEFAULT_THRESHOLDS,
    top_ns: Sequence[int] = DEFAULT_TOP_NS,
    seed_path=None,
    repo_revision: str = "unknown",
    timestamp: str = "1970-01-01T00:00:00Z",
    write: bool = True,
) -> dict:
    """Run the OQ2 grid live; emit the trade-off table + recommendation."""
    cases = load_dataset(seed_path or default_seed_path())
    stack = build_live_stack(base_settings, repo)
    return run_sweep(
        cases=cases,
        base_settings=base_settings,
        eval_config=eval_config,
        thresholds=thresholds,
        top_ns=top_ns,
        repo_path=repo,
        stack=stack,
        out_dir=out_dir,
        write=write,
        repo_revision=repo_revision,
        timestamp=timestamp,
    )
