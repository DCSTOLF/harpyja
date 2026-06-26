"""Read/write the ranked manifest `manifest.jsonl` (AC1, AC18).

One JSON object per line: ``path, language, size, hash, mtime, prior`` (fixed key
order). Entries are written in a stable order — descending ``prior``, then
``path`` — so repeated indexes of an unchanged tree produce byte-identical files.
The write is atomic: a temp file **in the same directory** is `os.replace`d into
place, so a crash mid-write can't leave a truncated manifest.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

MANIFEST_NAME = "manifest.jsonl"
# `degraded` (Wave 2, D18) is appended last — additive, so a Wave-1 manifest still
# reads (default `None` = clean) and the Wave-1 key order is otherwise unchanged.
_KEY_ORDER = ("path", "language", "size", "hash", "mtime", "prior", "degraded")


@dataclass
class ManifestEntry:
    path: str
    language: str | None
    size: int
    hash: str
    mtime: float
    prior: float
    degraded: str | None = None  # per-file degradation outcome; None = clean

    def to_json(self) -> str:
        ordered = {k: getattr(self, k) for k in _KEY_ORDER}
        return json.dumps(ordered, ensure_ascii=False, sort_keys=False)


def _sort_key(e: ManifestEntry) -> tuple[float, str]:
    return (-e.prior, e.path)


def write_manifest(dir_path: str | Path, entries: list[ManifestEntry]) -> Path:
    """Atomically write the sorted manifest into ``dir_path``."""
    dir_path = Path(dir_path)
    dir_path.mkdir(parents=True, exist_ok=True)
    target = dir_path / MANIFEST_NAME

    body = "".join(e.to_json() + "\n" for e in sorted(entries, key=_sort_key))

    fd, tmp_name = tempfile.mkstemp(dir=dir_path, prefix=".manifest.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(body)
        os.replace(tmp_name, target)
    except BaseException:
        # Best-effort cleanup; never leave the temp file behind on failure.
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
        raise
    return target


def read_manifest(dir_path: str | Path) -> list[ManifestEntry]:
    """Read the manifest in ``dir_path``; empty list if absent."""
    target = Path(dir_path) / MANIFEST_NAME
    if not target.is_file():
        return []
    out: list[ManifestEntry] = []
    for line in target.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        # `degraded` may be absent in a legacy (Wave-1) manifest → default clean.
        out.append(ManifestEntry(**{k: obj.get(k) for k in _KEY_ORDER}))
    return out
