"""No-silent-coverage invariant (0004 AC8, P1).

A language's extension routing and its symbol extraction must ship together. If
`classify` routes an extension to a language that `index` does not attempt to
extract, files of that language parse to **zero records with no degradation flag**
— indistinguishable from a genuinely symbol-less file (a silent "we never looked").
The project's no-false-capability rule forbids that, so the two sets are kept in
**lockstep**: every routed (symbol) language is an extracted language.

This guard is permanent — it must hold at every tier boundary as the remaining
grammars ship, not just at completion.
"""

from __future__ import annotations

from harpyja.index.classify import KNOWN_LANGUAGES, classify_language
from harpyja.index.indexer import SYMBOL_LANGUAGES


def test_symbol_languages_equal_known_languages():
    # Lockstep: classify produces exactly the languages the indexer extracts.
    assert KNOWN_LANGUAGES == SYMBOL_LANGUAGES


def test_every_routed_language_is_extracted_never_clean_zero():
    # KNOWN ⊆ SYMBOL — so `_extract_file` never returns ([], None) for a routed
    # file; an unsupported-but-routed language would surface `grammar-missing`,
    # never a silent clean-zero.
    assert KNOWN_LANGUAGES <= SYMBOL_LANGUAGES


def test_truly_unmapped_extension_is_null_language():
    # A genuinely unmapped extension stays null-language / ripgrep-only.
    assert classify_language("src/main.zig") is None
    assert classify_language("notes.xyz") is None
