"""spec 0026 AC8 — pre-registered, frozen+hashed pilot power gate. A discordant pair
counts only when it is signal-bearing (≥1 arm a correct localization); an
empty↔wrong-file flip is noise. STOP when the projected flips fall below the committed
MIN_DISCORDANT_PAIRS floor."""

from __future__ import annotations

import dataclasses

import pytest

from harpyja.eval.ac8_pilot import (
    AC8_CONFIG_HASH,
    PREREGISTERED_AC8_CONFIG,
    Ac8Outcome,
    PilotPair,
    config_hash,
    decide_ac8,
    project_flips,
    signal_bearing_discordant,
)
from harpyja.eval.benchmark_fit import PREREGISTERED_CONFIG
from harpyja.eval.locate_accuracy import LocateBucket


def test_preregistered_ac8_config_is_frozen_and_hashed():
    cfg = PREREGISTERED_AC8_CONFIG
    assert cfg.pilot_n == 10
    assert cfg.full_n_target == 30
    assert cfg.reference_model_a and cfg.reference_model_b
    assert cfg.reference_model_a != cfg.reference_model_b  # a capability contrast
    # STOP threshold reuses the committed exact-McNemar floor, not a new guess.
    assert cfg.min_discordant_pairs == PREREGISTERED_CONFIG.MIN_DISCORDANT_PAIRS == 8
    # frozen
    with pytest.raises(dataclasses.FrozenInstanceError):
        cfg.pilot_n = 5  # type: ignore[misc]
    # stable hash
    assert AC8_CONFIG_HASH == config_hash(cfg)
    assert isinstance(AC8_CONFIG_HASH, str) and len(AC8_CONFIG_HASH) == 64


def test_preregistered_0036_config_is_frozen_hashed_and_servable():
    # spec 0036: the frozen 0026 arm A (hf.co/Qwen/Qwen3-8B-GGUF:latest) is not
    # servable on the live stack, so the pilot runs under a NEW pre-registered
    # frozen+hashed config — arms swapped to servable models with a real capability
    # contrast, EVERY threshold copied verbatim, its own hash, committed before the
    # pilot fires (the freeze predates the data).
    from harpyja.eval.ac8_pilot import AC8_CONFIG_HASH_0036, PREREGISTERED_AC8_CONFIG_0036

    cfg = PREREGISTERED_AC8_CONFIG_0036
    assert cfg.reference_model_a == "qwen3:14b"
    assert cfg.reference_model_b == "qwen3:4b-instruct"
    assert cfg.reference_model_a != cfg.reference_model_b  # a capability contrast
    # thresholds copied verbatim from the 0026 freeze — only the arms differ.
    base = PREREGISTERED_AC8_CONFIG
    assert cfg.pilot_n == base.pilot_n == 10
    assert cfg.full_n_target == base.full_n_target == 30
    assert cfg.min_discordant_pairs == base.min_discordant_pairs == 8
    # frozen, with its OWN stable hash (distinct from the 0026 hash).
    with pytest.raises(dataclasses.FrozenInstanceError):
        cfg.pilot_n = 5  # type: ignore[misc]
    assert AC8_CONFIG_HASH_0036 == config_hash(cfg)
    assert isinstance(AC8_CONFIG_HASH_0036, str) and len(AC8_CONFIG_HASH_0036) == 64
    assert AC8_CONFIG_HASH_0036 != AC8_CONFIG_HASH


def _pair(a: LocateBucket, b: LocateBucket) -> PilotPair:
    return PilotPair(case_id="c", bucket_a=a, bucket_b=b)


def test_signal_bearing_discordant_excludes_empty_wrong_file_noise():
    pairs = [
        _pair(LocateBucket.EMPTY, LocateBucket.WRONG_FILE),  # noise flip — excluded
        _pair(LocateBucket.WRONG_FILE, LocateBucket.EMPTY),  # noise flip — excluded
        _pair(LocateBucket.CORRECT, LocateBucket.EMPTY),  # signal — counted
        _pair(LocateBucket.RIGHT_FILE_WRONG_SPAN, LocateBucket.WRONG_FILE),  # signal
        _pair(LocateBucket.CORRECT, LocateBucket.CORRECT),  # concordant — not counted
    ]
    assert signal_bearing_discordant(pairs) == 2


def test_project_flips_and_stop_threshold():
    # 3 signal flips / 10 pilot → 9 projected ≥ 8 → PROCEED
    assert project_flips(3, 10) == 9
    assert decide_ac8(3, 10) is Ac8Outcome.PROCEED
    # 2 / 10 → 6 < 8 → STOP
    assert project_flips(2, 10) == 6
    assert decide_ac8(2, 10) is Ac8Outcome.UNDER_POWERED_STOP


def test_ac8_outcome_is_total_pure_function():
    # total over the pilot grid: every input returns a member, never raises/defaults.
    for sig in range(0, 11):
        out = decide_ac8(sig, 10)
        assert isinstance(out, Ac8Outcome)
    # a zero-pilot (no data) is a STOP, not a crash.
    assert decide_ac8(0, 0) is Ac8Outcome.UNDER_POWERED_STOP
    # STOP names the finder-capability next step.
    assert "finder" in Ac8Outcome.UNDER_POWERED_STOP.next_step().lower()


def test_ac8_uses_same_oracle_buckets_as_locate_accuracy():
    # One-oracle reuse (convention): AC8's "located" predicate must be exactly the
    # buckets locate_accuracy credits at file level (CORRECT + RIGHT_FILE_WRONG_SPAN),
    # so the pilot's flip signal cannot drift from the scoring oracle.
    from harpyja.eval import ac8_pilot

    assert ac8_pilot._LOCATED_BUCKETS == frozenset(
        {LocateBucket.CORRECT, LocateBucket.RIGHT_FILE_WRONG_SPAN}
    )
    # a signal-discordant pair, by construction, has exactly one located arm.
    p = PilotPair(case_id="c", bucket_a=LocateBucket.CORRECT, bucket_b=LocateBucket.EMPTY)
    assert ac8_pilot.is_signal_discordant(p)
    q = PilotPair(
        case_id="c", bucket_a=LocateBucket.EMPTY, bucket_b=LocateBucket.WRONG_FILE
    )
    assert not ac8_pilot.is_signal_discordant(q)
