"""RED (T7, AC6): the tool-call-native `submit_citations` terminal action.

The model ends the loop by calling `submit_citations` with STRUCTURED args (not by
emitting free text to be regexed — the FastContext-era `<final_answer>` grammar is
retired). Its args validate under a STRICT schema: unknown/extra fields — including
any diagnosis-shaped field — fail schema (the enforceable form of the
locator-not-diagnoser guard). Semantically bad refs (out-of-repo / nonexistent /
over-budget / malformed range) are DROPPED by the existing `normalize_spans`, never
propagated. An empty well-formed submission is honest-empty, not an error.
"""

import inspect

import pytest

from harpyja.config.settings import Settings
from harpyja.orchestrator.format import format_citations
from harpyja.scout.submit import SubmitCitationsSchemaError, submit_citations
from harpyja.server.types import CodeSpan


def _file(tmp_path, rel, n=50):
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(f"line {i}" for i in range(1, n + 1)) + "\n", encoding="utf-8")
    return p


def test_submit_citations_returns_normalized_codespans(tmp_path):
    _file(tmp_path, "a.py", n=50)
    out = submit_citations(
        [{"path": "a.py", "start_line": 3, "end_line": 5}], str(tmp_path), Settings()
    )
    assert out.spans == [CodeSpan(path="a.py", start_line=3, end_line=5)]


def test_submit_citations_keeps_file_level_ref(tmp_path):
    _file(tmp_path, "a.py")
    out = submit_citations([{"path": "a.py"}], str(tmp_path), Settings())
    assert out.spans == [CodeSpan(path="a.py", start_line=None, end_line=None)]


def test_submit_citations_drops_out_of_repo_nonexistent_over_budget_malformed(tmp_path):
    _file(tmp_path, "real.py", n=10)
    out = submit_citations(
        [
            {"path": "../../etc/passwd", "start_line": 1, "end_line": 1},  # out-of-repo
            {"path": "ghost.py", "start_line": 1, "end_line": 1},          # nonexistent
            {"path": "real.py", "start_line": 9, "end_line": 2},           # inverted range
            {"path": "real.py", "start_line": 999, "end_line": 1000},      # out-of-range
        ],
        str(tmp_path),
        Settings(),
    )
    assert out.spans == []  # every bad ref dropped, never propagated


def test_submit_citations_strict_schema_rejects_unknown_field(tmp_path):
    with pytest.raises(SubmitCitationsSchemaError):
        submit_citations(
            [{"path": "a.py", "start_line": 1, "end_line": 1, "confidence": 0.9}],
            str(tmp_path),
            Settings(),
        )


def test_submit_citations_diagnosis_shaped_field_fails_schema(tmp_path):
    # A locator does not diagnose: a root_cause/fix/explanation-style field is not a
    # sanctioned citation field, so the strict schema rejects it.
    for bad in ("root_cause", "fix", "explanation", "rationale", "diagnosis"):
        with pytest.raises(SubmitCitationsSchemaError):
            submit_citations(
                [{"path": "a.py", "start_line": 1, "end_line": 1, bad: "text"}],
                str(tmp_path),
                Settings(),
            )


def test_submit_citations_has_no_repo_read_capability():
    # The terminal action is a pure validator: it takes citations + repo_root +
    # settings and NOTHING that reads the repo (no tool bundle, no grep/glob/read).
    params = set(inspect.signature(submit_citations).parameters)
    assert params == {"citations", "repo_root", "settings"}


def test_submit_citations_empty_is_honest_empty_not_error(tmp_path):
    assert submit_citations([], str(tmp_path), Settings()).spans == []


def test_submit_citations_spans_reach_source_tier_1_via_engine_path(tmp_path):
    # The action returns plain CodeSpans (unstamped); the =1 stamp happens downstream
    # in the UNCHANGED orchestrator path via format_citations(..., source_tier=1).
    _file(tmp_path, "a.py", n=50)
    spans = submit_citations(
        [{"path": "a.py", "start_line": 1, "end_line": 2}], str(tmp_path), Settings()
    ).spans
    cits = format_citations(spans, lambda p: 1.0, 8, source_tier=1)
    assert cits and all(c.source_tier == 1 for c in cits)


# --- Spec 0033: the astropy/django shapes end-to-end (AC3) ---

from harpyja.scout.explorer_tools import build_explorer_tools  # noqa: E402
from harpyja.symbols.ripgrep import RipgrepEngine  # noqa: E402
from harpyja.symbols.test_ripgrep import _match_line, _runner_returning  # noqa: E402


def _grown_file(tmp_path, rel, n=900):
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(f"line {i}" for i in range(1, n + 1)) + "\n", encoding="utf-8")
    return p


def test_astropy_scoped_grep_hit_survives_submit(tmp_path):
    """AC3: a scoped-grep hit, cited verbatim by the model, SURVIVES submit's
    normalize pass — the 0032 astropy found-then-dropped shape is closed."""
    _grown_file(tmp_path, "astropy/modeling/core.py")
    runner, _ = _runner_returning(_match_line("modeling/core.py", 812))
    engine = RipgrepEngine(Settings(), rg_runner=runner, which=lambda _n: "/usr/bin/rg")
    tools = build_explorer_tools(str(tmp_path), Settings(), search_engine=engine)

    hit = tools["grep"]("separability matrix", scope="astropy/")[0]
    out = submit_citations(
        [{"path": hit.path, "start_line": hit.start_line, "end_line": hit.end_line}],
        str(tmp_path),
        Settings(),
    )
    assert [s.path for s in _spans_of_submit(out)] == ["astropy/modeling/core.py"]


def test_django_unscoped_shape_unchanged(tmp_path):
    """AC3 control: the unscoped (repo-root) grep shape survives, byte-identical."""
    _grown_file(tmp_path, "django/db/models/query.py")
    runner, _ = _runner_returning(_match_line("django/db/models/query.py", 693))
    engine = RipgrepEngine(Settings(), rg_runner=runner, which=lambda _n: "/usr/bin/rg")
    tools = build_explorer_tools(str(tmp_path), Settings(), search_engine=engine)

    hit = tools["grep"]("in_bulk")[0]
    out = submit_citations(
        [{"path": hit.path, "start_line": hit.start_line, "end_line": hit.end_line}],
        str(tmp_path),
        Settings(),
    )
    assert [s.path for s in _spans_of_submit(out)] == ["django/db/models/query.py"]


def _spans_of_submit(result):
    """Shape-tolerant read: list today, SubmitResult.spans after 0033 T7."""
    return getattr(result, "spans", result)


# --- Spec 0033: submitted-vs-surviving counted AT the submit seam (AC5) ---


def test_submit_citations_returns_result_with_counts(tmp_path):
    """AC5: found-then-dropped is (submitted=1, surviving=0); a surviving ref is
    (1, 1). The counts live where the drop happens — the ONE submit-side
    normalize pass."""
    from harpyja.scout.submit import SubmitResult

    # Found-then-dropped: a scope-relative-style ref that does not resolve in-repo.
    dropped = submit_citations(
        [{"path": "modeling/core.py", "start_line": 812, "end_line": 812}],
        str(tmp_path),
        Settings(),
    )
    assert isinstance(dropped, SubmitResult)
    assert dropped.spans == []
    assert (dropped.submitted, dropped.surviving) == (1, 0)

    # Surviving: a real in-repo ref.
    p = tmp_path / "a.py"
    p.write_text("x\ny\n", encoding="utf-8")
    kept = submit_citations(
        [{"path": "a.py", "start_line": 1, "end_line": 2}], str(tmp_path), Settings()
    )
    assert (kept.submitted, kept.surviving) == (1, 1)
    assert [s.path for s in kept.spans] == ["a.py"]


def test_submit_citations_honest_empty_counts_zero_zero(tmp_path):
    """AC5: honest-empty is (0, 0) — structurally distinguishable from
    found-then-dropped (1, 0)."""
    out = submit_citations([], str(tmp_path), Settings())
    assert (out.submitted, out.surviving) == (0, 0)
    assert out.spans == []


def test_submit_citations_single_production_caller():
    """AC5: the ONLY non-test production caller of submit_citations is the
    ExplorerBackend submit closure — an ast assertion, not a prose grep."""
    import ast
    from pathlib import Path as _P

    root = _P(__file__).resolve().parents[1]  # harpyja/
    callers = set()
    for py in root.rglob("*.py"):
        if py.name.startswith("test_") or py.name == "submit.py":
            continue
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                fn = node.func
                name = fn.id if isinstance(fn, ast.Name) else getattr(fn, "attr", None)
                if name == "submit_citations":
                    callers.add(str(py.relative_to(root)))
    assert callers == {"scout/explorer_backend.py"}


def test_submit_citations_pure_seam_unchanged_by_confirm(tmp_path):
    # Spec 0046: confirm-before-submit lives in the BACKEND seam, never inside
    # submit_citations — the terminal action stays a pure validate+normalize with
    # NO query/read_span/confirmation surface (its args are unchanged).
    import inspect

    from harpyja.scout.submit import submit_citations as sc

    params = list(inspect.signature(sc).parameters)
    assert params == ["citations", "repo_root", "settings"]
    src = inspect.getsource(sc)
    assert "confirm" not in src and "ConfirmationOutcome" not in src
