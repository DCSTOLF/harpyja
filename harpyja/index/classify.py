"""Language classification by file extension (AC5).

Deliberately approximate and filename-derived — unknown/extensionless files
classify as ``None`` and are still indexed. Content/shebang sniffing is out of
scope for Wave 1.
"""

from __future__ import annotations

from pathlib import PurePosixPath

# Extension → language. The nine SPEC symbol-layer languages plus common kin.
_EXT_TO_LANG: dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
    ".go": "go",
    ".rs": "rust",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".cs": "csharp",
    ".java": "java",
    ".c": "c",
    ".h": "c",
    ".cc": "cpp",
    ".cpp": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    ".hh": "cpp",
}


# The set of languages the extension map can produce — used to tell an
# unrecognized language_hint from a recognized-but-unmatched one.
KNOWN_LANGUAGES: frozenset[str] = frozenset(_EXT_TO_LANG.values())


def classify_language(path: str) -> str | None:
    """Return a language string for ``path`` by extension, or ``None``."""
    suffix = PurePosixPath(path).suffix.lower()
    return _EXT_TO_LANG.get(suffix)
