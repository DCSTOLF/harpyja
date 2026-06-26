"""Streaming sha256 file hashing for the manifest (AC1)."""

from __future__ import annotations

import hashlib
from pathlib import Path

_CHUNK = 1 << 16


def hash_file(path: str | Path) -> str:
    """Return ``"sha256:<hexdigest>"`` for the file at ``path``."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(_CHUNK), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()
