"""Spec 0048 — bake-off: the FROZEN analysis contract, as a hashed config.

Pre-registers every decision rule that turns per model+case artifacts into a
verdict, committed by hash BEFORE the first live call (the two-stage-freeze
discipline of 0045; "freeze the choosing rule before the numbers", 0044–0046).
Mirrors ``pool_precheck.PoolConfig`` — but 0048 owns its OWN config + hash and
DELIBERATELY diverges from 0040's ``per-pair-alpha-uncorrected`` stance:
this bake-off corrects across the three conceptual pairwise tests with
Holm–Bonferroni, family size ``m = 3`` FIXED (the reconciled-freeze rule — a new
stance, pinned with a rationale, never a silent reuse of the 0040 hash).

The ONLY things reused BY IDENTITY are the absolute discordance floor of 8
(``benchmark_fit.PREREGISTERED_CONFIG.MIN_DISCORDANT_PAIRS``) and — in
``bakeoff_analysis`` — the discordance/located/McNemar oracles. Pure, no I/O, no
SUT import beyond the frozen taxonomy.
"""

from __future__ import annotations

import dataclasses
import hashlib

from harpyja.eval.benchmark_fit import PREREGISTERED_CONFIG

# The 0047 enlarged pool the run iterates (53 raw-clean: conceptual 44 / lexical
# 9). The full content sha256 whose prefix the spec cites as ``385107934f61``.
_POOL_SHA256 = "385107934f6107544c68a48f49d294ec4534616acd2f6e9b30b0bedd754bb7d3"


@dataclasses.dataclass(frozen=True)
class BakeoffConfig:
    """The pre-registered 0048 bake-off analysis contract (frozen; hashed)."""

    # The three model tags (three sizes, two generations) and the three named
    # pairwise contrasts, in the frozen tie-break order.
    model_tags: tuple[str, ...] = ("qwen3:14b", "qwen3:8b", "qwen3.5:4b")
    pairs: tuple[tuple[str, str], ...] = (
        ("qwen3:14b", "qwen3:8b"),
        ("qwen3:14b", "qwen3.5:4b"),
        ("qwen3:8b", "qwen3.5:4b"),
    )

    # Statistics. The discordance floor is an ABSOLUTE count reused BY IDENTITY
    # from the committed exact-McNemar source (never re-derived, never a rate).
    alpha: float = 0.05
    conceptual_min_discordant: int = PREREGISTERED_CONFIG.MIN_DISCORDANT_PAIRS
    floor_derivation: str = "reused-by-identity-from-benchmark-fit"

    # Coverage floor: eligible paired conceptual N must reach 80% of 44.
    conceptual_n: int = 44
    lexical_n: int = 9
    coverage_floor: int = 36
    coverage_derivation: str = "0.8 * 44 = 35.2 -> ceil to 36"

    # A coverage shortfall is PARTITIONED by cause: degrade-dominated when more
    # than this fraction of a pair's dropped cases were degrade-caused (vs
    # honest-empty / preflight-exclusion). A frozen threshold, not a judgement.
    degraded_dominated_threshold: float = 0.5

    # Multiplicity — the DELIBERATE divergence from 0040. Frozen outcome-blind.
    holm_family_size: int = 3
    multiplicity_stance: str = "holm-bonferroni-m3-fixed"
    multiplicity_rationale: str = (
        "the three conceptual pairwise McNemar tests feed one ranking; a fixed "
        "family m=3 (not the number that happen to reach the test) is the "
        "anti-steering guard — a data-dependent family size would let coverage "
        "outcomes loosen the surviving tests. Diverges from 0040's per-pair-"
        "uncorrected stance, which answered three standalone questions."
    )

    # Decoding determinism — greedy, verified by a reproducibility replay probe
    # at preflight (a batched local backend is not guaranteed bit-reproducible
    # at temperature 0). Stamped into every durable artifact.
    temperature: float = 0.0
    top_p: float = 1.0
    seed: int = 0

    # Arms parity: no thinking confound (that is 0039's question).
    explorer_think: bool | None = None

    # Provenance: the 0047 pool the run reads; recorded per artifact so the
    # powered claim is auditable and the no-train-on-test attestation holds.
    pool_sha256: str = _POOL_SHA256

    # OQ1 staging — pre-declared, operational-only, never chosen after results.
    staging_order: str = (
        "preflight-all-3-then-run-widest-gap-pair-14b-4b-first-then-full-grid"
    )


PREREGISTERED_BAKEOFF_CONFIG_0048 = BakeoffConfig()


def bakeoff_config_hash(cfg: BakeoffConfig) -> str:
    """sha256 over the frozen fields — the same shape as ``pool_config_hash``."""
    payload = "|".join(f"{k}={v}" for k, v in sorted(dataclasses.asdict(cfg).items()))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


BAKEOFF_CONFIG_HASH_0048 = bakeoff_config_hash(PREREGISTERED_BAKEOFF_CONFIG_0048)
