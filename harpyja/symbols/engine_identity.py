"""Engine identity — the symbol-cache invalidation key (AC8d, AC15; 0004 AC9/AC10).

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

`tree-sitter-typescript` ships **two** grammars (`typescript` and `tsx`) from a
single package, so the `tree-sitter-typescript` and `tree-sitter-tsx` identity
slots both resolve to that one distribution — they are *coupled*: a version bump or
an absence moves them together (0004 AC9/AC10 coupling note).
"""

from __future__ import annotations

from collections.abc import Callable

# Bumped only when the on-disk symbols.jsonl record *format* changes.
SCHEMA_VERSION = 1

_RUNTIME = "tree-sitter"

# Identity slot key → (distribution, module, language attribute). The slot key is
# what the sidecar stores and the probe is keyed on; the distribution is what is
# version-probed (two slots may share one distribution — see tsx). The language
# attribute is the function loaded for the ABI/version-skew check.
_GRAMMAR_SLOTS: dict[str, tuple[str, str, str]] = {
    "tree-sitter-python": ("tree-sitter-python", "tree_sitter_python", "language"),
    "tree-sitter-go": ("tree-sitter-go", "tree_sitter_go", "language"),
    "tree-sitter-rust": ("tree-sitter-rust", "tree_sitter_rust", "language"),
    "tree-sitter-java": ("tree-sitter-java", "tree_sitter_java", "language"),
    "tree-sitter-c-sharp": ("tree-sitter-c-sharp", "tree_sitter_c_sharp", "language"),
    "tree-sitter-javascript": ("tree-sitter-javascript", "tree_sitter_javascript", "language"),
    "tree-sitter-typescript": (
        "tree-sitter-typescript",
        "tree_sitter_typescript",
        "language_typescript",
    ),
    "tree-sitter-tsx": ("tree-sitter-typescript", "tree_sitter_typescript", "language_tsx"),
    "tree-sitter-c": ("tree-sitter-c", "tree_sitter_c", "language"),
    "tree-sitter-cpp": ("tree-sitter-cpp", "tree_sitter_cpp", "language"),
}

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


def _default_probe(slot: str) -> str:
    """Resolve a slot's version, attempting an ABI load for grammars.

    ``slot`` is an identity key from :data:`_GRAMMAR_SLOTS` (or ``_RUNTIME``).
    Raises :class:`GrammarMissing` if the package is absent, or
    :class:`GrammarLoadError` if it cannot be loaded against the runtime.
    """
    from importlib import import_module
    from importlib.metadata import PackageNotFoundError
    from importlib.metadata import version as dist_version

    if slot == _RUNTIME:
        try:
            return dist_version(_RUNTIME)
        except PackageNotFoundError as err:
            raise GrammarMissing(_RUNTIME) from err

    dist, module_name, language_attr = _GRAMMAR_SLOTS[slot]
    try:
        ver = dist_version(dist)
    except PackageNotFoundError as err:
        raise GrammarMissing(dist) from err

    # Confirm the grammar actually loads against the runtime — that is the
    # ABI/version-skew failure mode we route to a sentinel, not raise.
    try:
        import tree_sitter

        grammar = import_module(module_name)
        tree_sitter.Language(getattr(grammar, language_attr)())
    except ImportError as err:
        raise GrammarMissing(dist) from err
    except Exception as err:  # ABI mismatch / incompatible capsule
        raise GrammarLoadError(dist, type(err).__name__) from err
    return ver


def engine_identity(*, probe: Probe = _default_probe) -> dict:
    """Return the running engine's identity dict (deterministic, sentinel-safe)."""
    ident: dict = {"schema_version": SCHEMA_VERSION}
    for slot in (_RUNTIME, *_GRAMMAR_SLOTS):
        try:
            ident[slot] = probe(slot)
        except GrammarMissing:
            ident[slot] = "missing"
        except GrammarLoadError as err:
            ident[slot] = f"load-error:{err.abi_code}"
    return ident
