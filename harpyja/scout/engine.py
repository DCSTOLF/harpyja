"""`ScoutEngine` — Tier 1 behind the shared `Locator` (`.search`) seam.

The engine is self-seeding: every call runs its own lightweight Tier-0 lookup
(`seed_fn`) *before* invoking the backend, so an explicit `mode=fast` request
(which skipped `auto`'s Tier-0 pass) still hands the backend warm hints. Seed
errors are deliberately **not** caught — a missing hard precondition (e.g. `rg`)
propagates loudly rather than collapsing into a silent empty (the degradation
floor). Backend output is untrusted and is normalized before return.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from harpyja.config.settings import Settings
from harpyja.scout.backend import ScoutBackend
from harpyja.scout.normalize import normalize_spans_with_tally
from harpyja.server.types import CodeSpan

SeedFn = Callable[[str], list[CodeSpan]]


@dataclass(frozen=True)
class ScoutTally:
    """Per-search text-ref shape distribution (spec 0011, AC17).

    `spanned`/`filelevel` count the refs the model emitted (lined vs bare path —
    the bare-path frequency is the root-cause signal); `dropped` counts refs
    `normalize_spans` rejected (out-of-repo / nonexistent). Spec 0012:
    `recovered_spanned`/`recovered_filelevel` count refs that would have dropped but
    were recovered by suffix-matching against the manifest — split by shape because a
    recovered file-level ref skips the gate read-back (un-verified). Side-channel
    metadata the eval harness reads; the orchestrator never sees it.
    """

    spanned: int = 0
    filelevel: int = 0
    dropped: int = 0
    recovered_spanned: int = 0
    recovered_filelevel: int = 0
    # The repo-relative paths of the recovered FILE-LEVEL refs (un-gated set, for
    # operator inspection of wrong-but-unique recoveries — spec 0012 AC5).
    recovered_filelevel_paths: tuple[str, ...] = ()


class ScoutEngine:
    def __init__(
        self,
        backend: ScoutBackend,
        seed_fn: SeedFn,
        settings: Settings,
        repo_root: str,
        file_set: frozenset[str] | None = None,
    ) -> None:
        self._backend = backend
        self._seed_fn = seed_fn
        self._settings = settings
        self._repo_root = repo_root
        # Spec 0012: the repo's indexed manifest file set (repo-relative paths) used
        # for path-suffix recovery; None/empty ⇒ no recovery (graceful degrade).
        self._file_set = file_set
        # Spec 0011: the shape tally of the most recent search (None until run).
        self.last_tally: ScoutTally | None = None

    def search(self, pattern: str, scope: str | None = None) -> list[CodeSpan]:
        # Seed FIRST (its precondition errors must propagate before the backend).
        seed = self._seed_fn(pattern)
        hints = seed[: self._settings.scout_seed_top_n]
        raw = self._backend.run(pattern, hints)
        # Shape distribution of the model's emitted refs (before drop), so the
        # bare-path frequency is faithful to what the model produced.
        spanned = sum(1 for s in raw if not s.is_file_level)
        filelevel = sum(1 for s in raw if s.is_file_level)
        recovered_paths: list[str] = []
        out, dropped, rec_spanned, rec_filelevel = normalize_spans_with_tally(
            raw,
            self._repo_root,
            max_citations=self._settings.scout_max_citations,
            max_span_lines=self._settings.scout_max_span_lines,
            file_set=self._file_set,
            recovered_paths_out=recovered_paths,
        )
        self.last_tally = ScoutTally(
            spanned=spanned,
            filelevel=filelevel,
            dropped=dropped,
            recovered_spanned=rec_spanned,
            recovered_filelevel=rec_filelevel,
            recovered_filelevel_paths=tuple(recovered_paths),
        )
        return out
