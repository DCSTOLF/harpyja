"""Tests for symbols.jsonl + symbols.meta.json I/O and integrity (AC1, AC7, AC8).

The artifact is treated as **untrusted derived input**: it is self-verifying via a
`record_count` + `content_digest` in the sidecar, so a clean newline truncation or a
records-first/meta-last crash residue both force a rebuild.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from harpyja.symbols.extract import SymbolRecord
from harpyja.symbols.symbols_io import (
    META_NAME,
    SYMBOLS_NAME,
    load_symbols_or_none,
    needs_rebuild,
    read_symbols,
    write_symbols,
)

_IDENT = {"schema_version": 1, "tree-sitter": "0.25.2", "tree-sitter-python": "0.25.0"}


def _rec(name, kind="function", parent=None, lang="python", start=1, end=1, path="m.py"):
    return SymbolRecord(
        path=path,
        language=lang,
        name=name,
        kind=kind,
        parent=parent,
        start_line=start,
        end_line=end,
    )


def _records():
    return [
        _rec("zeta", start=10, end=12),
        _rec("alpha", start=1, end=3),
        _rec("M", kind="method", parent="C", start=5, end=6),
    ]


# --- deterministic write/read + sidecar (AC1, AC7) ---


def test_write_symbols_jsonl_fixed_key_order(tmp_path: Path):
    write_symbols(tmp_path, [_rec("foo")], engine_ident=_IDENT)
    first = (tmp_path / SYMBOLS_NAME).read_text().splitlines()[0]
    obj_keys = list(json.loads(first).keys())
    assert obj_keys == ["path", "language", "name", "kind", "parent", "start_line", "end_line"]


def test_symbols_ordered_by_full_total_key_path_start_end_kind_name(tmp_path: Path):
    write_symbols(tmp_path, _records(), engine_ident=_IDENT)
    lines = [json.loads(line) for line in (tmp_path / SYMBOLS_NAME).read_text().splitlines()]
    keys = [(o["path"], o["start_line"], o["end_line"], o["kind"], o["name"]) for o in lines]
    assert keys == sorted(keys)


def test_two_writes_byte_identical_with_colliding_constants_a1_b2(tmp_path: Path):
    colliding = [
        _rec("A", kind="constant", start=1, end=1),
        _rec("B", kind="constant", start=1, end=1),
    ]
    write_symbols(tmp_path, colliding, engine_ident=_IDENT)
    first = (tmp_path / SYMBOLS_NAME).read_bytes()
    meta_first = (tmp_path / META_NAME).read_bytes()
    write_symbols(tmp_path, list(reversed(colliding)), engine_ident=_IDENT)
    assert (tmp_path / SYMBOLS_NAME).read_bytes() == first
    assert (tmp_path / META_NAME).read_bytes() == meta_first


def test_write_atomic_same_dir_temp_then_os_replace(tmp_path: Path, monkeypatch):
    seen = []
    real = os.replace

    def spy(src, dst):
        seen.append((Path(src).parent, Path(dst).parent))
        return real(src, dst)

    monkeypatch.setattr("harpyja.symbols.symbols_io.os.replace", spy)
    write_symbols(tmp_path, [_rec("foo")], engine_ident=_IDENT)
    assert seen, "os.replace was not used"
    for src_dir, dst_dir in seen:
        assert src_dir == dst_dir  # temp lives in the destination dir


def test_meta_sidecar_fixed_key_order_and_stable_sorted_languages(tmp_path: Path):
    recs = [_rec("g", lang="go"), _rec("p", lang="python")]
    write_symbols(tmp_path, recs, engine_ident=_IDENT)
    meta = json.loads((tmp_path / META_NAME).read_text())
    assert meta["languages"] == ["go", "python"]  # stable-sorted
    assert meta["record_count"] == 2
    assert meta["content_digest"].startswith("sha256:")
    assert meta["engine_identity"] == _IDENT


def test_meta_languages_is_distinct_langs_with_at_least_one_record(tmp_path: Path):
    recs = [_rec("p1", lang="python"), _rec("p2", lang="python")]
    write_symbols(tmp_path, recs, engine_ident=_IDENT)
    meta = json.loads((tmp_path / META_NAME).read_text())
    assert meta["languages"] == ["python"]


def test_read_symbols_roundtrip(tmp_path: Path):
    recs = _records()
    write_symbols(tmp_path, recs, engine_ident=_IDENT)
    back = read_symbols(tmp_path)
    assert {(r.name, r.kind, r.parent, r.start_line) for r in back} == {
        (r.name, r.kind, r.parent, r.start_line) for r in recs
    }


# --- self-verifying integrity → rebuild (AC8) ---


def test_needs_rebuild_when_jsonl_missing_or_unreadable(tmp_path: Path):
    assert needs_rebuild(tmp_path, _IDENT) is True


def test_needs_rebuild_when_jsonl_truncated_midline_non_json(tmp_path: Path):
    write_symbols(tmp_path, _records(), engine_ident=_IDENT)
    p = tmp_path / SYMBOLS_NAME
    p.write_text(p.read_text() + '{"path": "x", "broken"\n')
    assert needs_rebuild(tmp_path, _IDENT) is True


def test_needs_rebuild_when_clean_newline_truncation_count_mismatch(tmp_path: Path):
    write_symbols(tmp_path, _records(), engine_ident=_IDENT)
    p = tmp_path / SYMBOLS_NAME
    lines = p.read_text().splitlines()
    p.write_text("\n".join(lines[:-1]) + "\n")  # drop one whole valid line
    assert needs_rebuild(tmp_path, _IDENT) is True


def test_needs_rebuild_when_content_digest_mismatch(tmp_path: Path):
    write_symbols(tmp_path, _records(), engine_ident=_IDENT)
    p = tmp_path / SYMBOLS_NAME
    # Rewrite a record's content keeping the same line count (in-place bit flip).
    lines = p.read_text().splitlines()
    obj = json.loads(lines[0])
    obj["name"] = obj["name"] + "X"
    lines[0] = json.dumps(obj, ensure_ascii=False)
    p.write_text("\n".join(lines) + "\n")
    assert needs_rebuild(tmp_path, _IDENT) is True


def test_needs_rebuild_when_meta_missing_but_jsonl_present(tmp_path: Path):
    write_symbols(tmp_path, _records(), engine_ident=_IDENT)
    (tmp_path / META_NAME).unlink()
    assert needs_rebuild(tmp_path, _IDENT) is True


def test_needs_rebuild_when_engine_identity_mismatch(tmp_path: Path):
    write_symbols(tmp_path, _records(), engine_ident=_IDENT)
    bumped = dict(_IDENT, **{"tree-sitter-python": "0.26.0"})
    assert needs_rebuild(tmp_path, bumped) is True


def test_needs_rebuild_on_records_first_meta_last_crash_residue(tmp_path: Path):
    # Simulate: records committed (new generation), meta still the OLD generation.
    write_symbols(tmp_path, _records(), engine_ident=_IDENT)
    stale_meta = (tmp_path / META_NAME).read_bytes()
    write_symbols(tmp_path, [_rec("only_one")], engine_ident=_IDENT)  # new records
    (tmp_path / META_NAME).write_bytes(stale_meta)  # but a crash left the old meta
    assert needs_rebuild(tmp_path, _IDENT) is True


def test_no_rebuild_when_records_and_meta_intact(tmp_path: Path):
    write_symbols(tmp_path, _records(), engine_ident=_IDENT)
    assert needs_rebuild(tmp_path, _IDENT) is False
    assert load_symbols_or_none(tmp_path, _IDENT) is not None


def test_load_symbols_or_none_returns_none_on_integrity_failure(tmp_path: Path):
    assert load_symbols_or_none(tmp_path, _IDENT) is None
