"""Spec 0048 — bake-off: the FROZEN 0048 config drift guards (T1).

Every verdict-shaping literal is pinned here so it cannot drift silently; the
config is committed (hash-stable) before any live call. Mirrors the
`pool_precheck` frozen-config discipline, but 0048 owns its OWN config + hash and
DELIBERATELY diverges from 0040's multiplicity stance (Holm–Bonferroni m=3 fixed,
not per-pair-uncorrected).
"""

from __future__ import annotations

from harpyja.eval.bakeoff_config import (
    BAKEOFF_CONFIG_HASH_0048,
    PREREGISTERED_BAKEOFF_CONFIG_0048,
    BakeoffConfig,
    bakeoff_config_hash,
)
from harpyja.eval.benchmark_fit import PREREGISTERED_CONFIG
from harpyja.eval.pool_precheck import PREREGISTERED_POOL_CONFIG_0040

_CFG = PREREGISTERED_BAKEOFF_CONFIG_0048
_FULL_POOL_SHA = "385107934f6107544c68a48f49d294ec4534616acd2f6e9b30b0bedd754bb7d3"


def test_bakeoff_config_pins_three_tags_and_three_pairs():
    assert _CFG.model_tags == ("qwen3:14b", "qwen3:8b", "qwen3.5:4b")
    assert _CFG.pairs == (
        ("qwen3:14b", "qwen3:8b"),
        ("qwen3:14b", "qwen3.5:4b"),
        ("qwen3:8b", "qwen3.5:4b"),
    )


def test_bakeoff_config_pins_absolute_floors_and_thresholds():
    # The floor is REUSED by identity from the committed exact-McNemar source.
    assert _CFG.conceptual_min_discordant == 8
    assert _CFG.conceptual_min_discordant == PREREGISTERED_CONFIG.MIN_DISCORDANT_PAIRS
    assert _CFG.coverage_floor == 36
    assert _CFG.degraded_dominated_threshold == 0.5
    assert _CFG.holm_family_size == 3
    assert _CFG.alpha == 0.05
    assert _CFG.conceptual_n == 44
    assert _CFG.lexical_n == 9


def test_bakeoff_config_pins_decoding_and_pool_provenance():
    assert _CFG.temperature == 0.0
    assert _CFG.top_p == 1.0
    assert isinstance(_CFG.seed, int)
    assert _CFG.pool_sha256 == _FULL_POOL_SHA
    # Arms-parity: no thinking confound in this bake-off (that is 0039's run).
    assert _CFG.explorer_think is None


def test_bakeoff_config_multiplicity_diverges_from_0040_holm_m3():
    assert _CFG.multiplicity_stance == "holm-bonferroni-m3-fixed"
    # The deliberate divergence: NOT 0040's per-pair-uncorrected stance.
    assert (
        _CFG.multiplicity_stance
        != PREREGISTERED_POOL_CONFIG_0040.multiplicity_stance
    )
    assert _CFG.multiplicity_rationale  # a non-empty rationale is present


def test_bakeoff_config_hash_is_stable():
    assert BAKEOFF_CONFIG_HASH_0048 == bakeoff_config_hash(_CFG)
    assert len(BAKEOFF_CONFIG_HASH_0048) == 64
    # A field change must change the hash (drift guard is real, not trivial).
    import dataclasses

    mutated = dataclasses.replace(_CFG, coverage_floor=35)
    assert bakeoff_config_hash(mutated) != BAKEOFF_CONFIG_HASH_0048


def test_bakeoff_config_is_frozen():
    import dataclasses

    assert isinstance(_CFG, BakeoffConfig)
    with __import__("pytest").raises(dataclasses.FrozenInstanceError):
        _CFG.coverage_floor = 1  # type: ignore[misc]
