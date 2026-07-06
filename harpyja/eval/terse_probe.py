"""spec 0026 AC6/AC8 — drive the terse set through the REAL explorer backend (offline).

Thin harness: it loads the joined terse set and delegates to the UNCHANGED
`run_locate_probe` (no forked scoring, no SUT edit); file-level + span-level scores come
from the existing `score_distribution` oracle. AC8 runs the pre-registered pilot through
two reference models (a per-arm `Settings.lm_model` override, `dataclasses.replace`,
never mutation) and emits the typed go/no-go outcome + the frozen config hash.

Per-case provisioning (raw `base_commit` → worktree) is injected as `provision`, so this
module never itself clones or mutates a repo — the harness stays read-only on targets.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable

from harpyja.eval.ac8_pilot import (
    AC8_CONFIG_HASH,
    PREREGISTERED_AC8_CONFIG,
    Ac8Outcome,
    Ac8PilotConfig,
    PilotPair,
    decide_from_pairs,
    signal_bearing_discordant,
)
from harpyja.eval.dataset import EvalCase
from harpyja.eval.locate_accuracy import (
    LocateBucket,
    LocateDistribution,
    SubFlags,
    score_distribution,
)
from harpyja.eval.locate_probe import build_scout_only_stack, run_locate_probe
from harpyja.eval.terse_dataset import load_terse_dataset

# provision(case_id, base_commit) -> worktree path (or None if unprovisioned).
Provision = Callable[[str, str], "str | None"]

_WINDOW = 50


@dataclasses.dataclass(frozen=True)
class TerseProbeResult:
    distribution: LocateDistribution
    n_scored: int
    excluded_count: int


@dataclasses.dataclass(frozen=True)
class Ac8PilotRunResult:
    outcome: Ac8Outcome
    signal_discordant: int
    pilot_pairs: int
    config_hash: str
    reference_models: tuple[str, str]


def _case_rows(case: EvalCase, repo_path: str, settings, window: int):
    stack = build_scout_only_stack(settings, repo_path)
    return run_locate_probe([case], stack=stack, repo_path=repo_path, window=window).rows


def run_terse_locate_probe(
    terse_path,
    raw_path,
    provenance_path,
    *,
    settings,
    provision: Provision,
    window: int = _WINDOW,
) -> TerseProbeResult:
    """AC6: score the terse set through the explorer via the existing oracle."""
    ds = load_terse_dataset(terse_path, raw_path, provenance_path)
    classified = []
    scored = 0
    for case in ds.cases:
        meta = ds.join_meta[case.case_id]
        repo_path = provision(case.case_id, meta.base_commit)
        if not repo_path:
            continue
        for r in _case_rows(case, repo_path, settings, window):
            # score_distribution ignores flags; the bucket + dropped carry the score.
            classified.append((r.bucket, SubFlags(), r.normalization_dropped))
            scored += 1
    return TerseProbeResult(
        distribution=score_distribution(classified),  # ONE oracle, reused
        n_scored=scored,
        excluded_count=ds.excluded_count,
    )


def _arm_bucket(case: EvalCase, repo_path: str, settings, model: str, window: int) -> LocateBucket:
    arm_settings = dataclasses.replace(settings, lm_model=model)
    rows = _case_rows(case, repo_path, arm_settings, window)
    return rows[0].bucket if rows else LocateBucket.EMPTY


def run_ac8_pilot(
    terse_path,
    raw_path,
    provenance_path,
    *,
    settings,
    provision: Provision,
    cfg: Ac8PilotConfig = PREREGISTERED_AC8_CONFIG,
    window: int = _WINDOW,
) -> Ac8PilotRunResult:
    """AC8: run the pre-registered pilot through the two reference models (same case,
    both arms) and emit the typed under-powered/proceed verdict."""
    ds = load_terse_dataset(terse_path, raw_path, provenance_path)
    pairs: list[PilotPair] = []
    for case in ds.cases[: cfg.pilot_n]:
        meta = ds.join_meta[case.case_id]
        repo_path = provision(case.case_id, meta.base_commit)
        if not repo_path:
            continue
        a = _arm_bucket(case, repo_path, settings, cfg.reference_model_a, window)
        b = _arm_bucket(case, repo_path, settings, cfg.reference_model_b, window)
        pairs.append(PilotPair(case_id=case.case_id, bucket_a=a, bucket_b=b))
    return Ac8PilotRunResult(
        outcome=decide_from_pairs(pairs, cfg),
        signal_discordant=signal_bearing_discordant(pairs),
        pilot_pairs=len(pairs),
        config_hash=AC8_CONFIG_HASH,
        reference_models=(cfg.reference_model_a, cfg.reference_model_b),
    )
