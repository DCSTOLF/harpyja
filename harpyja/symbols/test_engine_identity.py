"""Tests for engine_identity — the symbol-cache key (AC8d, AC15).

The identity binds a `symbols.jsonl` generation to the exact tree-sitter runtime
+ grammar versions that produced it, so a grammar bump invalidates the cache. An
absent or load-failed grammar records a *stable sentinel* (never an empty slot)
so a degraded run still writes a reproducible sidecar.
"""

from __future__ import annotations

import pytest

from harpyja.symbols.engine_identity import (
    _GRAMMAR_SLOTS,
    SCHEMA_VERSION,
    GrammarLoadError,
    GrammarMissing,
    engine_identity,
)


def _probe(table):
    """Build a probe seam from a {key: version-or-exception} table.

    Unlisted slots resolve to a stable filler version, so a test that cares only
    about a couple of slots need not enumerate all ten.
    """

    def probe(key: str) -> str:
        val = table.get(key, "0.0.0")
        if isinstance(val, BaseException):
            raise val
        return val

    return probe


def test_engine_identity_includes_runtime_and_each_grammar_version():
    probe = _probe(
        {
            "tree-sitter": "0.25.2",
            "tree-sitter-python": "0.25.0",
            "tree-sitter-go": "0.25.0",
        }
    )
    ident = engine_identity(probe=probe)
    assert ident["tree-sitter"] == "0.25.2"
    assert ident["tree-sitter-python"] == "0.25.0"
    assert ident["tree-sitter-go"] == "0.25.0"


def test_engine_identity_absent_grammar_records_missing_sentinel():
    probe = _probe(
        {
            "tree-sitter": "0.25.2",
            "tree-sitter-python": GrammarMissing("tree-sitter-python"),
            "tree-sitter-go": "0.25.0",
        }
    )
    ident = engine_identity(probe=probe)
    assert ident["tree-sitter-python"] == "missing"


def test_engine_identity_load_failure_records_load_error_abi_sentinel():
    probe = _probe(
        {
            "tree-sitter": "0.25.2",
            "tree-sitter-python": "0.25.0",
            "tree-sitter-go": GrammarLoadError("tree-sitter-go", "abi15"),
        }
    )
    ident = engine_identity(probe=probe)
    assert ident["tree-sitter-go"] == "load-error:abi15"


def test_engine_identity_is_deterministic_across_calls():
    probe = _probe(
        {
            "tree-sitter": "0.25.2",
            "tree-sitter-python": "0.25.0",
            "tree-sitter-go": "0.25.0",
        }
    )
    assert engine_identity(probe=probe) == engine_identity(probe=probe)


def test_engine_identity_carries_schema_version_for_record_format():
    probe = _probe(
        {
            "tree-sitter": "0.25.2",
            "tree-sitter-python": "0.25.0",
            "tree-sitter-go": "0.25.0",
        }
    )
    ident = engine_identity(probe=probe)
    assert ident["schema_version"] == SCHEMA_VERSION
    assert isinstance(SCHEMA_VERSION, int)


# --- 0004: all ten grammar slots + tsx/typescript coupling (AC9, AC10) ---

_ALL_SLOTS = (
    "tree-sitter-python",
    "tree-sitter-go",
    "tree-sitter-rust",
    "tree-sitter-java",
    "tree-sitter-c-sharp",
    "tree-sitter-javascript",
    "tree-sitter-typescript",
    "tree-sitter-tsx",
    "tree-sitter-c",
    "tree-sitter-cpp",
)


def _full_probe(default="9.9.9", **overrides):
    """Probe returning ``default`` for every slot unless overridden (by slot key)."""
    table = {"tree-sitter": default, **{s: default for s in _ALL_SLOTS}}
    table.update(overrides)
    return _probe(table)


def test_engine_identity_enumerates_all_ten_grammar_slots():
    ident = engine_identity(probe=_full_probe())
    for slot in _ALL_SLOTS:
        assert slot in ident, f"missing identity slot {slot}"
    assert ident["tree-sitter"] == "9.9.9"


def test_engine_identity_typescript_and_tsx_share_one_package():
    # Coupling lives in the slot→distribution map: both resolve to one package,
    # so a bump or an absence moves them together.
    assert _GRAMMAR_SLOTS["tree-sitter-typescript"][0] == "tree-sitter-typescript"
    assert _GRAMMAR_SLOTS["tree-sitter-tsx"][0] == "tree-sitter-typescript"


def test_engine_identity_real_typescript_and_tsx_slots_are_equal():
    # With the real (installed) package, both slots carry the same version.
    ident = engine_identity()
    assert ident["tree-sitter-typescript"] == ident["tree-sitter-tsx"]
    assert not ident["tree-sitter-typescript"].startswith("missing")


@pytest.mark.parametrize(
    "pkg",
    [
        "tree-sitter-rust",
        "tree-sitter-java",
        "tree-sitter-c-sharp",
        "tree-sitter-javascript",
        "tree-sitter-typescript",
        "tree-sitter-c",
        "tree-sitter-cpp",
    ],
)
def test_engine_identity_new_grammar_absent_records_missing_sentinel(pkg):
    ident = engine_identity(probe=_full_probe(**{pkg: GrammarMissing(pkg)}))
    assert ident[pkg] == "missing"


def test_engine_identity_new_grammar_load_failure_records_load_error_abi_sentinel():
    probe = _full_probe(**{"tree-sitter-rust": GrammarLoadError("tree-sitter-rust", "abi15")})
    ident = engine_identity(probe=probe)
    assert ident["tree-sitter-rust"] == "load-error:abi15"
