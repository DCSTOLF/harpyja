"""RED (tasks 34-40): Tier-0 orchestrator locate (AC10, 11, 12, 13)."""

import pytest

from harpyja.config.settings import Settings
from harpyja.index.artifacts import resolve_artifact_dir
from harpyja.index.manifest import read_manifest
from harpyja.orchestrator.locate import locate
from harpyja.server.types import CodeSpan, LocateRequest, LocateResult


def _write(root, rel, content="x\n"):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


class FakeEngine:
    """Returns preset spans; records the query/scope it was called with."""

    def __init__(self, spans):
        self.spans = spans
        self.calls = []

    def search(self, pattern, scope=None):
        self.calls.append((pattern, scope))
        return list(self.spans)


def _req(repo, query="q", mode="auto", max_results=8, language_hint=None):
    return LocateRequest(
        query=query,
        repo_path=str(repo),
        mode=mode,
        max_results=max_results,
        language_hint=language_hint,
    )


def test_locate_returns_file_line_citations_tier0(tmp_path):
    _write(tmp_path, "a.py", "needle here\n")
    engine = FakeEngine([CodeSpan(path="a.py", start_line=1, end_line=1)])
    result = locate(_req(tmp_path), Settings(), engine=engine)
    assert isinstance(result, LocateResult)
    assert result.tiers_run == [0]
    assert (result.citations[0].path, result.citations[0].start_line) == ("a.py", 1)


def test_locate_ensures_index_when_no_manifest(tmp_path):
    _write(tmp_path, "a.py", "x\n")
    engine = FakeEngine([])
    locate(_req(tmp_path), Settings(), engine=engine)
    art = resolve_artifact_dir(tmp_path, Settings())
    assert {e.path for e in read_manifest(art)} >= {"a.py"}


def test_locate_reflects_added_file_without_explicit_reindex(tmp_path):
    _write(tmp_path, "a.py")
    engine = FakeEngine([])
    locate(_req(tmp_path), Settings(), engine=engine)
    _write(tmp_path, "b.py")
    locate(_req(tmp_path), Settings(), engine=engine)
    art = resolve_artifact_dir(tmp_path, Settings())
    assert "b.py" in {e.path for e in read_manifest(art)}


def test_locate_reflects_deleted_file_via_prune(tmp_path):
    a = _write(tmp_path, "a.py")
    _write(tmp_path, "b.py")
    engine = FakeEngine([])
    locate(_req(tmp_path), Settings(), engine=engine)
    a.unlink()
    locate(_req(tmp_path), Settings(), engine=engine)
    art = resolve_artifact_dir(tmp_path, Settings())
    assert "a.py" not in {e.path for e in read_manifest(art)}


def test_locate_never_exceeds_max_results(tmp_path):
    _write(tmp_path, "a.py")
    spans = [CodeSpan(path=f"f{i}.py", start_line=1, end_line=1) for i in range(10)]
    engine = FakeEngine(spans)
    result = locate(_req(tmp_path, max_results=3), Settings(), engine=engine)
    assert len(result.citations) <= 3


def test_locate_invalid_mode_rejected(tmp_path):
    _write(tmp_path, "a.py")
    engine = FakeEngine([])
    with pytest.raises(ValueError):
        locate(_req(tmp_path, mode="bogus"), Settings(), engine=engine)


def test_locate_auto_no_longer_emits_mode_no_effect(tmp_path):
    # Spec 0008 (AC1): the Wave-0 "auto has no effect" lock is retired. auto with no
    # Scout wired falls back cleanly to the Tier-0 floor — never the inert note.
    _write(tmp_path, "a.py")
    engine = FakeEngine([CodeSpan(path="a.py", start_line=1, end_line=1)])
    result = locate(_req(tmp_path, mode="auto"), Settings(), engine=engine)
    assert "mode has no effect" not in (result.notes or "")
    assert result.tiers_run == [0]


def test_locate_language_hint_filters_to_matching_language(tmp_path):
    _write(tmp_path, "a.py")
    _write(tmp_path, "b.go")
    spans = [
        CodeSpan(path="a.py", start_line=1, end_line=1),
        CodeSpan(path="b.go", start_line=1, end_line=1),
    ]
    engine = FakeEngine(spans)
    result = locate(_req(tmp_path, language_hint="go"), Settings(), engine=engine)
    assert {c.path for c in result.citations} == {"b.go"}


def test_locate_null_language_returned_without_hint(tmp_path):
    _write(tmp_path, "run", "x\n")  # extensionless → null language
    engine = FakeEngine([CodeSpan(path="run", start_line=1, end_line=1)])
    result = locate(_req(tmp_path), Settings(), engine=engine)
    assert "run" in {c.path for c in result.citations}


def test_locate_null_language_excluded_under_hint(tmp_path):
    _write(tmp_path, "run", "x\n")
    engine = FakeEngine([CodeSpan(path="run", start_line=1, end_line=1)])
    result = locate(_req(tmp_path, language_hint="python"), Settings(), engine=engine)
    assert "run" not in {c.path for c in result.citations}
    assert "undetermined" in (result.notes or "")


def test_locate_unrecognized_hint_note(tmp_path):
    _write(tmp_path, "a.py")
    engine = FakeEngine([CodeSpan(path="a.py", start_line=1, end_line=1)])
    result = locate(_req(tmp_path, language_hint="klingon"), Settings(), engine=engine)
    assert "not a recognized language" in (result.notes or "")


# --- Wave 2: symbol-aware composition (AC9, AC10, AC11, AC13, AC14) ---

import os  # noqa: E402


def test_locate_promotes_definition_above_call_site_for_same_token(tmp_path):
    _write(tmp_path, "a.py", "def foo():\n    pass\nfoo()\nfoo()\n")
    # Fake ripgrep returns the call-site lines for the token `foo`.
    engine = FakeEngine([CodeSpan("a.py", 3, 3), CodeSpan("a.py", 4, 4)])
    result = locate(_req(tmp_path, query="foo"), Settings(), engine=engine)
    top = result.citations[0]
    assert top.symbol == "foo"  # the definition
    assert (top.start_line, top.end_line) == (1, 2)
    assert result.tiers_run == [0]  # still Tier 0, zero model calls


def test_locate_no_symbol_match_degrades_to_wave1_exact_citations_and_order(tmp_path):
    _write(tmp_path, "a.py", "x = 1\n")  # no symbol named 'zzz'
    engine = FakeEngine([CodeSpan(path="a.py", start_line=1, end_line=1)])
    result = locate(_req(tmp_path, query="zzz"), Settings(), engine=engine)
    assert [(c.path, c.start_line) for c in result.citations] == [("a.py", 1)]
    assert result.citations[0].symbol is None  # pure text hit, exactly Wave-1


def test_locate_method_address_foo_dot_bar_promotes_method(tmp_path):
    _write(tmp_path, "a.py", "class Foo:\n    def bar(self):\n        pass\n")
    result = locate(_req(tmp_path, query="Foo.bar"), Settings(), engine=FakeEngine([]))
    assert any(c.symbol == "bar" and c.kind == "method" for c in result.citations)


def test_locate_builds_symbols_from_scratch_when_none_present(tmp_path):
    _write(tmp_path, "a.py", "def foo():\n    pass\n")
    result = locate(_req(tmp_path, query="foo"), Settings(), engine=FakeEngine([]))
    assert any(c.symbol == "foo" for c in result.citations)


def test_locate_after_edit_reflects_new_symbols_without_explicit_reindex(tmp_path):
    f = _write(tmp_path, "a.py", "def foo():\n    pass\n")
    locate(_req(tmp_path, query="foo"), Settings(), engine=FakeEngine([]))
    f.write_text("def bar():\n    pass\n", encoding="utf-8")
    os.utime(f, (2_000_000_000, 2_000_000_000))
    result = locate(_req(tmp_path, query="bar"), Settings(), engine=FakeEngine([]))
    assert any(c.symbol == "bar" for c in result.citations)


# --- 0004: new-language definition promotion through the unchanged pipeline (AC11, AC12) ---


def test_locate_promotes_rust_definition_above_call_sites(tmp_path):
    _write(tmp_path, "lib.rs", "fn parse_cfg() {}\nfn caller() { parse_cfg(); }\n")
    engine = FakeEngine([CodeSpan("lib.rs", 2, 2)])  # ripgrep call-site hit
    result = locate(_req(tmp_path, query="parse_cfg"), Settings(), engine=engine)
    top = result.citations[0]
    assert top.symbol == "parse_cfg"  # the definition outranks the call site
    assert top.start_line == 1
    assert result.tiers_run == [0]  # still Tier 0, zero model calls


def test_locate_rust_method_address_colon_colon_promotes_method(tmp_path):
    _write(tmp_path, "lib.rs", "struct Foo;\nimpl Foo { fn bar(&self) {} }\n")
    result = locate(_req(tmp_path, query="Foo::bar"), Settings(), engine=FakeEngine([]))
    assert any(c.symbol == "bar" and c.kind == "method" for c in result.citations)


def test_locate_exact_case_sensitive_for_new_language(tmp_path):
    _write(tmp_path, "M.java", "class C { void Parse() {} }\n")
    # `parse` (lower) must NOT match the `Parse` definition.
    result = locate(_req(tmp_path, query="parse"), Settings(), engine=FakeEngine([]))
    assert all(c.symbol != "Parse" for c in result.citations)
    # `Parse` (exact) does.
    result2 = locate(_req(tmp_path, query="Parse"), Settings(), engine=FakeEngine([]))
    assert any(c.symbol == "Parse" for c in result2.citations)


def test_locate_no_symbol_match_degrades_to_wave1_on_mixed_tree(tmp_path):
    _write(tmp_path, "lib.rs", "fn bar() {}\n")
    _write(tmp_path, "M.java", "class C {}\n")
    engine = FakeEngine([CodeSpan(path="lib.rs", start_line=1, end_line=1)])
    result = locate(_req(tmp_path, query="zzz_nomatch"), Settings(), engine=engine)
    # No symbol named zzz_nomatch → identical to the Wave-1 ripgrep-only result.
    assert [(c.path, c.start_line) for c in result.citations] == [("lib.rs", 1)]
    assert result.citations[0].symbol is None


def test_locate_language_hint_filters_new_language_by_manifest_language(tmp_path):
    _write(tmp_path, "lib.rs", "x\n")
    _write(tmp_path, "M.java", "x\n")
    spans = [
        CodeSpan(path="lib.rs", start_line=1, end_line=1),
        CodeSpan(path="M.java", start_line=1, end_line=1),
    ]
    result = locate(_req(tmp_path, language_hint="rust"), Settings(), engine=FakeEngine(spans))
    assert {c.path for c in result.citations} == {"lib.rs"}


# --- Wave 3: Scout routing (AC1, AC2, AC3, AC5, AC6, AC8, AC9) ---

from harpyja.gateway.gateway import AirGapError, ModelGateway  # noqa: E402
from harpyja.orchestrator.gate import VerificationGate  # noqa: E402
from harpyja.orchestrator.locate import (  # noqa: E402
    GATE_LOW_CONFIDENCE,
    GATE_SCORING_FAILED,
    GATE_SKIPPED_NO_LINE_RANGE,
    GATE_SKIPPED_SCOUT_EMPTY,
)
from harpyja.scout.errors import ScoutUnavailable  # noqa: E402
from harpyja.symbols.ripgrep import RipgrepMissingError  # noqa: E402

_LOOPBACK = "http://127.0.0.1:11434/v1"


def _gate(score=None, *, raises=False):
    """A VerificationGate over a loopback gateway with a fixed-score fake judge."""

    def judge(query, cited_text):
        if raises:
            raise RuntimeError("judge boom")
        return score

    return VerificationGate(ModelGateway(api_base=_LOOPBACK, model="scout"), judge=judge)


class _BoomScout:
    """A Scout double that explodes if it is ever consulted (auto must not)."""

    def search(self, *args, **kwargs):
        raise AssertionError("scout/gateway invoked on a non-Scout path")


class _FakeScout:
    """Returns preset Scout spans; records calls."""

    def __init__(self, spans):
        self.spans = spans
        self.calls = []

    def search(self, pattern, scope=None):
        self.calls.append((pattern, scope))
        return list(self.spans)


class _UnavailableScout:
    def __init__(self, cause):
        self.cause = cause

    def search(self, pattern, scope=None):
        raise ScoutUnavailable(self.cause)


def test_locate_auto_no_scout_falls_back_to_tier0(tmp_path):
    # Spec 0008 (AC1): with no Scout wired, auto is the Tier-0 floor — the symbol-aware
    # Tier-0 result, minus the retired "mode has no effect" lock note.
    _write(tmp_path, "a.py", "def foo():\n    pass\nfoo()\n")
    engine = FakeEngine([CodeSpan("a.py", 3, 3)])
    result = locate(_req(tmp_path, query="foo"), Settings(), engine=engine)
    assert result.tiers_run == [0]
    assert "mode has no effect" not in (result.notes or "")
    assert result.citations[0].symbol == "foo"  # definition still promoted
    assert all(c.source_tier == 0 for c in result.citations)
    assert result.confidence == "medium"


# --- Spec 0008 (Wave 5): auto ladder contract (AC1, AC4, AC5, AC6, AC7) ---


def test_locate_auto_gated_pass_runs_zero_one(tmp_path):
    _write(tmp_path, "a.py", "needle here\n")
    scout = _FakeScout([CodeSpan("a.py", 1, 1)])
    result = locate(
        _req(tmp_path, query="needle"),
        Settings(),
        engine=FakeEngine([]),
        scout_engine=scout,
        deep_engine=_BoomDeep(),  # must NOT be reached on a gated pass
        gate=_gate(0.9),
    )
    assert result.tiers_run == [0, 1]  # Tier-2 not spent (cost lever held)
    assert result.confidence == "high"
    assert all(c.source_tier == 1 for c in result.citations)


def test_locate_auto_gate_fail_escalates_to_deep(tmp_path):
    _write(tmp_path, "a.py", "needle here\n")
    scout = _FakeScout([CodeSpan("a.py", 1, 1)])
    deep = _FakeDeep([CodeSpan("a.py", 1, 1)])
    result = locate(
        _req(tmp_path, query="needle"),
        Settings(),
        engine=FakeEngine([]),
        scout_engine=scout,
        deep_engine=deep,
        gate=_gate(0.1),  # below threshold → escalate
    )
    assert result.tiers_run == [0, 1, 2]
    assert deep.calls
    assert all(c.source_tier == 2 for c in result.citations)


def test_locate_auto_broad_routes_straight_to_deep(tmp_path):
    _write(tmp_path, "a.py", "needle here\n")
    deep = _FakeDeep([CodeSpan("a.py", 1, 1)])
    result = locate(
        _req(tmp_path, query="trace the whole request lifecycle"),
        Settings(),
        engine=FakeEngine([]),
        scout_engine=_BoomScout(),  # broad skips Scout entirely
        deep_engine=deep,
        gate=_gate(0.9),
    )
    assert result.tiers_run == [0, 2]
    assert deep.calls


def test_locate_auto_index_not_ready_gated_pass_is_one(tmp_path):
    _write(tmp_path, "a.py", "needle here\n")
    scout = _FakeScout([CodeSpan("a.py", 1, 1)])
    result = locate(
        _req(tmp_path, query="needle"),
        Settings(),
        engine=FakeEngine([]),
        scout_engine=scout,
        deep_engine=_BoomDeep(),
        gate=_gate(0.9),
        index_ready=False,  # seed skipped → query-only
    )
    assert result.tiers_run == [1]


def test_locate_auto_index_not_ready_escalated_is_one_two(tmp_path):
    _write(tmp_path, "a.py", "needle here\n")
    scout = _FakeScout([CodeSpan("a.py", 1, 1)])
    deep = _FakeDeep([CodeSpan("a.py", 1, 1)])
    result = locate(
        _req(tmp_path, query="needle"),
        Settings(),
        engine=FakeEngine([]),
        scout_engine=scout,
        deep_engine=deep,
        gate=_gate(0.1),
        index_ready=False,
    )
    assert result.tiers_run == [1, 2]


# --- Spec 0008: empty-case split + gate-scoring-failed contract (AC8) ---


def test_locate_auto_scout_typed_unavailable_degrades(tmp_path):
    # typed-unavailable → degrade to Tier-0 floor, confidence "degraded" (UNCHANGED,
    # NOT "low"), no escalation.
    _write(tmp_path, "a.py", "needle\n")
    engine = FakeEngine([CodeSpan("a.py", 1, 1)])
    result = locate(
        _req(tmp_path, query="needle"),
        Settings(),
        engine=engine,
        scout_engine=_UnavailableScout("connection-refused"),
        deep_engine=_BoomDeep(),  # must NOT escalate
        gate=_gate(0.9),
    )
    assert result.tiers_run == [0]
    assert result.confidence == "degraded"
    assert result.notes == "scout-degraded:connection-refused"


def test_locate_auto_scout_honest_empty_skips_gate_returns_seed(tmp_path):
    # Scout clean-empty + seed has matches → [0,1], gate-skipped flag, no climb.
    _write(tmp_path, "a.py", "needle\n")
    engine = FakeEngine([CodeSpan("a.py", 1, 1)])  # seed has results
    result = locate(
        _req(tmp_path, query="needle"),
        Settings(),
        engine=engine,
        scout_engine=_FakeScout([]),  # honest-empty
        deep_engine=_BoomDeep(),
        gate=_gate(0.9),
    )
    assert result.tiers_run == [0, 1]
    assert "gate-skipped:scout-empty" in (result.notes or "")
    assert "no-matches" not in (result.notes or "")
    assert result.citations  # the seed


def test_locate_auto_scout_honest_empty_query_only_is_one(tmp_path):
    # index_ready=False + Scout clean-empty → [1], no seed, +no-matches.
    _write(tmp_path, "a.py", "needle\n")
    result = locate(
        _req(tmp_path, query="needle"),
        Settings(),
        engine=FakeEngine([CodeSpan("a.py", 1, 1)]),
        scout_engine=_FakeScout([]),
        deep_engine=_BoomDeep(),
        gate=_gate(0.9),
        index_ready=False,
    )
    assert result.tiers_run == [1]
    assert result.notes == "gate-skipped:scout-empty+no-matches"
    assert result.citations == []


def test_locate_auto_scout_honest_empty_empty_seed_no_matches_suffix(tmp_path):
    # Scout clean-empty + seed also empty → +no-matches suffix, still [0,1].
    _write(tmp_path, "a.py", "x = 1\n")
    result = locate(
        _req(tmp_path, query="zzz_nomatch"),
        Settings(),
        engine=FakeEngine([]),  # empty seed
        scout_engine=_FakeScout([]),
        deep_engine=_BoomDeep(),
        gate=_gate(0.9),
    )
    assert result.tiers_run == [0, 1]
    assert result.notes == "gate-skipped:scout-empty+no-matches"


def test_locate_auto_malformed_citation_escalates(tmp_path):
    # A Scout citation the gate cannot read back (file absent) → gate can't vouch
    # → escalate to Tier-2 (the "malformed / un-scoreable" case).
    _write(tmp_path, "a.py", "needle\n")
    scout = _FakeScout([CodeSpan("ghost.py", 1, 1)])  # ghost.py does not exist
    deep = _FakeDeep([CodeSpan("a.py", 1, 1)])
    result = locate(
        _req(tmp_path, query="needle"),
        Settings(),
        engine=FakeEngine([]),
        scout_engine=scout,
        deep_engine=deep,
        gate=_gate(0.9),  # would pass, but read-back fails first
    )
    assert result.tiers_run == [0, 1, 2]
    assert deep.calls


def test_locate_auto_gate_scoring_failed_escalates_retains_flag(tmp_path):
    # Judge errors → gate-scoring-failed; in auto a tier remains → escalate,
    # flag retained, confidence low.
    _write(tmp_path, "a.py", "needle\n")
    scout = _FakeScout([CodeSpan("a.py", 1, 1)])
    deep = _FakeDeep([CodeSpan("a.py", 1, 1)])
    result = locate(
        _req(tmp_path, query="needle"),
        Settings(),
        engine=FakeEngine([]),
        scout_engine=scout,
        deep_engine=deep,
        gate=_gate(raises=True),
    )
    assert result.tiers_run == [0, 1, 2]
    assert "gate-scoring-failed" in (result.notes or "")
    assert result.confidence == "low"


# --- Spec 0008: confidence map + stable flag ids (AC9) ---


def test_flag_ids_are_stable_strings():
    # Callers/tests branch on the identifier, never the wording.
    assert GATE_LOW_CONFIDENCE == "gate-low-confidence"
    assert GATE_SCORING_FAILED == "gate-scoring-failed"
    assert GATE_SKIPPED_SCOUT_EMPTY == "gate-skipped:scout-empty"


def test_locate_confidence_gated_pass_high(tmp_path):
    _write(tmp_path, "a.py", "needle\n")
    result = locate(
        _req(tmp_path, query="needle"),
        Settings(),
        engine=FakeEngine([]),
        scout_engine=_FakeScout([CodeSpan("a.py", 1, 1)]),
        deep_engine=_BoomDeep(),
        gate=_gate(0.9),
    )
    assert result.tiers_run == [0, 1]
    assert result.confidence == "high"


def test_locate_confidence_honest_empty_seed_matches_is_medium(tmp_path):
    _write(tmp_path, "a.py", "needle\n")
    result = locate(
        _req(tmp_path, query="needle"),
        Settings(),
        engine=FakeEngine([CodeSpan("a.py", 1, 1)]),  # seed has matches
        scout_engine=_FakeScout([]),
        gate=_gate(0.9),
    )
    assert "gate-skipped:scout-empty" in (result.notes or "")
    assert result.confidence == "medium"


def test_locate_confidence_honest_empty_no_matches_is_low(tmp_path):
    _write(tmp_path, "a.py", "x = 1\n")
    result = locate(
        _req(tmp_path, query="zzz_nomatch"),
        Settings(),
        engine=FakeEngine([]),  # empty seed
        scout_engine=_FakeScout([]),
        gate=_gate(0.9),
    )
    assert result.notes == "gate-skipped:scout-empty+no-matches"
    assert result.confidence == "low"


def test_locate_confidence_escalated_is_medium(tmp_path):
    _write(tmp_path, "a.py", "needle\n")
    result = locate(
        _req(tmp_path, query="needle"),
        Settings(),
        engine=FakeEngine([]),
        scout_engine=_FakeScout([CodeSpan("a.py", 1, 1)]),
        deep_engine=_FakeDeep([CodeSpan("a.py", 1, 1)]),
        gate=_gate(0.1),  # fail → escalate
    )
    assert result.tiers_run == [0, 1, 2]
    assert result.confidence == "medium"


def test_locate_confidence_broad_deep_is_medium(tmp_path):
    _write(tmp_path, "a.py", "needle\n")
    result = locate(
        _req(tmp_path, query="trace the whole request lifecycle"),
        Settings(),
        engine=FakeEngine([]),
        deep_engine=_FakeDeep([CodeSpan("a.py", 1, 1)]),
        gate=_gate(0.9),
    )
    assert result.tiers_run == [0, 2]
    assert result.confidence == "medium"


def test_locate_confidence_flag_override_is_low(tmp_path):
    # A gate-scoring-failed flag pins confidence to low even on an escalated Deep run.
    _write(tmp_path, "a.py", "needle\n")
    result = locate(
        _req(tmp_path, query="needle"),
        Settings(),
        engine=FakeEngine([]),
        scout_engine=_FakeScout([CodeSpan("a.py", 1, 1)]),
        deep_engine=_FakeDeep([CodeSpan("a.py", 1, 1)]),
        gate=_gate(raises=True),
    )
    assert result.tiers_run == [0, 1, 2]
    assert "gate-scoring-failed" in (result.notes or "")
    assert result.confidence == "low"


def test_locate_fast_routes_to_scout(tmp_path):
    _write(tmp_path, "a.py", "x = 1\n")
    scout = _FakeScout([CodeSpan(path="a.py", start_line=1, end_line=1)])
    result = locate(
        _req(tmp_path, mode="fast"), Settings(), engine=FakeEngine([]), scout_engine=scout
    )
    assert scout.calls  # Scout was consulted
    assert {c.path for c in result.citations} == {"a.py"}


def test_locate_fast_tiers_run_includes_one(tmp_path):
    _write(tmp_path, "a.py", "x = 1\n")
    scout = _FakeScout([CodeSpan(path="a.py", start_line=1, end_line=1)])
    result = locate(
        _req(tmp_path, mode="fast"), Settings(), engine=FakeEngine([]), scout_engine=scout
    )
    assert result.tiers_run == [0, 1]


def test_locate_fast_citations_source_tier_one(tmp_path):
    _write(tmp_path, "a.py", "x = 1\n")
    scout = _FakeScout([CodeSpan(path="a.py", start_line=1, end_line=1)])
    result = locate(
        _req(tmp_path, mode="fast"), Settings(), engine=FakeEngine([]), scout_engine=scout
    )
    assert result.citations
    assert all(c.source_tier == 1 for c in result.citations)


# --- Spec 0008: fast informational gate (AC7, AC8) ---


def test_locate_fast_gate_would_fail_flags_low_confidence(tmp_path):
    _write(tmp_path, "a.py", "needle\n")
    scout = _FakeScout([CodeSpan("a.py", 1, 1)])
    result = locate(
        _req(tmp_path, query="needle", mode="fast"),
        Settings(),
        engine=FakeEngine([]),
        scout_engine=scout,
        deep_engine=_BoomDeep(),  # fast must never escalate
        gate=_gate(0.1),
    )
    assert result.tiers_run == [0, 1]
    assert "gate-low-confidence" in (result.notes or "")
    assert result.confidence == "low"


def test_locate_fast_never_escalates_even_for_broad(tmp_path):
    _write(tmp_path, "a.py", "needle\n")
    scout = _FakeScout([CodeSpan("a.py", 1, 1)])
    result = locate(
        _req(tmp_path, query="trace the whole request lifecycle", mode="fast"),
        Settings(),
        engine=FakeEngine([]),
        scout_engine=scout,
        deep_engine=_BoomDeep(),
        gate=_gate(0.1),
    )
    assert result.tiers_run == [0, 1]  # fast wins over broad — never Tier-2
    assert "gate-low-confidence" in (result.notes or "")


def test_locate_fast_gate_pass_no_flag(tmp_path):
    _write(tmp_path, "a.py", "needle\n")
    scout = _FakeScout([CodeSpan("a.py", 1, 1)])
    result = locate(
        _req(tmp_path, query="needle", mode="fast"),
        Settings(),
        engine=FakeEngine([]),
        scout_engine=scout,
        gate=_gate(0.9),
    )
    assert "gate-low-confidence" not in (result.notes or "")
    assert result.confidence == "high"


def test_locate_fast_honest_empty_no_low_confidence_flag(tmp_path):
    _write(tmp_path, "a.py", "needle\n")
    result = locate(
        _req(tmp_path, query="needle", mode="fast"),
        Settings(),
        engine=FakeEngine([]),
        scout_engine=_FakeScout([]),  # honest-empty
        gate=_gate(0.1),
    )
    assert "gate-skipped:scout-empty" in (result.notes or "")
    assert "gate-low-confidence" not in (result.notes or "")


def test_locate_fast_gate_scoring_failed_best_effort_tier1(tmp_path):
    _write(tmp_path, "a.py", "needle\n")
    scout = _FakeScout([CodeSpan("a.py", 1, 1)])
    result = locate(
        _req(tmp_path, query="needle", mode="fast"),
        Settings(),
        engine=FakeEngine([]),
        scout_engine=scout,
        deep_engine=_BoomDeep(),
        gate=_gate(raises=True),
    )
    assert result.tiers_run == [0, 1]  # no further tier in fast
    assert "gate-scoring-failed" in (result.notes or "")
    assert result.confidence == "low"


def test_locate_degraded_connection_refused(tmp_path):
    _write(tmp_path, "a.py", "needle\n")
    engine = FakeEngine([CodeSpan(path="a.py", start_line=1, end_line=1)])  # Tier-0 has results
    result = locate(
        _req(tmp_path, mode="fast"),
        Settings(),
        engine=engine,
        scout_engine=_UnavailableScout("connection-refused"),
    )
    assert result.confidence == "degraded"
    assert result.tiers_run == [0]
    assert result.notes == "scout-degraded:connection-refused"
    assert {c.path for c in result.citations} == {"a.py"}


def test_locate_degraded_no_endpoint_configured(tmp_path):
    _write(tmp_path, "a.py", "needle\n")
    engine = FakeEngine([CodeSpan(path="a.py", start_line=1, end_line=1)])
    result = locate(
        _req(tmp_path, mode="fast"),
        Settings(),
        engine=engine,
        scout_engine=_UnavailableScout("no-endpoint-configured"),
    )
    assert result.notes == "scout-degraded:no-endpoint-configured"


def test_locate_degraded_backend_error(tmp_path):
    _write(tmp_path, "a.py", "needle\n")
    engine = FakeEngine([CodeSpan(path="a.py", start_line=1, end_line=1)])
    result = locate(
        _req(tmp_path, mode="fast"),
        Settings(),
        engine=engine,
        scout_engine=_UnavailableScout("backend-error"),
    )
    assert result.notes == "scout-degraded:backend-error"


def test_locate_degraded_empty_tier0_no_matches_suffix(tmp_path):
    _write(tmp_path, "a.py", "x = 1\n")
    engine = FakeEngine([])  # Tier-0 honestly empty
    result = locate(
        _req(tmp_path, query="zzz_nomatch", mode="fast"),
        Settings(),
        engine=engine,
        scout_engine=_UnavailableScout("connection-refused"),
    )
    assert result.citations == []
    assert result.notes == "scout-degraded:connection-refused+no-matches"
    assert result.confidence == "degraded"


def test_locate_seed_precondition_error_propagates(tmp_path):
    _write(tmp_path, "a.py", "x = 1\n")

    class _RgMissingScout:
        def search(self, pattern, scope=None):
            raise RipgrepMissingError("rg not found")

    with pytest.raises(RipgrepMissingError):
        locate(
            _req(tmp_path, mode="fast"),
            Settings(),
            engine=FakeEngine([]),
            scout_engine=_RgMissingScout(),
        )


def test_locate_non_loopback_raises_airgap(tmp_path):
    _write(tmp_path, "a.py", "x = 1\n")

    class _AirGapScout:
        def search(self, pattern, scope=None):
            raise AirGapError("non-loopback endpoint rejected")

    with pytest.raises(AirGapError):
        locate(
            _req(tmp_path, mode="fast"),
            Settings(),
            engine=FakeEngine([]),
            scout_engine=_AirGapScout(),
        )


# --- Wave 4: Deep (Tier 2) routing — supersedes the Wave-3 provisional guard ---

from harpyja.deep.errors import DeepUnavailable  # noqa: E402


class _BoomDeep:
    """A Deep double that explodes if consulted (auto/fast must not)."""

    def run(self, *args, **kwargs):
        raise AssertionError("deep invoked on a non-deep path")


class _FakeDeep:
    """Returns (citations, truncated_bound); records calls."""

    def __init__(self, spans, truncated=None):
        self.spans = spans
        self.truncated = truncated
        self.calls = []

    def run(self, query):
        self.calls.append(query)
        return list(self.spans), self.truncated


class _UnavailableDeep:
    def __init__(self, cause):
        self.cause = cause

    def run(self, query):
        raise DeepUnavailable(self.cause)


def test_locate_deep_emits_tier2_marker_when_wired(tmp_path):
    # Inverts the Wave-3 "no Tier-2 marker" guard: deep now legitimately reports Tier 2.
    _write(tmp_path, "a.py", "x = 1\n")
    deep = _FakeDeep([CodeSpan(path="a.py", start_line=1, end_line=1)])
    result = locate(
        _req(tmp_path, mode="deep"),
        Settings(),
        engine=FakeEngine([]),
        deep_engine=deep,
    )
    assert result.tiers_run == [0, 2]
    assert result.citations and all(c.source_tier == 2 for c in result.citations)


def test_locate_deep_seed_rg_missing_propagates(tmp_path):
    _write(tmp_path, "a.py", "x = 1\n")

    class _RgMissingDeep:
        def run(self, query):
            raise RipgrepMissingError("rg not found")

    with pytest.raises(RipgrepMissingError):
        locate(
            _req(tmp_path, mode="deep"),
            Settings(),
            engine=FakeEngine([]),
            deep_engine=_RgMissingDeep(),
        )


def test_locate_deep_unavailable_degrades_to_scout(tmp_path):
    _write(tmp_path, "a.py", "needle\n")
    scout = _FakeScout([CodeSpan(path="a.py", start_line=1, end_line=1)])
    result = locate(
        _req(tmp_path, mode="deep"),
        Settings(),
        engine=FakeEngine([]),
        scout_engine=scout,
        deep_engine=_UnavailableDeep("rlm-down"),
    )
    assert result.tiers_run == [0, 1]  # Scout best-effort ran
    assert result.notes.startswith("deep-degraded:rlm-down")
    assert all(c.source_tier == 1 for c in result.citations)


def test_locate_deep_double_degrade_carries_both_notes(tmp_path):
    _write(tmp_path, "a.py", "needle\n")
    engine = FakeEngine([CodeSpan(path="a.py", start_line=1, end_line=1)])  # Tier-0 has results
    result = locate(
        _req(tmp_path, mode="deep"),
        Settings(),
        engine=engine,
        scout_engine=_UnavailableScout("connection-refused"),
        deep_engine=_UnavailableDeep("rlm-down"),
    )
    assert result.tiers_run == [0]
    assert "deep-degraded:rlm-down" in result.notes
    assert "scout-degraded:connection-refused" in result.notes


def test_locate_deep_distinct_cause_notes(tmp_path):
    _write(tmp_path, "a.py", "needle\n")
    notes = set()
    for cause in ("sandbox-absent", "rlm-down", "backend-error"):
        result = locate(
            _req(tmp_path, mode="deep"),
            Settings(),
            engine=FakeEngine([]),
            scout_engine=_FakeScout([CodeSpan("a.py", 1, 1)]),
            deep_engine=_UnavailableDeep(cause),
        )
        notes.add(result.notes.split(";")[0])
    assert notes == {
        "deep-degraded:sandbox-absent",
        "deep-degraded:rlm-down",
        "deep-degraded:backend-error",
    }


def test_locate_deep_weak_or_zero_citations_stay_tier2(tmp_path):
    _write(tmp_path, "a.py", "x = 1\n")
    # Successful Deep run returning zero citations must NOT fall back to Scout.
    result = locate(
        _req(tmp_path, mode="deep"),
        Settings(),
        engine=FakeEngine([]),
        scout_engine=_BoomScout(),  # explodes if a fallback is wrongly attempted
        deep_engine=_FakeDeep([]),
    )
    assert result.tiers_run == [0, 2]
    assert result.citations == []


def test_locate_deep_airgap_propagates(tmp_path):
    _write(tmp_path, "a.py", "x = 1\n")

    class _AirGapDeep:
        def run(self, query):
            raise AirGapError("non-loopback endpoint rejected")

    with pytest.raises(AirGapError):
        locate(
            _req(tmp_path, mode="deep"),
            Settings(),
            engine=FakeEngine([]),
            deep_engine=_AirGapDeep(),
        )


def test_locate_deep_truncated_note_plumbed(tmp_path):
    _write(tmp_path, "a.py", "x = 1\n")
    deep = _FakeDeep([CodeSpan("a.py", 1, 1)], truncated="wall-clock")
    result = locate(
        _req(tmp_path, mode="deep"),
        Settings(),
        engine=FakeEngine([]),
        deep_engine=deep,
    )
    assert result.tiers_run == [0, 2]
    assert "deep-truncated:wall-clock" in (result.notes or "")


def test_locate_auto_makes_zero_deep_calls(tmp_path):
    _write(tmp_path, "a.py", "x = 1\n")
    result = locate(
        _req(tmp_path), Settings(), engine=FakeEngine([]), deep_engine=_BoomDeep()
    )
    assert result.tiers_run == [0]  # _BoomDeep never raised → Deep untouched


def test_locate_fast_makes_zero_deep_calls(tmp_path):
    _write(tmp_path, "a.py", "x = 1\n")
    result = locate(
        _req(tmp_path, mode="fast"),
        Settings(),
        engine=FakeEngine([]),
        scout_engine=_FakeScout([CodeSpan("a.py", 1, 1)]),
        deep_engine=_BoomDeep(),
    )
    assert result.tiers_run == [0, 1]  # Scout path; Deep untouched


# --- Spec 0011 (citation-shape): file-level (line-less) gate routing (AC13) ---


def test_locate_auto_not_verifiable_escalates_to_deep(tmp_path):
    # AC13: a file-level (line-less) Scout result is not-verifiable; in auto with a
    # Deep tier remaining, it ESCALATES (verification was unavailable), and the
    # stable marker records why.
    _write(tmp_path, "a.py", "needle here\n")
    scout = _FakeScout([CodeSpan("a.py", None, None)])  # file-level span
    deep = _FakeDeep([CodeSpan("a.py", 1, 1)])
    result = locate(
        _req(tmp_path, query="needle"),
        Settings(),
        engine=FakeEngine([]),
        scout_engine=scout,
        deep_engine=deep,
        gate=_gate(0.9),  # would pass a lined span, but a file-level one is skipped
    )
    assert result.tiers_run == [0, 1, 2]
    assert deep.calls
    assert GATE_SKIPPED_NO_LINE_RANGE in (result.notes or "")


def test_locate_auto_not_verifiable_carries_marker_without_deep(tmp_path):
    # AC13: no Deep tier remaining → carry the coarse file-level result best-effort,
    # tagged with the marker, never at high confidence.
    _write(tmp_path, "a.py", "needle here\n")
    scout = _FakeScout([CodeSpan("a.py", None, None)])
    result = locate(
        _req(tmp_path, query="needle"),
        Settings(),
        engine=FakeEngine([]),
        scout_engine=scout,
        deep_engine=None,
        gate=_gate(0.9),
    )
    assert result.tiers_run == [0, 1]
    assert GATE_SKIPPED_NO_LINE_RANGE in (result.notes or "")
    assert result.confidence != "high"
    assert result.citations and result.citations[0].is_file_level


def test_no_line_range_marker_distinct_from_other_gate_flags():
    # AC13: the marker is a distinct stable id — it never collapses into the
    # low-confidence / scoring-failed / scout-empty flags.
    assert GATE_SKIPPED_NO_LINE_RANGE == "gate-skipped:no-line-range"
    assert GATE_SKIPPED_NO_LINE_RANGE not in {
        GATE_LOW_CONFIDENCE,
        GATE_SCORING_FAILED,
        GATE_SKIPPED_SCOUT_EMPTY,
    }


def test_locate_fast_file_level_tags_no_line_range_not_low_confidence(tmp_path):
    # AC13 (fast): a file-level result in fast mode tags the distinct marker, never
    # collapsing into gate-low-confidence.
    _write(tmp_path, "a.py", "needle here\n")
    scout = _FakeScout([CodeSpan("a.py", None, None)])
    result = locate(
        _req(tmp_path, query="needle", mode="fast"),
        Settings(),
        engine=FakeEngine([]),
        scout_engine=scout,
        deep_engine=_BoomDeep(),  # fast never escalates
        gate=_gate(0.9),
    )
    assert GATE_SKIPPED_NO_LINE_RANGE in (result.notes or "")
    assert GATE_LOW_CONFIDENCE not in (result.notes or "")
