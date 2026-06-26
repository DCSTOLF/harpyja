"""Tests for engine_identity — the symbol-cache key (AC8d, AC15).

The identity binds a `symbols.jsonl` generation to the exact tree-sitter runtime
+ grammar versions that produced it, so a grammar bump invalidates the cache. An
absent or load-failed grammar records a *stable sentinel* (never an empty slot)
so a degraded run still writes a reproducible sidecar.
"""

from __future__ import annotations

from harpyja.symbols.engine_identity import (
    SCHEMA_VERSION,
    GrammarLoadError,
    GrammarMissing,
    engine_identity,
)


def _probe(table):
    """Build a probe seam from a {key: version-or-exception} table."""

    def probe(key: str) -> str:
        val = table[key]
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
