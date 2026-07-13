"""The pre-model context map (spec 0024, AC3).

A compact, high-level repo map built from the EXISTING manifest — a filtered tree
with NO raw file contents — injected with the query so the model sees the repo
layout without loading any file bytes. The function takes ONLY the manifest and
the query, so it structurally cannot read the repo.

The vendor/test/generated exclusion is a DISPLAY concern that reuses the indexer's
own canonical classification (`index.prior`) — the single source of truth for what
counts as test/vendor/generated. It applies to the rendered map ONLY: the
navigation tools (`grep`/`glob`/`read_span`) are unaffected and still reach those
files, because a test/vendor file can be the localization target.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import PurePosixPath

from harpyja.config.settings import Settings
from harpyja.index.manifest import ManifestEntry
from harpyja.index.prior import (
    _GENERATED_DIRS,
    _GENERATED_SUFFIXES,
    _TEST_DIRS,
    _VENDOR_DIRS,
    _is_test_file,
)


def _is_map_excluded(path: str) -> bool:
    """True iff ``path`` is a test/vendor/generated file (dropped from the map).

    Reuses the exact dir-name sets + file heuristics `index.prior` uses to
    deprioritize these layers — one source of truth, no divergent second list.
    """
    p = PurePosixPath(path)
    dirs = {part.lower() for part in p.parts[:-1]}
    name = p.name.lower()
    if dirs & _TEST_DIRS or _is_test_file(name):
        return True
    if dirs & _VENDOR_DIRS:
        return True
    if dirs & _GENERATED_DIRS or name.endswith(_GENERATED_SUFFIXES):
        return True
    return False


def build_initial_prompt(query: str) -> str:
    """spec 0027 — the MINIMAL OpenCode-style initial prompt: the query + a short
    tool-usage framing, and NO repo listing. Structure is discovered on demand via the
    navigation tools (push → pull), so this is a small constant, independent of repo
    size — it reads no manifest.

    spec 0042 (AC1): the enumeration names EVERY registered tool — for an
    instruction-following 4–14B this list IS the menu, and the 0027 text silently
    omitted `symbols` (and `read_span`) for 5 specs, structurally unadvertising them
    (the 0040 0/28-adoption defect). The prompt carries the WHEN for `symbols`
    (candidate-file → exact definition span; repo-wide by-name lookup) and marks
    `submit_citations` terminal. Bound to the registered surface by the
    `test_initial_prompt_binds_to_registered_tool_surface_single_source` drift guard —
    a new tool is un-shippable without appearing here.

    spec 0044 (AC3): the 0043 UNCONDITIONAL submit-early sentence is REMOVED —
    it typed CLOCK_BOUND_PERSISTS at net −1 (2 conversions vs 3 premature-submission
    regressions: it fixed dawdle-after-locate but induced submit-before-verify). Its
    successor is the confidence-CONDITIONED mid-loop nudge (`confidence_gate` +
    `explorer_loop`), which cannot ride turn 0 because the triggering evidence does
    not exist yet. Both the removal and the injection ride `messages` ONLY — the
    0034/0038 `params == {max_tokens: 2048}` byte-frozen pin survives verbatim
    (`test_params_pin_survives_confidence_nudge`)."""
    return (
        "You are localizing a query in a repository. Discover the layout on demand "
        "with the ls, glob, and grep tools, and read code with read_span. Use the "
        "symbols tool to list the definitions in a candidate file with their exact "
        "start/end line spans, or to look up a symbol by name across the repo (omit "
        "path) when the query's words are not greppable. When you have the location, "
        "call submit_citations with the file:line citations to end the search.\n\n"
        f"Query: {query}"
    )


def build_context_map(
    manifest: Sequence[ManifestEntry],
    query: str,
    settings: Settings,
) -> str:
    """Render the query-injected, filtered repo map (no file bytes).

    RETIRED from the explorer's live path in spec 0027 (the eager whole-repo listing
    dominated the per-turn prompt and degraded the loop — see the 0026 RCA). Kept for
    reference/history; the backend now uses `build_initial_prompt`."""
    paths = [e.path for e in manifest if not _is_map_excluded(e.path)]
    paths.sort()
    tree = "\n".join(paths)
    return (
        "You are localizing a query in a repository. Repo layout "
        "(vendor/test/generated omitted; still reachable via tools):\n"
        f"{tree}\n\n"
        f"Query: {query}"
    )
