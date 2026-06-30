# Packaging domain

Consolidated, current requirements for packaging, the package skeleton, and the
dev toolchain. Each line carries its originating spec(s) as provenance.

- Package targets Python ≥3.12 via `uv` / `pyproject.toml`; `ruff` (lint) and `pytest` (test) are wired and pass. (spec 0001)
- Package skeleton is `harpyja/{server, orchestrator, index, symbols, scout, deep, gateway, config}/` plus `harpyja/cli.py`, all importable. (spec 0001)
- FastContext is a pinned `git` dependency (no PyPI) sourced from the `DCSTOLF/fastcontext` fork at SHA `1522d6d6b5e040e817b468e12826662aa069a8b0` (same commit as the original `microsoft/fastcontext` pin, byte-identical resolution) so local fixes can be carried; `requires-python >=3.12`. (specs 0007, 0013)
