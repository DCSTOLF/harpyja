"""Read/write `symbols.jsonl` + its `symbols.meta.json` sidecar (AC1, AC7, AC8).

`symbols.jsonl` holds one definition per line in a fixed key order, sorted by the
total key ``(path, start_line, end_line, kind, name)`` so an unchanged tree yields
a byte-identical file. The sidecar **authenticates a specific records generation**:
it carries the `engine_identity`, the `record_count`, and a `content_digest`
(`"sha256:…"`) over the exact bytes of `symbols.jsonl`.

The artifact is **untrusted derived input** on the read path. A rebuild is forced
when the records are missing/unreadable/truncated, the meta is missing/unreadable,
the `engine_identity` differs, **or** the records don't match the meta's fingerprint
(line count ≠ `record_count`, or recomputed `sha256` ≠ `content_digest`). The
fingerprint is what makes a clean newline truncation and a records-first/meta-last
crash residue both detectable.

Commit order is **records first, meta last**, each via a same-dir temp + `os.replace`:
a crash between them leaves fresh records under a stale meta whose fingerprint no
longer binds, which the read path detects and rebuilds.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

from harpyja.server.types import CodeSpan
from harpyja.symbols.extract import SymbolRecord

SYMBOLS_NAME = "symbols.jsonl"
META_NAME = "symbols.meta.json"
_KEY_ORDER = ("path", "language", "name", "kind", "parent", "start_line", "end_line")


def record_to_codespan(record: SymbolRecord) -> CodeSpan:
    """Convert a SymbolRecord to a CodeSpan with symbol/kind/line-span fields.

    Shared projection used by both Deep and Scout symbol tools to ensure a
    single source of truth for the record→CodeSpan conversion.
    """
    return CodeSpan(
        path=record.path,
        start_line=record.start_line,
        end_line=record.end_line,
        symbol=record.name,
        language=record.language,
        kind=record.kind,
    )


def _record_json(rec: SymbolRecord) -> str:
    ordered = {k: getattr(rec, k) for k in _KEY_ORDER}
    return json.dumps(ordered, ensure_ascii=False, sort_keys=False)


def _sort_key(rec: SymbolRecord) -> tuple:
    return (rec.path, rec.start_line, rec.end_line, rec.kind, rec.name)


def _atomic_write(target: Path, data: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.replace(tmp_name, target)
    except BaseException:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
        raise


def write_symbols(dir_path: str | Path, records: list[SymbolRecord], *, engine_ident: dict) -> None:
    """Write `symbols.jsonl` (first) then `symbols.meta.json` (last), atomically."""
    dir_path = Path(dir_path)
    body = "".join(_record_json(r) + "\n" for r in sorted(records, key=_sort_key))
    body_bytes = body.encode("utf-8")

    # Records first — a crash before the meta lands leaves a stale-meta residue
    # the fingerprint will reject on read.
    _atomic_write(dir_path / SYMBOLS_NAME, body_bytes)

    languages = sorted({r.language for r in records if r.language is not None})
    meta = {
        "engine_identity": engine_ident,
        "languages": languages,
        "record_count": len(records),
        "content_digest": "sha256:" + hashlib.sha256(body_bytes).hexdigest(),
    }
    meta_bytes = json.dumps(meta, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")
    _atomic_write(dir_path / META_NAME, meta_bytes)


def read_symbols(dir_path: str | Path) -> list[SymbolRecord]:
    """Read `symbols.jsonl`; empty list if absent. (No integrity check — see
    :func:`load_symbols_or_none`.)"""
    target = Path(dir_path) / SYMBOLS_NAME
    if not target.is_file():
        return []
    out: list[SymbolRecord] = []
    for line in target.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        out.append(SymbolRecord(**{k: obj[k] for k in _KEY_ORDER}))
    return out


def needs_rebuild(dir_path: str | Path, engine_ident: dict) -> bool:
    """True when the symbol artifact cannot be trusted and must be rebuilt."""
    dir_path = Path(dir_path)
    symbols = dir_path / SYMBOLS_NAME
    meta_path = dir_path / META_NAME

    if not symbols.is_file():
        return True
    try:
        raw = symbols.read_bytes()
    except OSError:
        return True

    # Every line must be valid JSON (catches a mid-line truncation).
    lines = [line for line in raw.decode("utf-8", errors="replace").splitlines() if line.strip()]
    try:
        for line in lines:
            json.loads(line)
    except (json.JSONDecodeError, ValueError):
        return True

    if not meta_path.is_file():
        return True
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return True

    if meta.get("engine_identity") != engine_ident:
        return True
    if meta.get("record_count") != len(lines):
        return True
    if meta.get("content_digest") != "sha256:" + hashlib.sha256(raw).hexdigest():
        return True
    return False


def load_symbols_or_none(dir_path: str | Path, engine_ident: dict) -> list[SymbolRecord] | None:
    """Return the records if the artifact is intact, else ``None`` (signal rebuild)."""
    if needs_rebuild(dir_path, engine_ident):
        return None
    return read_symbols(dir_path)
