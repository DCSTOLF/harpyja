"""Engine identity — the symbol-cache invalidation key (AC8d, AC15).

`engine_identity()` returns the tree-sitter runtime version plus each pinned
grammar's version, alongside a `schema_version` for the record *format*. The
symbol cache (`symbols.meta.json`) stores this; a refresh rebuilds whenever the
running engine's identity differs from the stored one — so bumping a grammar
invalidates the cache even when `(mtime, size)` and `schema_version` are unchanged.

A grammar that is **absent** records the sentinel ``"missing"``; one that fails to
load against the runtime (an ABI / version-skew mismatch) records
``"load-error:<abi-code>"``. A sentinel is always a stable, non-empty value, so a
degraded run still writes a reproducible sidecar and the identity comparison stays
deterministic across machines.
"""

from __future__ import annotations

from collections.abc import Callable

# Bumped only when the on-disk symbols.jsonl record *format* changes.
SCHEMA_VERSION = 1

# Distribution names probed for a version, in a fixed order for determinism.
_RUNTIME = "tree-sitter"
_GRAMMARS = ("tree-sitter-python", "tree-sitter-go")

Probe = Callable[[str], str]


class GrammarMissing(RuntimeError):
    """The grammar package could not be imported (absent)."""

    def __init__(self, dist: str) -> None:
        super().__init__(f"{dist} is not installed")
        self.dist = dist


class GrammarLoadError(RuntimeError):
    """The grammar failed to load against the runtime (ABI / version skew)."""

    def __init__(self, dist: str, abi_code: str) -> None:
        super().__init__(f"{dist} failed to load (abi {abi_code})")
        self.dist = dist
        self.abi_code = abi_code


def _default_probe(dist: str) -> str:
    """Resolve a distribution's version, attempting an ABI load for grammars.

    Raises :class:`GrammarMissing` if the package is absent, or
    :class:`GrammarLoadError` if it cannot be loaded against the runtime.
    """
    from importlib import import_module
    from importlib.metadata import PackageNotFoundError
    from importlib.metadata import version as dist_version

    try:
        ver = dist_version(dist)
    except PackageNotFoundError as err:
        raise GrammarMissing(dist) from err

    if dist == _RUNTIME:
        return ver

    # For a grammar, confirm it actually loads against the runtime — that is the
    # ABI/version-skew failure mode we must route to a sentinel, not raise.
    module_name = dist.replace("-", "_")
    try:
        import tree_sitter

        grammar = import_module(module_name)
        tree_sitter.Language(grammar.language())
    except ImportError as err:
        raise GrammarMissing(dist) from err
    except Exception as err:  # ABI mismatch / incompatible capsule
        raise GrammarLoadError(dist, type(err).__name__) from err
    return ver


def engine_identity(*, probe: Probe = _default_probe) -> dict:
    """Return the running engine's identity dict (deterministic, sentinel-safe)."""
    ident: dict = {"schema_version": SCHEMA_VERSION}
    for dist in (_RUNTIME, *_GRAMMARS):
        try:
            ident[dist] = probe(dist)
        except GrammarMissing:
            ident[dist] = "missing"
        except GrammarLoadError as err:
            ident[dist] = f"load-error:{err.abi_code}"
    return ident
