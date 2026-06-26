"""RED (task 1): the package skeleton must exist and be importable.

Drives AC2 — all eight subpackages plus cli.py import cleanly. This file lives
next to the package under test per repo conventions (no top-level tests/ root).
"""

import importlib

import pytest

SUBPACKAGES = [
    "harpyja.server",
    "harpyja.orchestrator",
    "harpyja.index",
    "harpyja.symbols",
    "harpyja.scout",
    "harpyja.deep",
    "harpyja.gateway",
    "harpyja.config",
]


@pytest.mark.parametrize("module", SUBPACKAGES)
def test_subpackages_importable_all_eight(module):
    assert importlib.import_module(module) is not None


def test_cli_module_importable():
    assert importlib.import_module("harpyja.cli") is not None
