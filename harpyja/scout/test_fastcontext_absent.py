"""Spec 0025 (T12/T13, AC4): executable consumer-absence guard for the FastContext surface.

An import-absence / public-name assertion that ROTS FALSE if the FastContext module
reappears or a deleted public name resolves — durable where a point-in-time grep
would silently go stale. Covers the adapter/client modules, the FC-only Settings
fields, the FC error causes, and the FC imports in `wiring` / `locate_probe`, while
asserting the served `scout_model` gate baseline was NOT swept away with them.
"""

from __future__ import annotations

import ast
import importlib

import pytest


def _imported_modules(module) -> set[str]:
    """The set of module names imported by `module`'s source (AST, not a text grep)."""
    with open(module.__file__, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
        elif isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
    return names


def test_fastcontext_adapter_module_removed():
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("harpyja.scout.fastcontext")


def test_scout_client_module_removed():
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("harpyja.scout.client")


def test_fastcontext_tool_whitelist_module_removed():
    # `scout.tools.build_tool_whitelist` built FastContext's read/glob/grep/model
    # whitelist; the explorer uses `explorer_tools.build_explorer_tools` instead.
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("harpyja.scout.tools")


def test_wiring_imports_no_fastcontext():
    import harpyja.scout.wiring as wiring

    imported = _imported_modules(wiring)
    assert not any(m.startswith("fastcontext") for m in imported)
    assert "harpyja.scout.client" not in imported
    assert "harpyja.scout.fastcontext" not in imported


def test_locate_probe_imports_no_upstream_fastcontext():
    # `scout_stack_available` no longer hard-imports the upstream `fastcontext` package
    # (which would false-skip after the dependency drop).
    import harpyja.eval.locate_probe as lp

    imported = _imported_modules(lp)
    assert not any(m.startswith("fastcontext") for m in imported)


def test_fc_only_scout_settings_fields_removed():
    import dataclasses

    from harpyja.config.settings import Settings

    field_names = {f.name for f in dataclasses.fields(Settings)}
    for gone in ("scout_max_tokens", "scout_temperature", "scout_reasoning_effort"):
        assert gone not in field_names, f"{gone} should be removed with the FC plumbing"


def test_scout_model_gate_baseline_preserved():
    # The FC cleanup must NOT sweep away the served `scout_model` gate baseline.
    from harpyja.config.settings import Settings

    field_names = {f.name for f in __import__("dataclasses").fields(Settings)}
    assert "scout_model" in field_names
    assert Settings().scout_model  # a non-empty served default remains


def test_fc_error_causes_removed():
    from harpyja.scout import errors

    assert not hasattr(errors, "FASTCONTEXT_MISSING")
    assert not hasattr(errors, "CLI_MISSING")
