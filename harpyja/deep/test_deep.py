"""Unit tests for Tier 2 (Deep) — errors, backend Protocol, budget meter.

All network-/process-/model-free: fakes + injected runner only. The live RLM /
Deno sandbox lives in test_deep_integration.py (skip-not-fail).
"""

import pytest

from harpyja.config.settings import Settings
from harpyja.deep.backend import DeepBackend
from harpyja.deep.budget import DeepBudget, DeepBudgetExceeded
from harpyja.deep.errors import (
    BACKEND_ERROR,
    PARSE_ERROR,
    RLM_DOWN,
    SANDBOX_ABSENT,
    DeepUnavailable,
)
from harpyja.deep.runner import DeepRunner
from harpyja.server.types import CodeSpan

# --- task 05: DeepUnavailable stable causes ---


def test_deep_unavailable_carries_stable_cause():
    err = DeepUnavailable(RLM_DOWN)
    assert err.cause == "rlm-down"
    assert {SANDBOX_ABSENT, RLM_DOWN, BACKEND_ERROR} == {
        "sandbox-absent",
        "rlm-down",
        "backend-error",
    }


def test_deep_unavailable_preserves_cause():
    try:
        try:
            raise OSError("boom")
        except OSError as inner:
            raise DeepUnavailable(BACKEND_ERROR) from inner
    except DeepUnavailable as err:
        assert isinstance(err.__cause__, OSError)


# --- spec 0014 (P1): parse-error is a distinct, stable, sibling cause ---


def test_deep_unavailable_parse_error_cause_is_stable():
    # A named, narrow-caught seam earns its OWN cause; it is a sibling of
    # backend-error, never a replacement for it.
    assert PARSE_ERROR == "parse-error"
    assert DeepUnavailable(PARSE_ERROR).cause == "parse-error"
    assert len({SANDBOX_ABSENT, RLM_DOWN, BACKEND_ERROR, PARSE_ERROR}) == 4


# --- task 07: DeepBackend Protocol ---


def test_deep_backend_protocol_accepts_fake():
    class _Fake:
        def run(self, query, seed, tools):
            return []

    assert isinstance(_Fake(), DeepBackend)


# --- task 09: DeepBudget meter ---


def test_budget_tool_calls_stops_after_max():
    b = DeepBudget(Settings(deep_max_tool_calls=2))
    assert b.charge_tool_call() is True
    assert b.charge_tool_call() is True
    assert b.charge_tool_call() is False
    assert b.truncated_bound == "tool-calls"


def test_budget_token_ceiling_blocks_completion():
    b = DeepBudget(Settings(deep_token_ceiling=100))
    assert b.charge_tokens(80) is True
    assert b.charge_tokens(80) is False
    assert b.truncated_bound == "tokens"


def test_budget_depth_caps_at_max_depth():
    b = DeepBudget(Settings(deep_max_depth=2, deep_max_subqueries=100))
    assert b.enter_subquery() is True  # depth 1
    assert b.enter_subquery() is True  # depth 2
    assert b.enter_subquery() is False  # depth 3 > max
    assert b.truncated_bound == "depth"


def test_budget_subqueries_cap_at_spawn_seam():
    b = DeepBudget(Settings(deep_max_subqueries=2, deep_max_depth=100))
    assert b.enter_subquery() is True
    b.exit_subquery()
    assert b.enter_subquery() is True
    b.exit_subquery()
    assert b.enter_subquery() is False  # 3rd spawn > max
    assert b.truncated_bound == "subqueries"


def test_budget_truncated_bound_none_when_unexhausted():
    b = DeepBudget(Settings())
    assert b.charge_tool_call() is True
    assert b.charge_tokens(10) is True
    assert b.enter_subquery() is True
    assert b.truncated_bound is None


# --- task 13: runner counter facet (in-process; no subprocess) ---


def test_runner_invokes_target_and_returns_spans():
    spans = [CodeSpan("a.py", 1, 1)]
    out, bound = DeepRunner(Settings()).run(lambda: list(spans), DeepBudget(Settings()))
    assert out == spans
    assert bound is None


def test_runner_surfaces_truncated_bound_from_budget():
    settings = Settings(deep_token_ceiling=10)
    budget = DeepBudget(settings)
    gathered = [CodeSpan("a.py", 1, 1)]

    def target():
        budget.charge_tokens(999)  # trips "tokens" (cooperative return of partial)
        return gathered

    out, bound = DeepRunner(settings).run(target, budget)
    assert out == gathered
    assert bound == "tokens"


def test_runner_catches_budget_exceeded_returns_bound():
    settings = Settings(deep_max_tool_calls=0)
    budget = DeepBudget(settings)

    def target():
        if not budget.charge_tool_call():
            raise DeepBudgetExceeded("tool-calls")
        return [CodeSpan("a.py", 1, 1)]

    out, bound = DeepRunner(settings).run(target, budget)
    assert bound == "tool-calls"  # never a DeepUnavailable


# --- tasks 16/17: DeepEngine (self-seed, dual surface, typed-only failure) ---


class _FakeDeepBackend:
    def __init__(self, *, returns=None, raises=None, order=None):
        self.returns = returns or []
        self.raises = raises
        self.order = order
        self.calls = []

    def run(self, query, seed, tools):
        if self.order is not None:
            self.order.append("backend")
        self.calls.append((query, list(seed), tools))
        if self.raises is not None:
            raise self.raises
        return list(self.returns)


def _engine(tmp_path, backend, *, seed=None, seed_fn=None, settings=None):
    from harpyja.deep.engine import DeepEngine

    settings = settings or Settings()
    if seed_fn is None:
        def seed_fn(_query):
            return list(seed or [])

    return DeepEngine(
        backend,
        seed_fn,
        DeepRunner(settings),
        settings,
        str(tmp_path),
        make_tools=lambda budget: {},
    )


def test_deep_engine_seeds_before_backend(tmp_path):
    order = []

    def seed_fn(_q):
        order.append("seed")
        return []

    backend = _FakeDeepBackend(order=order)
    _engine(tmp_path, backend, seed_fn=seed_fn).run("q")
    assert order == ["seed", "backend"]


def test_deep_engine_passes_top_n_seed_hints(tmp_path):
    spans = [CodeSpan(f"f{i}.py", i, i) for i in range(1, 11)]
    backend = _FakeDeepBackend()
    _engine(tmp_path, backend, seed=spans, settings=Settings(deep_seed_top_n=5)).run("q")
    _query, hints, _tools = backend.calls[0]
    assert hints == spans[:5]


def test_deep_engine_seed_precondition_error_propagates(tmp_path):
    from harpyja.symbols.ripgrep import RipgrepMissingError

    def seed_fn(_q):
        raise RipgrepMissingError("rg not found")

    backend = _FakeDeepBackend()
    with pytest.raises(RipgrepMissingError):
        _engine(tmp_path, backend, seed_fn=seed_fn).run("q")
    assert backend.calls == []  # backend never reached


def test_deep_engine_search_returns_normalized_codespans(tmp_path):
    (tmp_path / "real.py").write_text("a\nb\nc\n", encoding="utf-8")
    backend = _FakeDeepBackend(
        returns=[
            CodeSpan("real.py", 1, 2),
            CodeSpan("../escape.py", 1, 1),  # outside repo → dropped
            CodeSpan("nope.py", 1, 1),  # nonexistent → dropped
        ]
    )
    out = _engine(tmp_path, backend).search("q")
    assert [(c.path, c.start_line, c.end_line) for c in out] == [("real.py", 1, 2)]


def test_deep_engine_run_returns_citations_and_no_truncation(tmp_path):
    (tmp_path / "real.py").write_text("a\nb\nc\n", encoding="utf-8")
    backend = _FakeDeepBackend(returns=[CodeSpan("real.py", 1, 1)])
    citations, bound = _engine(tmp_path, backend).run("q")
    assert [c.path for c in citations] == ["real.py"]
    assert bound is None


def test_deep_engine_run_surfaces_truncated_bound(tmp_path):
    backend = _FakeDeepBackend(raises=DeepBudgetExceeded("tokens"))
    citations, bound = _engine(tmp_path, backend).run("q")
    assert bound == "tokens"  # not a DeepUnavailable


def test_deep_engine_raises_deep_unavailable_on_typed_infra_failure(tmp_path):
    backend = _FakeDeepBackend(raises=DeepUnavailable(RLM_DOWN))
    with pytest.raises(DeepUnavailable):
        _engine(tmp_path, backend).run("q")


def test_deep_engine_weak_or_zero_output_not_unavailable(tmp_path):
    backend = _FakeDeepBackend(returns=[])  # honest empty Tier-2 result
    citations, bound = _engine(tmp_path, backend).run("q")
    assert citations == []
    assert bound is None  # NOT a DeepUnavailable, NOT a fallback trigger


# --- tasks 18/19: RlmBackend (dspy seam: assert_local first, no hard import, fresh per request) ---


class _Prediction:
    def __init__(self, answer):
        self.answer = answer


class _FakeRlm:
    def __init__(self, settings, tools, answer):
        self.settings = settings
        self.tools = tools
        self._answer = answer

    def __call__(self, query):
        return _Prediction(self._answer)


def test_rlm_backend_module_imports_without_dspy():
    import importlib

    mod = importlib.import_module("harpyja.deep.rlm")
    assert hasattr(mod, "RlmBackend")  # no top-level `import dspy` broke this


def test_rlm_backend_parses_citations_from_answer(tmp_path):
    from harpyja.deep.rlm import RlmBackend

    def factory(settings, tools):
        return _FakeRlm(settings, tools, answer="see auth.py:10-12 and util.py:3")

    backend = RlmBackend(Settings(), rlm_factory=factory, assert_local=lambda *a, **k: None)
    out = backend.run("find auth", [CodeSpan("seed.py", 2, 2)], {})
    assert (out[0].path, out[0].start_line, out[0].end_line) == ("auth.py", 10, 12)
    assert (out[1].path, out[1].start_line, out[1].end_line) == ("util.py", 3, 3)


def test_rlm_backend_asserts_local_before_building_lm():
    from harpyja.deep.rlm import RlmBackend

    order = []

    def assert_local(endpoint, **kw):
        order.append(("assert_local", endpoint))

    def factory(settings, tools):
        order.append(("factory",))
        return _FakeRlm(settings, tools, answer="")

    RlmBackend(
        Settings(lm_api_base="http://127.0.0.1:11434/v1"),
        rlm_factory=factory,
        assert_local=assert_local,
    ).run("q", [], {})
    assert order[0] == ("assert_local", "http://127.0.0.1:11434/v1")  # endpoint checked first
    assert order[1] == ("factory",)


def test_rlm_backend_airgap_blocks_before_factory():
    from harpyja.deep.rlm import RlmBackend
    from harpyja.gateway.gateway import AirGapError

    def assert_local(endpoint, **kw):
        raise AirGapError("non-loopback")

    def factory(settings, tools):  # pragma: no cover - must never run
        raise AssertionError("RLM built despite a non-loopback endpoint")

    with pytest.raises(AirGapError):
        RlmBackend(Settings(), rlm_factory=factory, assert_local=assert_local).run("q", [], {})


def test_rlm_backend_fresh_instance_per_request():
    from harpyja.deep.rlm import RlmBackend

    instances = []

    def factory(settings, tools):
        rlm = _FakeRlm(settings, tools, answer="")
        instances.append(rlm)
        return rlm

    backend = RlmBackend(Settings(), rlm_factory=factory, assert_local=lambda *a, **k: None)
    backend.run("a", [], {})
    backend.run("b", [], {})
    assert len(instances) == 2  # not thread-safe → fresh RLM per request


# --- spec 0014 (P3): AdapterParseError → DeepUnavailable(parse-error) seam ---


class _RaisingRlm:
    """An rlm whose forward call raises — models a dspy adapter parse failure
    (or, for the narrow-catch guard, an unrelated exception)."""

    def __init__(self, settings, tools, exc):
        self._exc = exc

    def __call__(self, query):
        raise self._exc


def _adapter_parse_error():
    # AdapterParseError.__init__ needs a real Signature + heavy args; bypass it.
    from dspy.utils.exceptions import AdapterParseError

    return AdapterParseError.__new__(AdapterParseError)


def test_rlm_backend_adapter_parse_error_maps_to_deep_unavailable():
    from harpyja.deep.rlm import RlmBackend

    err = _adapter_parse_error()

    def factory(settings, tools):
        return _RaisingRlm(settings, tools, err)

    backend = RlmBackend(Settings(), rlm_factory=factory, assert_local=lambda *a, **k: None)
    with pytest.raises(DeepUnavailable) as excinfo:
        backend.run("q", [], {})
    # Raw AdapterParseError does NOT escape (no crash); it maps to the typed cause.
    assert excinfo.value.cause == PARSE_ERROR


def test_rlm_backend_parse_error_preserves_cause():
    from harpyja.deep.rlm import RlmBackend

    err = _adapter_parse_error()

    def factory(settings, tools):
        return _RaisingRlm(settings, tools, err)

    backend = RlmBackend(Settings(), rlm_factory=factory, assert_local=lambda *a, **k: None)
    try:
        backend.run("q", [], {})
    except DeepUnavailable as de:
        assert de.__cause__ is err  # raise ... from err preserves the foreign cause


def test_rlm_backend_unrelated_exception_not_swallowed():
    from harpyja.deep.rlm import RlmBackend

    def factory(settings, tools):
        return _RaisingRlm(settings, tools, RuntimeError("bad config"))

    backend = RlmBackend(Settings(), rlm_factory=factory, assert_local=lambda *a, **k: None)
    # Narrow catch: an unrelated exception is NOT laundered into parse-error.
    with pytest.raises(RuntimeError):
        backend.run("q", [], {})


def test_rlm_backend_weak_answer_stays_result():
    from harpyja.deep.rlm import RlmBackend

    def factory(settings, tools):
        return _FakeRlm(settings, tools, answer="no citations here")  # well-formed, weak

    backend = RlmBackend(Settings(), rlm_factory=factory, assert_local=lambda *a, **k: None)
    out = backend.run("q", [], {})
    # A successful run with weak/empty citations is an honest Tier-2 result, NOT a degrade.
    assert out == []


def test_rlm_backend_module_has_no_toplevel_dspy_import():
    import ast
    import pathlib

    import harpyja.deep.rlm as rlm_mod

    src = pathlib.Path(rlm_mod.__file__).read_text(encoding="utf-8")
    tree = ast.parse(src)
    # Only MODULE-LEVEL imports matter: a lazy `from dspy...` inside a function
    # body is the sanctioned pattern (and is what the seam uses).
    for node in tree.body:
        if isinstance(node, ast.Import):
            assert all(not n.name.startswith("dspy") for n in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert not (node.module or "").startswith("dspy")
