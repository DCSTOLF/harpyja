"""Spec 0039 — AC5: the cheap gate before the expensive run (0026 pilot-gate
discipline applied to the thinking A/B).

THE POWER ARITHMETIC, OUT LOUD: the conceptual stratum is N=15 and the frozen
floor is 8 signal-bearing discordant pairs. The committed 0036 pilot covered
only the FIRST 10 of 19 cases, of which 7 are conceptual; the pinned arm
(``qwen3:14b``) located 3 of those 7. Projecting that rate to the full stratum
and assuming EVERY located case flips between arms gives round(15 * 3/7) = 6 —
below the floor of 8 before any realism discount. A same-model think-on/off
contrast flips far FEWER than every located case, so the true expectation is
lower still.

The projection is an UPPER-BOUND FEASIBILITY CHECK, not a power estimate: the
pilot measured cross-MODEL discordance (qwen3:14b vs qwen3:4b-instruct), which
BOUNDS but cannot estimate within-model think-flip rates. When even the upper
bound cannot reach the floor, the typed ``UNDER_POWERED_STOP`` is the run's
honest deliverable — discovered for free, not after ~4h of paired wall-clock —
and the named next step is the 0036 pool-enlargement audited convert step.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any

from harpyja.eval.locate_accuracy import LocateBucket
from harpyja.eval.think_ab import (
    PRECHECK_STOP,
    PREREGISTERED_AB_CONFIG_0039,
    AbConfig,
    located_via_oracle,
)

PRECHECK_PROJECTION_KIND = "upper-bound-feasibility"

_POOL_ENLARGEMENT_NEXT_STEP = (
    "enlarge the blind-clean pool first — the named 0036 pool-enlargement "
    "audited convert step (the 50-case raw pool is exhausted at 19 blind-clean); "
    "the conceptual stratum cannot reach the committed floor at N=15"
)


class PrecheckError(ValueError):
    """Committed pre-check evidence that does not conform — loud, never defaulted."""


@dataclasses.dataclass(frozen=True)
class PrecheckOutcome:
    """The typed pre-check outcome (total: proceed | under-powered-stop)."""

    outcome: str
    projection_kind: str
    piloted_conceptual_n: int
    located_conceptual: int
    full_conceptual_n: int
    projected_upper_bound: int
    floor: int
    degrade_warning: str | None
    next_step: str


def project_conceptual_upper_bound(
    located: int, piloted_n: int, full_n: int
) -> int:
    """round(rate * full_n): every located case assumed to flip — the generous
    ceiling a same-model contrast cannot exceed."""
    if piloted_n <= 0:
        return 0
    return round((located / piloted_n) * full_n)


def ab_power_precheck(
    ledger: dict[str, Any],
    reachability: dict[str, str],
    cfg: AbConfig = PREREGISTERED_AB_CONFIG_0039,
    *,
    full_conceptual_n: int,
    on_arm_truncation_fraction: float | None = None,
) -> PrecheckOutcome:
    """Pure core: project the conceptual-stratum signal-bearing ceiling from the
    pilot ledger's pinned-arm buckets; typed stop when the ceiling is under the
    frozen floor. Also projects the on-arm truncation risk (a predictable
    CONFOUNDED is as discoverable-for-free as a predictable UNDER_POWERED)."""
    suffix = f"::{cfg.lm_model}"
    piloted = 0
    located = 0
    for key, entry in ledger.get("entries", {}).items():
        if not key.endswith(suffix):
            continue
        case_id = key[: -len(suffix)]
        if reachability.get(case_id) != "conceptual":
            continue
        piloted += 1
        if located_via_oracle(LocateBucket(entry["bucket"])):
            located += 1

    projected = project_conceptual_upper_bound(located, piloted, full_conceptual_n)
    floor = cfg.conceptual_min_discordant

    if on_arm_truncation_fraction is None:
        degrade_warning = (
            "per-turn artifacts unavailable; on-arm truncation risk unprojected "
            "(0038 observed 850-3980 reasoning chars/turn against "
            "explorer_max_tokens=2048)"
        )
    elif on_arm_truncation_fraction > cfg.degrade_asymmetry_threshold:
        degrade_warning = (
            f"projected on-arm truncation fraction "
            f"{on_arm_truncation_fraction:.2f} exceeds the frozen "
            f"degrade-asymmetry threshold {cfg.degrade_asymmetry_threshold} — "
            f"a predictable CONFOUNDED; the reasoning tax against "
            f"explorer_max_tokens=2048 is a live risk"
        )
    else:
        degrade_warning = None

    if projected >= floor:
        outcome, next_step = "proceed", "run the paired A/B via the committed driver"
    else:
        outcome, next_step = PRECHECK_STOP, _POOL_ENLARGEMENT_NEXT_STEP

    return PrecheckOutcome(
        outcome=outcome,
        projection_kind=PRECHECK_PROJECTION_KIND,
        piloted_conceptual_n=piloted,
        located_conceptual=located,
        full_conceptual_n=full_conceptual_n,
        projected_upper_bound=projected,
        floor=floor,
        degrade_warning=degrade_warning,
        next_step=next_step,
    )


# ---- committed-evidence loaders (archive-first, the 79f7bf2 convention) ------


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def committed_pilot_ledger_path() -> Path:
    """The committed 0036 pilot ledger — specs/.archive first, live fallback."""
    root = _repo_root()
    archived = (
        root / "specs" / ".archive" / "0036-terse-query" / "pilot" / "pilot_results.json"
    )
    live = root / "specs" / "0036-terse-query" / "pilot" / "pilot_results.json"
    return archived if archived.is_file() else live


def load_committed_pilot_ledger() -> dict[str, Any]:
    path = committed_pilot_ledger_path()
    if not path.is_file():
        raise PrecheckError(f"committed 0036 pilot ledger not found: {path}")
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict) or "entries" not in obj or "config_hash" not in obj:
        raise PrecheckError("pilot ledger missing 'entries'/'config_hash'")
    return obj


def load_fixture_reachability() -> dict[str, str]:
    """case_id → reachability from the committed 0036 terse fixture."""
    path = _repo_root() / "harpyja" / "eval" / "fixtures" / "swebench_verified.terse.jsonl"
    if not path.is_file():
        raise PrecheckError(f"committed terse fixture not found: {path}")
    tags: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        reachability = row.get("reachability")
        if not reachability:
            raise PrecheckError(
                f"case {row.get('case_id')!r} carries no reachability tag"
            )
        tags[row["case_id"]] = reachability
    return tags


def run_precheck(cfg: AbConfig = PREREGISTERED_AB_CONFIG_0039) -> PrecheckOutcome:
    """The committed-evidence pre-check: 0036 pilot ledger x fixture tags."""
    ledger = load_committed_pilot_ledger()
    reachability = load_fixture_reachability()
    full_conceptual_n = sum(1 for tag in reachability.values() if tag == "conceptual")
    return ab_power_precheck(
        ledger, reachability, cfg, full_conceptual_n=full_conceptual_n
    )
