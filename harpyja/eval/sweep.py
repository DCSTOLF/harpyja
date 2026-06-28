"""OQ2 sweep (AC6, AC8).

Runs the case set across a grid of `verify_threshold` × `verify_top_n`, K runs per
point. Each grid point is built with `dataclasses.replace` on the base `Settings`
(never mutation — `test_sweep_does_not_mutate_settings`), so the only SUT
interaction is overriding the two real gate fields. Per-point metrics are reduced
to `{mean, spread}` over the K runs, and `recommend.rank_sweep` selects the
recommended point under the D3 variance gate + D4 lexicographic scorer.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from itertools import product

from harpyja.config.settings import Settings
from harpyja.eval.config import EvalConfig, aggregate_runs
from harpyja.eval.dataset import EvalCase
from harpyja.eval.recommend import SweepPoint, rank_sweep
from harpyja.eval.report import SCHEMA_VERSION, atomic_write_json
from harpyja.eval.runner import LocateStack, run_dataset

# Aggregate metrics wrapped as {mean, spread} in the per-point sweep block.
_WRAPPED_METRICS = (
    "span_hit_rate_primary",
    "span_hit_rate_secondary",
    "escalation_rate",
    "tier01_resolve_rate",
    "gate_catch_rate",
    "gate_false_escalation",
)


def _mean_or_none(values: Sequence[float | None]) -> float | None:
    present = [v for v in values if v is not None]
    if not present:
        return None
    return sum(present) / len(present)


def run_sweep(
    *,
    cases: Sequence[EvalCase],
    base_settings: Settings,
    eval_config: EvalConfig,
    thresholds: Sequence[float],
    top_ns: Sequence[int],
    repo_path: str,
    stack: LocateStack,
    out_dir=None,
    write: bool = False,
    repo_revision: str = "unknown",
    timestamp: str = "1970-01-01T00:00:00Z",
) -> dict:
    sweep_points: list[dict] = []
    rank_inputs: list[SweepPoint] = []

    for thr, top_n in product(thresholds, top_ns):
        point_settings = replace(base_settings, verify_threshold=thr, verify_top_n=top_n)

        # K runs at this grid point; collect each run's aggregate.
        per_run: list[dict] = [
            run_dataset(
                cases, point_settings, eval_config,
                repo_path=repo_path, stack=stack, write=False,
                repo_revision=repo_revision, timestamp=timestamp, mode="auto",
            )["aggregate"]
            for _ in range(eval_config.k_runs)
        ]

        wrapped: dict[str, dict] = {}
        for metric in _WRAPPED_METRICS:
            values = [agg[metric] for agg in per_run]
            present = [v for v in values if v is not None]
            wrapped[metric] = aggregate_runs(present)

        catch_runs = [agg["gate_catch_rate"] for agg in per_run]
        false_runs = [agg["gate_false_escalation"] for agg in per_run]
        false_present = tuple(v for v in false_runs if v is not None)

        sweep_points.append({
            "verify_threshold": thr,
            "verify_top_n": top_n,
            "aggregate": wrapped,
        })
        rank_inputs.append(SweepPoint(
            verify_threshold=thr,
            verify_top_n=top_n,
            catch_rate_mean=_mean_or_none(catch_runs),
            false_escalation_mean=(_mean_or_none(false_runs) or 0.0),
            false_escalation_runs=false_present,
        ))

    rec = rank_sweep(rank_inputs, eval_config)
    seed_n = len(cases)
    report = {
        "schema_version": SCHEMA_VERSION,
        "run_metadata": {
            "repo_revision": repo_revision,
            "seed_n": seed_n,
            "n_floor": eval_config.n_floor,
            "indicative_only": seed_n < eval_config.n_floor,
            "mode": "sweep-auto",
            "k_runs": eval_config.k_runs,
            "settings_snapshot": {
                "verify_method": base_settings.verify_method,
                "verify_threshold": base_settings.verify_threshold,
                "verify_top_n": base_settings.verify_top_n,
            },
            "timestamp": timestamp,
            "artifact_dir": str(out_dir) if out_dir is not None else None,
        },
        "sweep": sweep_points,
        "recommendation": {
            "verify_threshold": rec.verify_threshold,
            "verify_top_n": rec.verify_top_n,
            "catch_rate_bar": rec.catch_rate_bar,
            "advantage_exceeds_variance": rec.advantage_exceeds_variance,
            "incumbent_validated": rec.incumbent_validated,
            "rationale": rec.rationale,
        },
    }

    if write:
        if out_dir is None:
            raise ValueError("write=True requires out_dir")
        atomic_write_json(report, out_dir=out_dir, repo_path=repo_path, filename="sweep.json")
    return report
