"""Spec 0041 (AC5) — the residency mechanism is confined to the driver seam.

An ``ast``-based sweep (the deletion-guard discipline — never a text grep,
which comments and docstrings would fool) asserts the residency vocabulary
(``keep_alive`` as a call keyword / dict key / string constant, and the
``/api/ps`` endpoint) appears ONLY in the eval driver / native-API modules and
NEVER in the SUT packages (``gateway/``, ``scout/``, ``deep/``). Green on
introduction; ROTS FALSE on any future leak of the hygiene mechanism into a
capability path.
"""

from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]

_SUT_PACKAGES = ("gateway", "scout", "deep")

# The sanctioned driver/native-API seam (eval-side only).
_ALLOWED_EVAL_MODULES = {
    "pool_pilot.py",
    "gate_run.py",
    "residency_probe.py",
    "exclusivity_gate.py",
}

_FORBIDDEN_SUBSTRINGS = ("keep_alive", "/api/ps")


def _residency_mentions(path: Path) -> list[str]:
    """Every residency-vocabulary occurrence in real code positions:
    string constants, call keywords, and attribute/name identifiers."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    hits: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if any(s in node.value for s in _FORBIDDEN_SUBSTRINGS):
                hits.append(f"{path.name}:{node.lineno} constant {node.value!r}")
        elif isinstance(node, ast.keyword) and node.arg == "keep_alive":
            hits.append(f"{path.name}:{node.lineno} keyword keep_alive=")
        elif isinstance(node, ast.Name | ast.Attribute):
            ident = node.id if isinstance(node, ast.Name) else node.attr
            if ident == "keep_alive":
                hits.append(f"{path.name}:{node.lineno} identifier keep_alive")
    return hits


def _prod_files(package: str) -> list[Path]:
    return [
        p
        for p in (_ROOT / package).rglob("*.py")
        if not p.name.startswith("test_")
    ]


def test_keep_alive_and_api_ps_confined_to_driver_native_api_seam():
    # Direction 1: NO SUT package mentions the residency vocabulary.
    leaks: list[str] = []
    for package in _SUT_PACKAGES:
        for path in _prod_files(package):
            leaks.extend(f"{package}/{hit}" for hit in _residency_mentions(path))
    assert leaks == [], (
        "residency mechanism leaked into the SUT (spec 0041 confines it to "
        f"the eval driver seam): {leaks}"
    )
    # Direction 2: outside the sanctioned eval modules, no other eval prod
    # module grows the mechanism either.
    stray = [
        f"eval/{hit}"
        for path in _prod_files("eval")
        if path.name not in _ALLOWED_EVAL_MODULES
        for hit in _residency_mentions(path)
    ]
    assert stray == [], f"residency vocabulary outside the sanctioned seam: {stray}"
    # The sweep itself is live: the sanctioned seam DOES carry the mechanism
    # (a silently-empty sweep would prove nothing).
    seam_hits = [
        hit
        for name in sorted(_ALLOWED_EVAL_MODULES)
        for hit in _residency_mentions(_ROOT / "eval" / name)
    ]
    assert seam_hits, "sweep is vacuous — the driver seam shows no mechanism"