"""Spec 0049 (AC3) — the positive ``/api/tags`` membership guard over the greedy
variant tags (offline unit; the live gated form is in test_greedy_serving_live).

Reuses the 0048 ``probe_served_membership`` machinery but keyed on
``served_variant_tags`` (NOT ``model_tags``): ``assert_local`` FIRST, then a
positive per-tag membership that CANNOT pass trivially when the endpoint is down.
"""

from __future__ import annotations

from harpyja.eval.bakeoff_config import BakeoffConfig
from harpyja.eval.bakeoff_run import probe_served_variant_membership

_CFG = BakeoffConfig()


def test_probe_served_variant_membership_iterates_variant_tags_not_model_tags():
    # Served set contains ONLY the greedy variants (not the base model_tags).
    served = list(_CFG.served_variant_tags)
    result = probe_served_variant_membership(
        _CFG,
        api_base="http://127.0.0.1:11434",
        assert_local_fn=lambda _: None,
        tags_reader=lambda _: served,
    )
    assert set(result) == set(_CFG.served_variant_tags)
    assert all(result.values())
    # The base logical tags are NOT what this probe checks.
    assert set(result).isdisjoint(_CFG.model_tags)


def test_probe_served_variant_membership_asserts_local_first():
    calls: list[str] = []
    probe_served_variant_membership(
        _CFG,
        api_base="http://127.0.0.1:11434",
        assert_local_fn=lambda base: calls.append(f"assert_local:{base}"),
        tags_reader=lambda base: (calls.append(f"read:{base}") or []),
    )
    assert calls[0].startswith("assert_local:")
    assert any(c.startswith("read:") for c in calls)
    assert calls.index("assert_local:http://127.0.0.1:11434") < next(
        i for i, c in enumerate(calls) if c.startswith("read:")
    )


def test_probe_served_variant_membership_empty_served_set_all_false():
    # A down endpoint yields an empty served set → every greedy tag False; the
    # guard cannot pass trivially.
    result = probe_served_variant_membership(
        _CFG,
        api_base="http://127.0.0.1:11434",
        assert_local_fn=lambda _: None,
        tags_reader=lambda _: [],
    )
    assert set(result) == set(_CFG.served_variant_tags)
    assert not any(result.values())
