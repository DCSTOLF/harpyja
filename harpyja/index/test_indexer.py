"""RED (task 20): incremental detection, pruning, rehash (AC2, AC3, AC5, AC6b)."""

import os

from harpyja.config.settings import Settings
from harpyja.index.indexer import index_repo
from harpyja.index.manifest import read_manifest


def _write(root, rel, content="x"):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


def _counting_hash():
    calls = []

    def hash_fn(path):
        calls.append(str(path))
        return "sha256:deadbeef"

    return hash_fn, calls


def _artifact_dir(repo):
    return repo / ".harpyja"


def test_index_unchanged_file_not_rehashed(tmp_path):
    _write(tmp_path, "a.py", "content")
    hash_fn, calls = _counting_hash()
    index_repo(tmp_path, Settings(), hash_fn=hash_fn)
    assert any(c.endswith("a.py") for c in calls)  # hashed on first pass
    calls.clear()
    index_repo(tmp_path, Settings(), hash_fn=hash_fn)  # unchanged
    assert not any(c.endswith("a.py") for c in calls)  # not re-hashed


def test_index_changed_size_triggers_rehash(tmp_path):
    f = _write(tmp_path, "a.py", "small")
    hash_fn, calls = _counting_hash()
    index_repo(tmp_path, Settings(), hash_fn=hash_fn)
    calls.clear()
    f.write_text("a much larger body of content", encoding="utf-8")
    index_repo(tmp_path, Settings(), hash_fn=hash_fn)
    assert any(c.endswith("a.py") for c in calls)


def test_index_changed_mtime_triggers_rehash(tmp_path):
    f = _write(tmp_path, "a.py", "12345")
    hash_fn, calls = _counting_hash()
    index_repo(tmp_path, Settings(), hash_fn=hash_fn)
    calls.clear()
    f.write_text("67890", encoding="utf-8")  # same size, different content
    os.utime(f, (1_000_000_000, 1_000_000_000))  # force a distinct mtime
    index_repo(tmp_path, Settings(), hash_fn=hash_fn)
    assert any(c.endswith("a.py") for c in calls)


def test_index_prunes_deleted_file_entry(tmp_path):
    a = _write(tmp_path, "a.py")
    _write(tmp_path, "b.py")
    index_repo(tmp_path, Settings())
    a.unlink()
    index_repo(tmp_path, Settings())
    paths = {e.path for e in read_manifest(_artifact_dir(tmp_path))}
    assert "a.py" not in paths
    assert "b.py" in paths


def test_index_rehash_ignores_mtime_size_gate(tmp_path):
    _write(tmp_path, "a.py", "content")
    hash_fn, calls = _counting_hash()
    index_repo(tmp_path, Settings(), hash_fn=hash_fn)
    calls.clear()
    index_repo(tmp_path, Settings(), hash_fn=hash_fn, rehash=True)  # unchanged but forced
    assert any(c.endswith("a.py") for c in calls)


def test_index_null_language_file_still_indexed(tmp_path):
    _write(tmp_path, "run", "#!/bin/sh\n")  # extensionless
    index_repo(tmp_path, Settings())
    entries = {e.path: e for e in read_manifest(_artifact_dir(tmp_path))}
    assert "run" in entries
    assert entries["run"].language is None


def test_index_result_shape_matches_spec(tmp_path):
    _write(tmp_path, "a.py")
    result = index_repo(tmp_path, Settings())
    d = result.to_dict()
    assert set(d.keys()) == {
        "files_indexed",
        "symbols_indexed",
        "languages",
        "elapsed_ms",
        "degraded",
    }
    assert d["symbols_indexed"] == 0
    assert d["degraded"] == []


def test_index_languages_sum_le_files_indexed(tmp_path):
    _write(tmp_path, "a.py")
    _write(tmp_path, "b.go")
    _write(tmp_path, "run")  # null-language: counted in files_indexed, not languages
    result = index_repo(tmp_path, Settings())
    assert sum(result.languages.values()) < result.files_indexed
    assert result.files_indexed == 3
    assert result.languages == {"python": 1, "go": 1}


# --- Wave 2: symbol extraction integration (AC1, AC3, AC5, AC6, AC4, AC8, AC16) ---

from harpyja.symbols.extract import ExtractResult  # noqa: E402
from harpyja.symbols.symbols_io import META_NAME, SYMBOLS_NAME, load_symbols_or_none  # noqa: E402


def _spy_extractor():
    calls = []
    from harpyja.symbols.extract import extract_symbols

    def ex(path, language, source):
        calls.append(path)
        return extract_symbols(path, language, source)

    return ex, calls


def test_index_writes_symbols_jsonl_and_meta_alongside_manifest(tmp_path):
    _write(tmp_path, "a.py", "def foo():\n    pass\n")
    index_repo(tmp_path, Settings())
    art = _artifact_dir(tmp_path)
    assert (art / SYMBOLS_NAME).is_file()
    assert (art / META_NAME).is_file()


def test_index_symbols_indexed_equals_total_records_in_index(tmp_path):
    _write(tmp_path, "a.py", "def foo():\n    pass\nclass Bar:\n    def m(self):\n        pass\n")
    result = index_repo(tmp_path, Settings())
    # foo (function) + Bar (class) + m (method) = 3 records.
    assert result.symbols_indexed == 3
    art = _artifact_dir(tmp_path)
    assert len((art / SYMBOLS_NAME).read_text().splitlines()) == 3


def test_index_null_language_and_grammarless_files_contribute_zero_symbols(tmp_path):
    _write(tmp_path, "run", "#!/bin/sh\n")  # null-language
    _write(tmp_path, "lib.rs", "fn main() {}\n")  # grammarless (no Wave-2 grammar)
    result = index_repo(tmp_path, Settings())
    assert result.symbols_indexed == 0
    assert result.degraded == []  # grammarless ≠ grammar-missing


def test_index_symbols_indexed_is_total_in_index_on_no_reparse(tmp_path):
    _write(tmp_path, "a.py", "def foo():\n    pass\n")
    index_repo(tmp_path, Settings())
    result = index_repo(tmp_path, Settings())  # unchanged → no re-parse
    assert result.symbols_indexed == 1  # still the full total, not parsed-this-run


def test_index_unchanged_file_not_reparsed_zero_parse_calls(tmp_path):
    _write(tmp_path, "a.py", "def foo():\n    pass\n")
    ex, calls = _spy_extractor()
    index_repo(tmp_path, Settings(), extractor=ex)
    assert any(c.endswith("a.py") for c in calls)
    calls.clear()
    index_repo(tmp_path, Settings(), extractor=ex)
    assert not any(c.endswith("a.py") for c in calls)  # reused, not re-parsed


def test_index_changed_hash_file_reparsed_records_replaced(tmp_path):
    f = _write(tmp_path, "a.py", "def foo():\n    pass\n")
    ex, calls = _spy_extractor()
    index_repo(tmp_path, Settings(), extractor=ex)
    calls.clear()
    f.write_text("def bar():\n    pass\n", encoding="utf-8")
    os.utime(f, (1_000_000_000, 1_000_000_000))
    index_repo(tmp_path, Settings(), extractor=ex)
    assert any(c.endswith("a.py") for c in calls)
    names = {r.name for r in load_symbols_or_none(_artifact_dir(tmp_path), _ident(tmp_path)) or []}
    assert names == {"bar"}


def test_index_rehash_reparses_every_file(tmp_path):
    _write(tmp_path, "a.py", "def foo():\n    pass\n")
    ex, calls = _spy_extractor()
    index_repo(tmp_path, Settings(), extractor=ex)
    calls.clear()
    index_repo(tmp_path, Settings(), extractor=ex, rehash=True)
    assert any(c.endswith("a.py") for c in calls)


def test_index_prunes_deleted_file_symbol_records(tmp_path):
    a = _write(tmp_path, "a.py", "def foo():\n    pass\n")
    _write(tmp_path, "b.py", "def bar():\n    pass\n")
    index_repo(tmp_path, Settings())
    a.unlink()
    index_repo(tmp_path, Settings())
    recs = load_symbols_or_none(_artifact_dir(tmp_path), _ident(tmp_path)) or []
    paths = {r.path for r in recs}
    assert "a.py" not in paths
    assert "b.py" in paths


def _ident(repo):
    from harpyja.symbols.engine_identity import engine_identity

    return engine_identity()


def test_index_degraded_reports_parse_error_file_total_in_index(tmp_path):
    _write(tmp_path, "broken.py", "def good():\n    pass\ndef bad(:\n    pass\n")
    result = index_repo(tmp_path, Settings())
    assert any("parse-error" in d and "broken.py" in d for d in result.degraded)


def test_index_degraded_persisted_and_reused_on_no_reparse(tmp_path):
    _write(tmp_path, "broken.py", "def bad(:\n    pass\n")
    index_repo(tmp_path, Settings())
    ex, calls = _spy_extractor()
    result = index_repo(tmp_path, Settings(), extractor=ex)  # unchanged
    assert not calls  # not re-parsed
    assert any("parse-error" in d and "broken.py" in d for d in result.degraded)
    entry = {e.path: e for e in read_manifest(_artifact_dir(tmp_path))}["broken.py"]
    assert entry.degraded == "parse-error"


def test_index_pruning_drops_persisted_degraded_flag(tmp_path):
    b = _write(tmp_path, "broken.py", "def bad(:\n    pass\n")
    index_repo(tmp_path, Settings())
    b.unlink()
    result = index_repo(tmp_path, Settings())
    assert not any("broken.py" in d for d in result.degraded)


def test_index_grammar_missing_distinguishable_from_parse_error(tmp_path):
    _write(tmp_path, "broken.py", "def bad(:\n    pass\n")
    _write(tmp_path, "ok.go", "package m\nfunc F() {}\n")

    def ex(path, language, source):
        if language == "go":
            return ExtractResult([], "grammar-missing")
        from harpyja.symbols.extract import extract_symbols

        return extract_symbols(path, language, source)

    result = index_repo(tmp_path, Settings(), extractor=ex)
    assert any("grammar-missing" in d and "ok.go" in d for d in result.degraded)
    assert any("parse-error" in d and "broken.py" in d for d in result.degraded)


def test_index_forces_full_rebuild_on_integrity_failure_independent_of_gate(tmp_path):
    _write(tmp_path, "a.py", "def foo():\n    pass\n")
    index_repo(tmp_path, Settings())
    # Corrupt the records artifact out-of-band.
    (_artifact_dir(tmp_path) / SYMBOLS_NAME).write_text("not valid json\n")
    ex, calls = _spy_extractor()
    index_repo(tmp_path, Settings(), extractor=ex)  # file unchanged on disk
    assert any(c.endswith("a.py") for c in calls)  # rebuilt despite the gate


def test_index_grammar_version_bump_forces_rebuild_with_mtime_size_unchanged(tmp_path):
    _write(tmp_path, "a.py", "def foo():\n    pass\n")
    ex, calls = _spy_extractor()
    index_repo(tmp_path, Settings(), extractor=ex, engine_ident={"v": 1})
    calls.clear()
    index_repo(tmp_path, Settings(), extractor=ex, engine_ident={"v": 2})  # unchanged file
    assert any(c.endswith("a.py") for c in calls)  # bump invalidated the cache


def test_index_absent_to_present_grammar_rebuild_clears_stale_grammar_missing(tmp_path):
    _write(tmp_path, "a.py", "def foo():\n    pass\n")

    def absent(path, language, source):
        return ExtractResult([], "grammar-missing")

    first = index_repo(tmp_path, Settings(), extractor=absent, engine_ident={"py": "missing"})
    assert any("grammar-missing" in d for d in first.degraded)

    # Grammar now present: engine identity changes, real extractor parses.
    from harpyja.symbols.extract import extract_symbols

    second = index_repo(
        tmp_path, Settings(), extractor=extract_symbols, engine_ident={"py": "0.25"}
    )
    assert second.degraded == []  # stale grammar-missing cleared
    assert second.symbols_indexed == 1
