"""Spec 0040 — the committed per-model preflight-result contract (typed
outcomes + loud validator + archive-first loader, the 0037/0038 pattern)."""

from __future__ import annotations

import json

import pytest

from harpyja.eval.pool_preflight_result import (
    POOL_PREFLIGHT_SCHEMA_VERSION,
    PoolPreflightError,
    load_pool_preflight_result,
    validate_pool_preflight_result,
)

_MODELS = ("qwen3:14b", "qwen3:8b", "qwen3.5:4b")


def _valid_result() -> dict:
    return {
        "schema_version": POOL_PREFLIGHT_SCHEMA_VERSION,
        "endpoint": "http://127.0.0.1:11434/v1",
        "config_hash": "a" * 64,
        "models": {
            "qwen3:14b": {
                "outcome": "preflight-pass",
                "served": True,
                "coherent": True,
                "tool_calls_clean": True,
                "think_control": "effective",
                "think_control_mechanism": "reasoning-effort",
                "exclusion_reason": None,
            },
            "qwen3:8b": {
                "outcome": "think-control-noop",
                "served": True,
                "coherent": True,
                "tool_calls_clean": True,
                "think_control": "noop",
                "think_control_mechanism": None,
                "exclusion_reason": None,
            },
            "qwen3.5:4b": {
                "outcome": "coherence-fail",
                "served": True,
                "coherent": False,
                "tool_calls_clean": False,
                "think_control": "indeterminate",
                "think_control_mechanism": None,
                "exclusion_reason": "gibberish on known-localizable case",
            },
        },
    }


def test_validate_pool_preflight_result_rejects_unknown_schema():
    obj = _valid_result()
    obj["schema_version"] = "9999/1"
    with pytest.raises(PoolPreflightError, match="schema_version"):
        validate_pool_preflight_result(obj)


def test_validate_requires_all_three_models_each_typed():
    obj = _valid_result()
    del obj["models"]["qwen3:8b"]
    with pytest.raises(PoolPreflightError, match="exactly the three"):
        validate_pool_preflight_result(obj)
    # An EXCLUDING outcome must carry its recorded reason — never silent.
    obj = _valid_result()
    obj["models"]["qwen3.5:4b"]["exclusion_reason"] = None
    with pytest.raises(PoolPreflightError, match="exclusion_reason"):
        validate_pool_preflight_result(obj)
    # A non-excluding outcome must NOT carry one (the asymmetry, recorded).
    obj = _valid_result()
    obj["models"]["qwen3:8b"]["exclusion_reason"] = "spurious"
    with pytest.raises(PoolPreflightError, match="non-excluding"):
        validate_pool_preflight_result(obj)


def test_outcome_must_be_in_committed_preflight_enum():
    obj = _valid_result()
    obj["models"]["qwen3:14b"]["outcome"] = "kinda-ok"
    with pytest.raises(PoolPreflightError, match="typed outcome"):
        validate_pool_preflight_result(obj)


def test_load_pool_preflight_result_reads_and_validates(tmp_path):
    path = tmp_path / "preflight_result.json"
    path.write_text(json.dumps(_valid_result()), encoding="utf-8")
    obj = load_pool_preflight_result(path)
    assert obj["models"]["qwen3:14b"]["outcome"] == "preflight-pass"
    with pytest.raises(PoolPreflightError, match="not found"):
        load_pool_preflight_result(tmp_path / "missing.json")


def test_committed_preflight_result_pins_three_models():
    # The drift pin on the COMMITTED live artifact: it validates under the
    # loud contract, carries exactly the three pinned tags, and cites the
    # frozen 0040 config hash — the claim cannot exist without the recorded
    # evidence backing it.
    from harpyja.eval.pool_precheck import POOL_CONFIG_HASH_0040
    from harpyja.eval.pool_preflight_result import (
        committed_pool_preflight_path,
        load_committed_pool_preflight_result,
    )

    if not committed_pool_preflight_path().is_file():
        pytest.skip("committed preflight artifact not yet produced (pre-live)")
    obj = load_committed_pool_preflight_result()
    assert set(obj["models"]) == set(_MODELS)
    assert obj["config_hash"] == POOL_CONFIG_HASH_0040
    # The committed 0040 run's recorded finding: all three tags served this
    # harness build and honored reasoning_effort (OQ1 answered live).
    for tag in _MODELS:
        assert obj["models"][tag]["outcome"] == "preflight-pass"
        assert obj["models"][tag]["think_control_mechanism"] == "reasoning-effort"


def test_load_committed_pool_preflight_result_archive_first():
    # The canonical location is specs/.archive/0040-pool/... (pins target the
    # archived path from authoring — the 79f7bf2 convention); the live spec
    # dir is the explicit fallback while unarchived.
    from harpyja.eval import pool_preflight_result as mod

    root = mod._repo_root()
    archived = (
        root / "specs" / ".archive" / "0040-pool" / "preflight"
        / "preflight_result.json"
    )
    live = root / "specs" / "0040-pool" / "preflight" / "preflight_result.json"
    assert mod.committed_pool_preflight_path() == (
        archived if archived.is_file() else live
    )
