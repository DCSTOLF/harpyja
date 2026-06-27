"""Language classification by file extension (AC5).

Deliberately approximate and filename-derived — unknown/extensionless files
classify as ``None`` and are still indexed. Content/shebang sniffing is out of
scope for Wave 1.
"""

from __future__ import annotations

from pathlib import PurePosixPath

# Extension → language. A language is routed here ONLY once its symbol extraction
# ships (the no-silent-coverage invariant, 0004 AC8 / test_routing.py): routing and
# extraction stay in lockstep so a routed file is never a silent zero-symbol result.
# Wave 2 (0003) shipped python + go; the remaining grammars (rust, java, csharp,
# javascript, typescript, tsx, c, cpp) are added per tier as each ships.
_EXT_TO_LANG: dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
    ".go": "go",
    # Tier A (0004): Rust, Java, C#
    ".rs": "rust",
    ".java": "java",
    ".cs": "csharp",
    # Tier B (0004): JavaScript, TypeScript, TSX
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    # Tier C (0004): C, C++. `.h` defaults to C (documented ambiguity); a C++-only
    # construct in a .h that the C grammar cannot parse degrades via parse-error.
    ".c": "c",
    ".h": "c",
    ".cc": "cpp",
    ".cpp": "cpp",
    ".cxx": "cpp",
    ".c++": "cpp",
    ".hpp": "cpp",
    ".hh": "cpp",
    ".hxx": "cpp",
    ".h++": "cpp",
}


# The set of languages the extension map can produce — used to tell an
# unrecognized language_hint from a recognized-but-unmatched one.
KNOWN_LANGUAGES: frozenset[str] = frozenset(_EXT_TO_LANG.values())


def classify_language(path: str) -> str | None:
    """Return a language string for ``path`` by extension, or ``None``."""
    suffix = PurePosixPath(path).suffix.lower()
    return _EXT_TO_LANG.get(suffix)
