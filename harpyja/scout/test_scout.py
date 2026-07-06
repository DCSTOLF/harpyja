"""Scout backend + engine (Tier 1).

Drives the self-seeding `ScoutEngine`, its normalization of backend output, and the
tool whitelist — against a fake backend, with no live model. (Spec 0025 retired the
FastContext adapter; the explorer backend is exercised in `test_explorer_backend.py`.)
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


# Spec 0025: the FastContext tool whitelist (`build_tool_whitelist`) and the
# `FastContextBackend` delegation test were removed with the retired adapter. The
# explorer backend + its `build_explorer_tools` suite are covered in
# `test_explorer_backend.py` / `test_explorer_tools.py`.


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


def test_scout_engine_out_of_repo_cite_drops_no_recovery(tmp_path):
    # Spec 0025: suffix recovery is REMOVED — the same out-of-repo cite that used to
    # recover at the engine seam now honestly DROPS, even with a file_set present.
    # The tally is still carried; recovered_* read zero.
    repo, fs = _flask_repo(tmp_path)
    backend = _RecordingBackend(
        [CodeSpan("/pallets/flask/src/flask/blueprints.py", None, None)]
    )
    engine = ScoutEngine(backend, _seed_of(), Settings(), str(repo), file_set=fs)
    out = engine.search("q")
    assert out == []
    t = engine.last_tally
    assert (t.recovered_filelevel, t.recovered_spanned, t.dropped) == (0, 0, 1)
    assert t.recovered_filelevel_paths == ()


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


# --- Spec 0025 (T3/T4, AC3): the engine surfaces the backend's turns-used seam ---


class _TurnsBackend:
    """A fake backend that exposes the explorer's per-run `last_turns_used` seam."""

    def __init__(self, turns, returns=None):
        self._turns = turns
        self.returns = returns or []
        self.last_turns_used = None

    def run(self, query, seed):
        self.last_turns_used = self._turns
        return list(self.returns)


def test_scout_engine_surfaces_last_turns_used(tmp_path):
    backend = _TurnsBackend(4)
    engine = ScoutEngine(backend, _seed_of(), Settings(), str(tmp_path))
    engine.search("q")
    assert engine.last_turns_used == 4


def test_scout_engine_last_turns_used_reset_per_search(tmp_path):
    backend = _TurnsBackend(4)
    engine = ScoutEngine(backend, _seed_of(), Settings(), str(tmp_path))
    engine.search("q")
    backend._turns = 1
    engine.search("q2")
    assert engine.last_turns_used == 1  # reset per call, not sticky


def test_scout_engine_last_turns_used_none_for_backend_without_seam(tmp_path):
    # getattr-guarded: a backend lacking the seam yields None, never AttributeError.
    backend = _RecordingBackend()
    engine = ScoutEngine(backend, _seed_of(), Settings(), str(tmp_path))
    engine.search("q")
    assert engine.last_turns_used is None


# --- Spec 0025 (T7/T8, AC5): last_tally survives suffix-recovery removal ---


def test_last_tally_still_populated_after_recovery_removed(tmp_path):
    # The shared shape-tally is KEPT (its live consumers — runner, locate_probe, the
    # 0022 locate-accuracy diagnostic — still read it); only recovery is removed, so
    # the recovered_* counts read zero.
    (tmp_path / "real.py").write_text("a = 1\nb = 2\n", encoding="utf-8")
    backend = _RecordingBackend([CodeSpan("real.py", 1, 2)])
    engine = ScoutEngine(backend, _seed_of(), Settings(), str(tmp_path))
    out = engine.search("q")
    assert [(c.path, c.start_line, c.end_line) for c in out] == [("real.py", 1, 2)]
    t = engine.last_tally
    assert t is not None
    assert (t.spanned, t.dropped) == (1, 0)
    assert (t.recovered_spanned, t.recovered_filelevel) == (0, 0)
