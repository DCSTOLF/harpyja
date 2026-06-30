---
id: "0013"
title: "fastcontext"
status: closed
created: 2026-06-30
authors: [claude]
packages: []
related-specs: ["0007-fastcontext"]
---

# Spec 0013 — fastcontext

## Why

The Tier 1 "Scout" dependency is currently pinned to the upstream
`github.com/microsoft/fastcontext` git source. We need to source it from the
fork `github.com/DCSTOLF/fastcontext` instead — pinning the **same commit**
(`1522d6d6b5e040e817b468e12826662aa069a8b0`, short `1522d6d`) so the resolved
code is byte-identical today, while giving us a controlled source we can carry
local fixes on (e.g. the open FastContext `format_citations` crash and the
recommended-Q4 quality leads). This is a pure dependency-source swap, not a
version bump.

## What

Repoint the `fastcontext` git dependency from `microsoft/fastcontext` to
`DCSTOLF/fastcontext` at the identical pinned revision, regenerate the lock so
the install resolves from the fork, and update the user-facing install/source
references in the docs that quote the clone URL.

## Acceptance criteria

1. `pyproject.toml` declares `fastcontext = { git =
   "https://github.com/DCSTOLF/fastcontext", rev =
   "1522d6d6b5e040e817b468e12826662aa069a8b0" }` — the `rev` is unchanged from
   the current pin; only the `git` URL changes.
2. `uv.lock` resolves `fastcontext` from
   `https://github.com/DCSTOLF/fastcontext?rev=1522d6d6b5e040e817b468e12826662aa069a8b0`
   (both the `[[package]]` `source` entry and the dependency-edge `git = …`
   marker), and `uv sync` / `uv lock --check` succeed offline-of-other-changes
   (i.e. the lock is consistent with `pyproject.toml`).
3. The pinned commit hash is identical before and after the change in both
   `pyproject.toml` and `uv.lock` — a `grep` for the old hash still finds the
   same `1522d6d6b5e040e817b468e12826662aa069a8b0` value, never a different rev.
4. `grep -rn "github.com/microsoft/fastcontext"` over tracked **non-spec,
   non-history** files returns nothing — the clone-URL references in
   `FASTCONTEXT_INSTALL.md` (the `uv add "git+https://…"` examples) and
   `README.md` (the FastContext link) point at `DCSTOLF/fastcontext`.
5. The package imports and Scout still loads: `uv run python -c "import
   fastcontext"` succeeds and the existing Scout integration tests pass
   unchanged (no behavior change, since the commit is identical).

## Out of scope

- Bumping the FastContext revision or pulling any new upstream/fork commits —
  the rev stays pinned to `1522d6d…`.
- Prose attribution wording ("Microsoft FastContext") in ARCHITECTURE.md,
  SPEC.md, IMPLEMENTATION_PLAN.md, `.speccraft/index.md`, and source-file
  docstrings — the fork is a fork of Microsoft's project, so upstream
  attribution remains accurate and is left as-is.
- Historical/spec artifacts that quote the old URL as a record (e.g.
  `specs/0007-fastcontext/`, `.speccraft/history.md`) — these document what was
  true at the time and are not rewritten.
- Any code change inside the FastContext fork itself (carrying local patches is
  the motivation but a separate, later effort).

## Open questions

_none_
