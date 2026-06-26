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
