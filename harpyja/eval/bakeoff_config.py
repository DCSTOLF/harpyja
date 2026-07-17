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

    # Spec 0049 (path A) — greedy serving variant tags, re-frozen into THIS config.
    # ``served_variant_tags`` is what the runner actually serves/measures (the base
    # ``model_tags`` above stay the LOGICAL identity, UNTOUCHED); the base tags are
    # deliberately absent here (path A, not the tag-mutating path B).
    served_variant_tags: tuple[str, ...] = (
        "qwen3-14b-greedy",
        "qwen3-8b-greedy",
        "qwen3.5-4b-greedy",
    )
    # Each greedy tag's COMMITTED semantic fingerprint (re-derivable from the
    # committed ``serving/Modelfile.*`` via ``greedy_serving.parse_modelfile_fingerprint``
    # → ``fingerprint_digest``). COMMITTED, so the config hash is a pure function of
    # in-repo data (a live ``ollama show`` read is CONFORMANCE-only, never a hash input).
    served_variant_fingerprints: tuple[tuple[str, str], ...] = (
        (
            "qwen3-14b-greedy",
            "03826a2ef9465419f0292747c13947cab17ab64e75f29d6b56a725beda23e33c",
        ),
        (
            "qwen3-8b-greedy",
            "29b890f3c3f77a779276f5673bb03a3255a8fee14d0e8b723aa96192b62675a6",
        ),
        (
            "qwen3.5-4b-greedy",
            "8c717e0c8aa4fc529d700ed49e379aea27f91e9e9a88065a81b1f84f6424db52",
        ),
    )


# The single measurement-config consumer: map a logical base tag → its served
# greedy variant. This is the ONLY call site that reads ``served_variant_tags``
# (pinned by an ast sweep in the tests) so deployment/unrelated paths never adopt
# the control tags.
_LOGICAL_TO_GREEDY = {
    "qwen3:14b": "qwen3-14b-greedy",
    "qwen3:8b": "qwen3-8b-greedy",
    "qwen3.5:4b": "qwen3.5-4b-greedy",
}


def resolve_served_model(cfg: BakeoffConfig, logical_tag: str) -> str:
    """Resolve a logical base tag to the greedy variant the runner serves."""

    greedy = _LOGICAL_TO_GREEDY.get(logical_tag)
    if greedy is None or greedy not in cfg.served_variant_tags:
        raise KeyError(f"no served greedy variant for logical tag {logical_tag!r}")
    return greedy


PREREGISTERED_BAKEOFF_CONFIG_0048 = BakeoffConfig()


def bakeoff_config_hash(cfg: BakeoffConfig) -> str:
    """sha256 over the frozen fields — the same shape as ``pool_config_hash``."""
    payload = "|".join(f"{k}={v}" for k, v in sorted(dataclasses.asdict(cfg).items()))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


BAKEOFF_CONFIG_HASH_0048 = bakeoff_config_hash(PREREGISTERED_BAKEOFF_CONFIG_0048)

# Spec 0049 — the re-frozen served-config digest (greedy variant tags + committed
# fingerprints flow in via ``sorted(asdict)``). Offline-reproducible; pinned as a
# known-value drift guard in ``test_bakeoff_config_served_variants``.
SERVED_VARIANT_CONFIG_HASH = bakeoff_config_hash(PREREGISTERED_BAKEOFF_CONFIG_0048)
