---
spec: "0013-fastcontext"
---

# Tasks

- [x] T1 — RED: add `harpyja/test_fastcontext_source.py` asserting pyproject git source == DCSTOLF, rev unchanged, no microsoft URL in pyproject
- [x] T2 — GREEN: swap `pyproject.toml:60` git URL to `DCSTOLF/fastcontext` (rev byte-identical)
- [x] T3 — RED: extend test file to assert `uv.lock` points at DCSTOLF (source + edge marker, rev intact) and README/FASTCONTEXT_INSTALL have no microsoft URL
- [x] T4 — GREEN [NETWORK]: `uv lock` regen from fork, edit README.md:77 + FASTCONTEXT_INSTALL.md:40,47, then `uv lock --check`
- [x] T5 — VERIFY/REFACTOR: full unit suite + ruff; `import fastcontext`; Scout integration tests [LIVE ENDPOINT]; hoist shared path/read helper
