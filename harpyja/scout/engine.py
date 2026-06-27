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

from harpyja.config.settings import Settings
from harpyja.scout.backend import ScoutBackend
from harpyja.scout.normalize import normalize_spans
from harpyja.server.types import CodeSpan

SeedFn = Callable[[str], list[CodeSpan]]


class ScoutEngine:
    def __init__(
        self,
        backend: ScoutBackend,
        seed_fn: SeedFn,
        settings: Settings,
        repo_root: str,
    ) -> None:
        self._backend = backend
        self._seed_fn = seed_fn
        self._settings = settings
        self._repo_root = repo_root

    def search(self, pattern: str, scope: str | None = None) -> list[CodeSpan]:
        # Seed FIRST (its precondition errors must propagate before the backend).
        seed = self._seed_fn(pattern)
        hints = seed[: self._settings.scout_seed_top_n]
        raw = self._backend.run(pattern, hints)
        return normalize_spans(raw, self._repo_root, self._settings)
