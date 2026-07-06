"""spec 0026 AC8 — pre-registered pilot-gated power go/no-go.

A frozen, hashed config (`PREREGISTERED_AC8_CONFIG` / `AC8_CONFIG_HASH`), fixed BEFORE
any live pilot so the thresholds cannot be tuned post-hoc (mirrors
`benchmark_fit.PREREGISTERED_CONFIG`). A discordant localization-flip pair is
SIGNAL-BEARING only when the two arms disagree on whether they LOCATED the target
(oracle file/span hit) — an empty↔wrong-file flip is noise (both not-located) and does
not count, guarding exactly the 0023 near-zero-localization failure. The pilot's
signal-bearing rate is projected to full size; below the committed
`MIN_DISCORDANT_PAIRS` floor the set is declared UNDER-POWERED (STOP). Pure, no I/O, no
SUT import beyond the frozen `LocateBucket` oracle.
"""

from __future__ import annotations

import dataclasses
import enum
import hashlib

from harpyja.eval.benchmark_fit import PREREGISTERED_CONFIG
from harpyja.eval.locate_accuracy import LocateBucket

# An arm "located" the target when it produced a correct file-or-span hit.
_LOCATED_BUCKETS = frozenset({LocateBucket.CORRECT, LocateBucket.RIGHT_FILE_WRONG_SPAN})


class Ac8Outcome(enum.Enum):
    PROCEED = "proceed"
    UNDER_POWERED_STOP = "under-powered-stop"

    def next_step(self) -> str:
        if self is Ac8Outcome.UNDER_POWERED_STOP:
            # A STOP is the DESIGNED, valid deliverable at 0023's floor — it names the
            # finder-capability work, never "author a set to rank noise".
            return (
                "finder-capability retrieval work (the 0022/0023 RETRIEVAL_FUNDAMENTAL "
                "line): the terse set cannot rank while Scout localization sits near zero"
            )
        return "author the full ~20-40 case terse set and run the bake-off"


@dataclasses.dataclass(frozen=True)
class Ac8PilotConfig:
    """Pre-registered pilot power-gate config (frozen; hashed before the pilot)."""

    # Two servable loopback-Ollama tool-calling models with a real capability contrast
    # (size) so they actually generate discordant localization flips.
    reference_model_a: str = "hf.co/Qwen/Qwen3-8B-GGUF:latest"
    reference_model_b: str = "qwen3:4b-instruct"
    pilot_n: int = 10
    full_n_target: int = 30
    # STOP threshold REUSES the committed exact-McNemar reachability floor.
    min_discordant_pairs: int = PREREGISTERED_CONFIG.MIN_DISCORDANT_PAIRS


PREREGISTERED_AC8_CONFIG = Ac8PilotConfig()


def config_hash(cfg: Ac8PilotConfig) -> str:
    payload = "|".join(f"{k}={v}" for k, v in sorted(dataclasses.asdict(cfg).items()))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


AC8_CONFIG_HASH = config_hash(PREREGISTERED_AC8_CONFIG)


@dataclasses.dataclass(frozen=True)
class PilotPair:
    """One within-case pilot pair: the same gold target scored on arm A vs arm B."""

    case_id: str
    bucket_a: LocateBucket
    bucket_b: LocateBucket


def _located(bucket: LocateBucket) -> bool:
    return bucket in _LOCATED_BUCKETS


def is_signal_discordant(pair: PilotPair) -> bool:
    """The arms DISAGREE on whether they located the target (one hit, one missed).
    Two not-located arms (empty↔wrong-file) are concordant NOISE, not a flip."""
    return _located(pair.bucket_a) != _located(pair.bucket_b)


def signal_bearing_discordant(pairs: list[PilotPair]) -> int:
    return sum(1 for p in pairs if is_signal_discordant(p))


def project_flips(
    signal_discordant: int,
    pilot_pairs_run: int,
    cfg: Ac8PilotConfig = PREREGISTERED_AC8_CONFIG,
) -> int:
    """Extrapolate the pilot's signal-bearing discordant RATE to the full-size flip
    count: round((signal / pilot) * full_n_target). Zero pilot pairs → 0 (no data)."""
    if pilot_pairs_run <= 0:
        return 0
    return round((signal_discordant / pilot_pairs_run) * cfg.full_n_target)


def decide_ac8(
    signal_discordant: int,
    pilot_pairs_run: int,
    cfg: Ac8PilotConfig = PREREGISTERED_AC8_CONFIG,
) -> Ac8Outcome:
    """Total pure verdict: PROCEED iff the projected full-size flips reach the floor,
    else UNDER_POWERED_STOP. Never raises, never silently defaults."""
    projected = project_flips(signal_discordant, pilot_pairs_run, cfg)
    if projected >= cfg.min_discordant_pairs:
        return Ac8Outcome.PROCEED
    return Ac8Outcome.UNDER_POWERED_STOP


def decide_from_pairs(
    pairs: list[PilotPair], cfg: Ac8PilotConfig = PREREGISTERED_AC8_CONFIG
) -> Ac8Outcome:
    return decide_ac8(signal_bearing_discordant(pairs), len(pairs), cfg)
