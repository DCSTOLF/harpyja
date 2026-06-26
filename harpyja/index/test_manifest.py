"""RED (task 18): manifest write/read — shape, order, atomicity (AC18, AC1)."""

import json
import os

from harpyja.index.manifest import ManifestEntry, read_manifest, write_manifest

_FIELDS = {"path", "language", "size", "hash", "mtime", "prior", "degraded"}


def _entry(path, prior, language="python"):
    return ManifestEntry(
        path=path, language=language, size=10, hash="sha256:x", mtime=1.0, prior=prior
    )


def test_manifest_line_has_spec_fields(tmp_path):
    write_manifest(tmp_path, [_entry("a.py", 1.0)])
    line = (tmp_path / "manifest.jsonl").read_text(encoding="utf-8").splitlines()[0]
    assert set(json.loads(line).keys()) == _FIELDS


def test_manifest_ordered_by_prior_desc_then_path(tmp_path):
    entries = [
        _entry("b.py", 0.5),
        _entry("a.py", 0.9),
        _entry("c.py", 0.9),  # ties with a.py on prior → path order
    ]
    write_manifest(tmp_path, entries)
    paths = [
        json.loads(line)["path"] for line in (tmp_path / "manifest.jsonl").read_text().splitlines()
    ]
    assert paths == ["a.py", "c.py", "b.py"]


def test_manifest_two_writes_byte_identical(tmp_path):
    entries = [_entry("a.py", 0.9), _entry("b.py", 0.5)]
    write_manifest(tmp_path, entries)
    first = (tmp_path / "manifest.jsonl").read_bytes()
    write_manifest(tmp_path, entries)
    assert (tmp_path / "manifest.jsonl").read_bytes() == first


def test_manifest_atomic_temp_in_same_dir_then_rename(tmp_path, monkeypatch):
    seen = {}
    real_replace = os.replace

    def spy(src, dst):
        seen["src"], seen["dst"] = src, dst
        return real_replace(src, dst)

    monkeypatch.setattr(os, "replace", spy)
    write_manifest(tmp_path, [_entry("a.py", 1.0)])
    from pathlib import Path

    assert Path(seen["src"]).parent == Path(seen["dst"]).parent  # same-dir temp


def test_manifest_roundtrips(tmp_path):
    entries = [_entry("a.py", 0.9), _entry("x", 0.1, language=None)]
    write_manifest(tmp_path, entries)
    back = {e.path: e for e in read_manifest(tmp_path)}
    assert back["a.py"].prior == 0.9
    assert back["x"].language is None


# --- Wave 2: per-file `degraded` field (D18, AC16) ---


def test_manifest_entry_has_degraded_field_default_clean(tmp_path):
    # Default (omitted) → clean (None).
    assert _entry("a.py", 1.0).degraded is None


def test_manifest_degraded_in_key_order_and_serialized_json(tmp_path):
    entry = ManifestEntry(
        path="a.py",
        language="python",
        size=1,
        hash="sha256:x",
        mtime=1.0,
        prior=1.0,
        degraded="parse-error",
    )
    write_manifest(tmp_path, [entry])
    obj = json.loads((tmp_path / "manifest.jsonl").read_text().splitlines()[0])
    assert obj["degraded"] == "parse-error"
    assert list(obj.keys())[-1] == "degraded"  # additive, last in key order


def test_manifest_reads_legacy_entry_missing_degraded_with_default(tmp_path):
    # A Wave-1 manifest line has no `degraded` key — read must default it.
    legacy = json.dumps(
        {
            "path": "a.py",
            "language": "python",
            "size": 1,
            "hash": "sha256:x",
            "mtime": 1.0,
            "prior": 1.0,
        }
    )
    (tmp_path / "manifest.jsonl").write_text(legacy + "\n")
    back = read_manifest(tmp_path)
    assert back[0].degraded is None


def test_manifest_two_writes_byte_identical_with_degraded_field(tmp_path):
    entries = [
        ManifestEntry("a.py", "python", 1, "sha256:x", 1.0, 0.9, degraded="parse-error"),
        ManifestEntry("b.py", "go", 1, "sha256:y", 1.0, 0.5, degraded=None),
    ]
    write_manifest(tmp_path, entries)
    first = (tmp_path / "manifest.jsonl").read_bytes()
    write_manifest(tmp_path, entries)
    assert (tmp_path / "manifest.jsonl").read_bytes() == first
