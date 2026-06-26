"""The `prior` relevance heuristic (SPEC §4.1).

A pure, deterministic function from a repo-relative path to a float in roughly
[0, 1.5]: higher = more likely to be relevant, used to order candidates before
any search/model runs.

The factor **structure** is what ships here — path depth, test/vendor/generated
penalties, and a source-dir bonus. The weight **numbers** are placeholders to be
tuned against real repos later (P5); whatever the tuning, it must preserve the
orderings the tests assert (vendored/test/generated < equivalent source).
"""

from __future__ import annotations

from pathlib import PurePosixPath

# Placeholder weights (P5: tuning must keep the sign/ordering, not these exact numbers).
_BASE = 1.0
_DEPTH_PENALTY = 0.05
_TEST_PENALTY = 0.40
_VENDOR_PENALTY = 0.50
_GENERATED_PENALTY = 0.40
_SOURCE_BONUS = 0.30

_TEST_DIRS = {"test", "tests", "testing", "__tests__", "spec", "specs"}
_VENDOR_DIRS = {
    "vendor",
    "vendored",
    "node_modules",
    "third_party",
    "thirdparty",
    ".venv",
    "venv",
    "site-packages",
    "bower_components",
}
_GENERATED_DIRS = {"generated", "gen", "dist", "build", "out", "target", "__pycache__"}
_SOURCE_DIRS = {"src", "lib", "libs", "app", "pkg", "internal", "source", "core"}

_GENERATED_SUFFIXES = (".min.js", ".pb.go", "_pb2.py", ".g.dart", ".generated.ts")


def _is_test_file(name: str) -> bool:
    stem = name.rsplit(".", 1)[0]
    return (
        stem.startswith("test_")
        or stem.endswith("_test")
        or stem.endswith(".test")
        or ".test." in name
        or ".spec." in name
    )


def prior(path: str) -> float:
    """Relevance prior for a repo-relative path. Pure and deterministic."""
    p = PurePosixPath(path)
    parts = [part.lower() for part in p.parts]
    dirs = set(parts[:-1])
    name = p.name.lower()

    score = _BASE
    score -= _DEPTH_PENALTY * (len(p.parts) - 1)

    if dirs & _TEST_DIRS or _is_test_file(name):
        score -= _TEST_PENALTY
    if dirs & _VENDOR_DIRS:
        score -= _VENDOR_PENALTY
    if dirs & _GENERATED_DIRS or name.endswith(_GENERATED_SUFFIXES):
        score -= _GENERATED_PENALTY
    if dirs & _SOURCE_DIRS:
        score += _SOURCE_BONUS

    return score
