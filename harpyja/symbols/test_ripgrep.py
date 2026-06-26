"""RED (task 24/26): bounded literal ripgrep search → CodeSpans (AC8, AC9)."""

import json

import pytest

from harpyja.config.settings import Settings
from harpyja.server.types import CodeSpan
from harpyja.symbols.ripgrep import RipgrepEngine, RipgrepMissingError

_RG_PRESENT = lambda _name: "/usr/bin/rg"  # noqa: E731 - test stub


def _match_line(path, line):
    return json.dumps(
        {
            "type": "match",
            "data": {
                "path": {"text": path},
                "lines": {"text": "some matching line\n"},
                "line_number": line,
                "submatches": [{"match": {"text": "q"}, "start": 0, "end": 1}],
            },
        }
    )


def _runner_returning(*lines):
    captured = {}

    def runner(args):
        captured["args"] = args
        return "\n".join(lines) + "\n"

    return runner, captured


def test_search_returns_codespans_for_literal_match():
    runner, _ = _runner_returning(_match_line("a.py", 12))
    engine = RipgrepEngine(Settings(), rg_runner=runner, which=_RG_PRESENT)
    spans = engine.search("q", scope=".")
    assert spans == [CodeSpan(path="a.py", start_line=12, end_line=12)]


def test_search_treats_query_as_literal_by_default():
    runner, captured = _runner_returning(_match_line("a.py", 1))
    engine = RipgrepEngine(Settings(), rg_runner=runner, which=_RG_PRESENT)
    engine.search("a.b*c", scope=".")
    assert "--fixed-strings" in captured["args"]


def test_search_caps_at_search_max_matches():
    lines = [_match_line("a.py", n) for n in range(1, 6)]
    runner, _ = _runner_returning(*lines)
    settings = Settings(search_max_matches=2)
    engine = RipgrepEngine(settings, rg_runner=runner, which=_RG_PRESENT)
    assert len(engine.search("q", scope=".")) == 2


def test_search_caps_at_search_max_files():
    lines = [_match_line(f"f{n}.py", 1) for n in range(1, 5)]
    runner, _ = _runner_returning(*lines)
    settings = Settings(search_max_files=2)
    engine = RipgrepEngine(settings, rg_runner=runner, which=_RG_PRESENT)
    spans = engine.search("q", scope=".")
    assert len({s.path for s in spans}) <= 2


def test_search_passes_rg_chunk_size():
    runner, captured = _runner_returning(_match_line("a.py", 1))
    settings = Settings(rg_chunk_size=999)
    engine = RipgrepEngine(settings, rg_runner=runner, which=_RG_PRESENT)
    engine.search("q", scope=".")
    assert any("999" in str(a) for a in captured["args"])


def test_search_missing_rg_raises_typed_actionable_error():
    runner, _ = _runner_returning()
    engine = RipgrepEngine(Settings(), rg_runner=runner, which=lambda _n: None)
    with pytest.raises(RipgrepMissingError) as exc:
        engine.search("q", scope=".")
    assert "ripgrep" in str(exc.value).lower() or "rg" in str(exc.value).lower()
