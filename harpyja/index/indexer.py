"""Build/refresh the manifest + symbol index (AC1-6, AC8, AC16, AC17, AC18).

Pure-Python walk/hash/manifest (no ripgrep needed). Incremental on two axes:
- **hashing** — a file whose ``(mtime, size)`` match the prior manifest entry is
  reused without re-hashing (Wave 1);
- **symbols** — the same gate avoids re-parsing; prior `SymbolRecord`s are reused.

Symbol extraction (Wave 2) runs only for languages with a bundled grammar
(`python`, `go`); other and null-language files contribute zero symbols. The symbol
artifact is **self-verifying**: if it is missing/corrupt or the running
`engine_identity` differs from the stored one, a **full symbol rebuild** is forced
(re-parse every file) independently of the `(mtime, size)` gate and without
``--rehash`` — this also clears stale `grammar-missing` flags once a grammar is
installed. Each file's degradation outcome is persisted on its manifest entry so
the `degraded` array stays total-in-index across a no-reparse refresh.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path

from harpyja.config.settings import Settings
from harpyja.index.artifacts import resolve_artifact_dir
from harpyja.index.classify import classify_language
from harpyja.index.hash import hash_file
from harpyja.index.ignore import build_ignore
from harpyja.index.manifest import ManifestEntry, read_manifest, write_manifest
from harpyja.index.prior import prior
from harpyja.index.walk import walk
from harpyja.symbols.engine_identity import engine_identity
from harpyja.symbols.extract import ExtractResult, SymbolRecord, extract_symbols
from harpyja.symbols.symbols_io import load_symbols_or_none, write_symbols

HashFn = Callable[[Path], str]
Extractor = Callable[[str, str, bytes], ExtractResult]

# Languages with a bundled tree-sitter grammar in Wave 2.
SYMBOL_LANGUAGES = frozenset({"python", "go"})


@dataclass
class IndexResult:
    files_indexed: int
    symbols_indexed: int = 0
    languages: dict[str, int] = field(default_factory=dict)
    elapsed_ms: int = 0
    degraded: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "files_indexed": self.files_indexed,
            "symbols_indexed": self.symbols_indexed,
            "languages": self.languages,
            "elapsed_ms": self.elapsed_ms,
            "degraded": self.degraded,
        }


def index_repo(
    repo_path: str | Path,
    settings: Settings,
    *,
    rehash: bool = False,
    hash_fn: HashFn = hash_file,
    artifact_dir: Path | None = None,
    extractor: Extractor = extract_symbols,
    engine_ident: dict | None = None,
) -> IndexResult:
    start = time.perf_counter()
    repo = Path(repo_path)
    ident = engine_ident if engine_ident is not None else engine_identity()

    art_dir = artifact_dir or resolve_artifact_dir(repo, settings)
    prior_entries = {e.path: e for e in read_manifest(art_dir)}

    # Load prior symbols; None => the artifact can't be trusted (missing/corrupt/
    # engine-identity mismatch) so we force a full re-parse independent of the gate.
    prior_symbols = load_symbols_or_none(art_dir, ident)
    force_rebuild = prior_symbols is None
    prior_by_path: dict[str, list[SymbolRecord]] = {}
    for rec in prior_symbols or []:
        prior_by_path.setdefault(rec.path, []).append(rec)

    ignore = build_ignore(repo, settings.ignore_globs)

    entries: list[ManifestEntry] = []
    languages: dict[str, int] = {}
    all_records: list[SymbolRecord] = []
    degraded: list[str] = []

    for rel in walk(repo, ignore, follow_symlinks=settings.follow_symlinks):
        full = repo / rel
        try:
            st = full.stat()
        except OSError:
            continue
        size, mtime = st.st_size, st.st_mtime

        cached = prior_entries.get(rel)
        hash_gate = (
            not rehash and cached is not None and cached.size == size and cached.mtime == mtime
        )
        language = cached.language if hash_gate else classify_language(rel)

        reuse_symbols = hash_gate and not force_rebuild and not rehash
        if reuse_symbols:
            file_records = prior_by_path.get(rel, [])
            degraded_reason = cached.degraded
        else:
            file_records, degraded_reason = _extract_file(full, rel, language, extractor)

        if hash_gate:
            entry = (
                cached
                if cached.degraded == degraded_reason
                else replace(cached, degraded=degraded_reason)
            )
        else:
            entry = ManifestEntry(
                path=rel,
                language=language,
                size=size,
                hash=hash_fn(full),
                mtime=mtime,
                prior=prior(rel),
                degraded=degraded_reason,
            )

        entries.append(entry)
        all_records.extend(file_records)
        if degraded_reason:
            degraded.append(f"{degraded_reason}: {rel}")
        if entry.language is not None:
            languages[entry.language] = languages.get(entry.language, 0) + 1

    write_symbols(art_dir, all_records, engine_ident=ident)
    write_manifest(art_dir, entries)

    return IndexResult(
        files_indexed=len(entries),
        symbols_indexed=len(all_records),
        languages=languages,
        elapsed_ms=int((time.perf_counter() - start) * 1000),
        degraded=sorted(degraded),
    )


def _extract_file(
    full: Path, rel: str, language: str | None, extractor: Extractor
) -> tuple[list[SymbolRecord], str | None]:
    """Extract symbols for a single file; only bundled-grammar languages parse."""
    if language not in SYMBOL_LANGUAGES:
        return [], None
    try:
        source = full.read_bytes()
    except OSError:
        return [], None
    result = extractor(rel, language, source)
    return result.records, result.degraded
