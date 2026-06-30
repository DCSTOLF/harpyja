---
spec: "0013"
closed: 2026-06-30
---

# Changelog — 0013 FastContext source swap

## What shipped vs spec

- A pure dependency-**source** swap: the Tier-1 Scout FastContext git source moved
  from `microsoft/fastcontext` to `DCSTOLF/fastcontext` at the **same pinned rev**
  `1522d6d6b5e040e817b468e12826662aa069a8b0`. The resolved code is byte-identical —
  **no version bump, no behavior change.**
- `pyproject.toml` `[tool.uv.sources].fastcontext` `git` URL →
  `https://github.com/DCSTOLF/fastcontext` (rev unchanged).
- `uv.lock` regenerated — the `[[package]]` source entry and the dependency-edge
  marker now point at DCSTOLF at the identical rev; `uv lock --check` passes.
- `README.md` and `FASTCONTEXT_INSTALL.md` clone-URL references → DCSTOLF.
- New drift-guard test `harpyja/test_fastcontext_source.py` — 5 tests asserting the
  git source == DCSTOLF, the rev is unchanged (AC3 byte-identity guard), and no
  `microsoft/fastcontext` URL survives in `pyproject.toml`, `uv.lock`, or the docs.
- No `harpyja/scout/` code changed; the `ScoutBackend` / `ScoutEngine` / `client.py`
  Path-A/B seams are untouched (this is a source-of-supply change, not a code change).

## Deviations

- **Prose attribution intentionally left as-is (explicit out-of-scope).** "Microsoft
  FastContext" attribution in `README.md` / `FASTCONTEXT_INSTALL.md` prose — and in
  `.speccraft/architecture.md`, `.speccraft/index.md`, `ARCHITECTURE.md`, `SPEC.md`
  — remains, because the fork *is* a fork of Microsoft's project, so the attribution
  stays accurate. Only the clone/source **URLs** were swapped, not the credit. No
  substantive deviation.
- **Plan's "fork not pushed / network resolution" risk was moot.** The fork resolved
  and built cleanly on the first `uv run`, so the contingency never fired.
- This spec is **only** the source swap. Carrying actual local FastContext patches
  (the open `format_citations` crash, recommended-Q4 quality leads) is a deliberate
  later effort — out of scope here.

## Files touched

- `pyproject.toml` — `[tool.uv.sources].fastcontext` git URL → DCSTOLF (rev unchanged).
- `uv.lock` — regenerated; source entry + dependency-edge marker → DCSTOLF, same rev.
- `README.md` — clone-URL reference → DCSTOLF.
- `FASTCONTEXT_INSTALL.md` — clone-URL reference → DCSTOLF.
- `harpyja/test_fastcontext_source.py` (new) — 5 source/rev/no-stale-URL drift-guard tests.

## Verification status

- **683 unit pass** (678 + 5 new), ruff clean.
- **38 Scout integration tests pass** against the fork (live endpoint) — confirms
  AC5 "tests pass unchanged" / no behavior change.
- `uv lock --check` resolves 144 packages, consistent.

## Acceptance criteria — all met

- **AC1** — `pyproject.toml` git URL + rev correct.
- **AC2** — lock resolves from the fork and is consistent (`uv lock --check`).
- **AC3** — resolved hash byte-identical (rev unchanged).
- **AC4** — no `microsoft/fastcontext` URL in non-spec / non-history files.
- **AC5** — import + Scout tests pass unchanged.
