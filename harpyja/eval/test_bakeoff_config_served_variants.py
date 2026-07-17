"""Spec 0049 (AC2) — the re-frozen served config: greedy variant tags + committed
fingerprints + a new offline-reproducible hash, path A (base tags absent).

Drift is guarded by FIELD-DEFAULT INTROSPECTION over ``dataclasses.fields`` and a
KNOWN-VALUE hash literal — never a source grep. The single measurement-config
consumer (``resolve_served_model``) is pinned by an ``ast`` sweep so no
deployment/unrelated path reads ``served_variant_tags``.
"""

from __future__ import annotations

import ast
import dataclasses
import pathlib

from harpyja.eval.bakeoff_config import (
    SERVED_VARIANT_CONFIG_HASH,
    BakeoffConfig,
    bakeoff_config_hash,
    resolve_served_model,
)
from harpyja.eval.greedy_serving import fingerprint_digest, parse_modelfile_fingerprint

_CFG = BakeoffConfig()
_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_SERVING = _REPO_ROOT / "serving"
_GREEDY_TAGS = ("qwen3-14b-greedy", "qwen3-8b-greedy", "qwen3.5-4b-greedy")
_MODELFILES = {
    "qwen3-14b-greedy": _SERVING / "Modelfile.qwen3-14b",
    "qwen3-8b-greedy": _SERVING / "Modelfile.qwen3-8b",
    "qwen3.5-4b-greedy": _SERVING / "Modelfile.qwen3.5-4b",
}


def test_bakeoff_config_pins_three_greedy_variant_tags():
    assert _CFG.served_variant_tags == _GREEDY_TAGS


def test_served_variant_tags_exclude_base_tags_path_a_not_b():
    # Path A: the greedy config names ONLY the variant tags — no base tag leaks in.
    for base in _CFG.model_tags:
        assert base not in _CFG.served_variant_tags


def test_served_variant_tags_field_default_no_placeholder():
    # FIELD-DEFAULT INTROSPECTION (never a source grep): the default is the three
    # greedy tags, and none is a known-unserved/placeholder sentinel.
    field = {f.name: f for f in dataclasses.fields(BakeoffConfig)}[
        "served_variant_tags"
    ]
    assert field.default == _GREEDY_TAGS
    placeholders = {"", "TODO", "placeholder", "hf.co/Qwen/Qwen3-8B-GGUF:latest"}
    assert not (set(field.default) & placeholders)
    assert all(t.endswith("-greedy") for t in field.default)


def test_served_variant_fingerprints_match_committed_modelfiles():
    # Chain of custody: the committed digests are re-derivable from the committed
    # Modelfile bytes via the ONE parser (the hash's inputs are pure in-repo data).
    committed = dict(_CFG.served_variant_fingerprints)
    assert set(committed) == set(_GREEDY_TAGS)
    for tag, path in _MODELFILES.items():
        expected = fingerprint_digest(parse_modelfile_fingerprint(path.read_text()))
        assert committed[tag] == expected


def test_served_variant_config_hash_known_value():
    # Offline-reproducible KNOWN-VALUE drift test (a pure function of in-repo data).
    assert SERVED_VARIANT_CONFIG_HASH == bakeoff_config_hash(_CFG)
    assert len(SERVED_VARIANT_CONFIG_HASH) == 64
    assert (
        SERVED_VARIANT_CONFIG_HASH
        == "82885d1b63cbd554b6584501d0c289f0467c49f467f0f2cbd1900ba8eb98e25a"
    )


def test_served_variant_config_hash_changes_on_tag_drift():
    mutated = dataclasses.replace(
        _CFG, served_variant_tags=("qwen3-14b-greedy", "qwen3-8b-greedy", "other")
    )
    assert bakeoff_config_hash(mutated) != SERVED_VARIANT_CONFIG_HASH


def test_resolve_served_model_maps_logical_to_greedy_variant():
    assert resolve_served_model(_CFG, "qwen3:14b") == "qwen3-14b-greedy"
    assert resolve_served_model(_CFG, "qwen3:8b") == "qwen3-8b-greedy"
    assert resolve_served_model(_CFG, "qwen3.5:4b") == "qwen3.5-4b-greedy"


class _ServedVariantReaderVisitor(ast.NodeVisitor):
    """Collect the enclosing-function name of every `.served_variant_tags` read."""

    def __init__(self, module_name: str):
        self.module_name = module_name
        self.func_stack: list[str] = []
        self.readers: list[str] = []

    def visit_FunctionDef(self, node):  # noqa: N802
        self.func_stack.append(node.name)
        self.generic_visit(node)
        self.func_stack.pop()

    def visit_Attribute(self, node):  # noqa: N802
        if node.attr == "served_variant_tags":
            self.readers.append(
                self.func_stack[-1]
                if self.func_stack
                else f"<module:{self.module_name}>"
            )
        self.generic_visit(node)


# The sanctioned 0049 measurement-config consumers of `served_variant_tags`: the
# model resolver (what the runner serves) and the AC3 served-membership probe.
# ANY other reader would be a deployment/unrelated path adopting the control tags.
_SANCTIONED_READERS = {"resolve_served_model", "probe_served_variant_membership"}


def test_served_variant_tags_read_only_by_model_resolution():
    # An ast sweep over harpyja/ (tests + the config module itself excluded): the
    # ONLY readers of `.served_variant_tags` are the sanctioned measurement consumers.
    readers: list[str] = []
    for py in (_REPO_ROOT / "harpyja").rglob("*.py"):
        if py.name.startswith("test_") or py.name == "bakeoff_config.py":
            continue
        visitor = _ServedVariantReaderVisitor(py.name)
        visitor.visit(ast.parse(py.read_text(), filename=str(py)))
        readers.extend(visitor.readers)
    assert set(readers) <= _SANCTIONED_READERS, readers
