"""RED (tasks 11/13/15/17): Scout backend + engine (Tier 1).

Drives the self-seeding `ScoutEngine`, its normalization of backend output, the
exact FastContext tool whitelist, and the `FastContextBackend` delegation — all
against a fake backend / injected client, with no live model.
"""

import pytest

from harpyja.config.settings import Settings
from harpyja.scout.engine import ScoutEngine
from harpyja.server.types import CodeSpan
from harpyja.symbols.ripgrep import RipgrepMissingError


class _RecordingBackend:
    def __init__(self, returns=None):
        self.returns = returns or []
        self.calls = []

    def run(self, query, seed):
        self.calls.append((query, list(seed)))
        return list(self.returns)


def _seed_of(*spans):
    def seed_fn(query):
        return list(spans)

    return seed_fn


# --- task 11: self-seed ordering + top-N hints + seed error propagation ---


def test_scout_engine_seeds_before_backend(tmp_path):
    order = []

    def seed_fn(query):
        order.append("seed")
        return []

    backend = _RecordingBackend()
    original_run = backend.run

    def run(query, seed):
        order.append("backend")
        return original_run(query, seed)

    backend.run = run
    engine = ScoutEngine(backend, seed_fn, Settings(), str(tmp_path))
    engine.search("q")
    assert order == ["seed", "backend"]


def test_scout_engine_passes_top_n_hints(tmp_path):
    spans = [CodeSpan(path=f"f{i}.py", start_line=i, end_line=i) for i in range(1, 11)]
    backend = _RecordingBackend()
    engine = ScoutEngine(backend, _seed_of(*spans), Settings(scout_seed_top_n=5), str(tmp_path))
    engine.search("q")
    _query, hints = backend.calls[0]
    assert len(hints) == 5
    assert hints == spans[:5]  # formatter rank order preserved


def test_scout_engine_seed_precondition_error_propagates(tmp_path):
    def seed_fn(query):
        raise RipgrepMissingError("rg not found")

    backend = _RecordingBackend()
    engine = ScoutEngine(backend, seed_fn, Settings(), str(tmp_path))
    with pytest.raises(RipgrepMissingError):
        engine.search("q")
    assert backend.calls == []  # backend never reached


# --- task 13: engine normalizes backend output ---


def test_scout_engine_normalizes_hostile_output(tmp_path):
    (tmp_path / "real.py").write_text("a\nb\nc\n", encoding="utf-8")
    backend = _RecordingBackend(
        returns=[
            CodeSpan(path="real.py", start_line=1, end_line=2),
            CodeSpan(path="../escape.py", start_line=1, end_line=1),  # outside repo
            CodeSpan(path="nope.py", start_line=1, end_line=1),  # nonexistent
        ]
    )
    engine = ScoutEngine(backend, _seed_of(), Settings(), str(tmp_path))
    out = engine.search("q")
    assert [(c.path, c.start_line, c.end_line) for c in out] == [("real.py", 1, 2)]


# --- task 15: exact tool whitelist ---


def test_build_tool_whitelist_exact_set():
    from harpyja.scout.tools import build_tool_whitelist

    client = object()
    read, glob, grep = object(), object(), object()
    tools = build_tool_whitelist(client, read=read, glob=glob, grep=grep)
    assert set(tools) == {"read", "glob", "grep", "model"}
    assert tools["model"] is client
    assert tools["read"] is read and tools["glob"] is glob and tools["grep"] is grep


# --- task 17: FastContextBackend delegates to an injected client ---


def test_fastcontext_backend_delegates_to_injected_client():
    from harpyja.scout.fastcontext import FastContextBackend

    seen = {}

    def fake_client(query, seed, tools):
        seen["query"] = query
        seen["seed"] = list(seed)
        seen["tools"] = tools
        return [CodeSpan(path="x.py", start_line=1, end_line=1)]

    backend = FastContextBackend(
        client=fake_client,
        model_client=object(),
        read=object(),
        glob=object(),
        grep=object(),
    )
    seed = [CodeSpan(path="seed.py", start_line=2, end_line=2)]
    out = backend.run("find auth", seed)
    assert seen["query"] == "find auth"
    assert seen["seed"] == seed
    assert set(seen["tools"]) == {"read", "glob", "grep", "model"}
    assert out == [CodeSpan(path="x.py", start_line=1, end_line=1)]


# --- Spec 0011 (citation-shape): the Scout result carries the shape tally (AC17) ---


def test_scout_engine_exposes_fc_citation_tally(tmp_path):
    # AC17 (carrier): after search, the engine exposes the per-shape text-ref tally
    # — spanned (lined) vs filelevel (bare path, the root-cause signal) emitted by
    # the model, and dropped by normalize — as side-channel metadata the eval
    # harness reads. The returned list[CodeSpan] (orchestrator seam) is unchanged.
    (tmp_path / "real.py").write_text("a\nb\nc\n", encoding="utf-8")
    backend = _RecordingBackend(
        [
            CodeSpan("real.py", 1, 2),  # spanned, survives
            CodeSpan("real.py", None, None),  # file-level, survives
            CodeSpan("ghost.py", None, None),  # file-level, dropped (no such file)
        ]
    )
    engine = ScoutEngine(backend, _seed_of(), Settings(), str(tmp_path))
    out = engine.search("q")
    assert all(isinstance(c, CodeSpan) for c in out)  # seam unchanged
    tally = engine.last_tally
    assert (tally.spanned, tally.filelevel, tally.dropped) == (1, 2, 1)


# --- Spec 0012: suffix recovery threaded through the engine + tally ---


def _flask_repo(tmp_path):
    (tmp_path / "src" / "flask").mkdir(parents=True)
    (tmp_path / "src" / "flask" / "blueprints.py").write_text(
        "\n".join(f"line {i}" for i in range(1, 30)) + "\n", encoding="utf-8"
    )
    return tmp_path, frozenset({"src/flask/blueprints.py"})


def test_scout_tally_carries_recovered_counts(tmp_path):
    # AC4: an out-of-repo cite whose suffix recovers is kept and counted in the
    # recovered_* tally split by shape (file-level here).
    repo, fs = _flask_repo(tmp_path)
    backend = _RecordingBackend(
        [CodeSpan("/pallets/flask/src/flask/blueprints.py", None, None)]
    )
    engine = ScoutEngine(backend, _seed_of(), Settings(), str(repo), file_set=fs)
    out = engine.search("q")
    assert [c.path for c in out] == ["src/flask/blueprints.py"]
    t = engine.last_tally
    assert (t.recovered_filelevel, t.recovered_spanned, t.dropped) == (1, 0, 0)
    # AC5 support: the engine tally also carries the recovered file-level PATHS.
    assert t.recovered_filelevel_paths == ("src/flask/blueprints.py",)


def test_scout_engine_no_file_set_means_no_recovery(tmp_path):
    # AC2 degrade at the engine seam: no file set -> no recovery -> spec-0011 drop.
    repo, _fs = _flask_repo(tmp_path)
    backend = _RecordingBackend(
        [CodeSpan("/pallets/flask/src/flask/blueprints.py", None, None)]
    )
    engine = ScoutEngine(backend, _seed_of(), Settings(), str(repo))  # no file_set
    out = engine.search("q")
    assert out == []
    t = engine.last_tally
    assert (t.recovered_filelevel, t.recovered_spanned, t.dropped) == (0, 0, 1)
