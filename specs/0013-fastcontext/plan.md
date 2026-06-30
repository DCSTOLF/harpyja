---
spec: "0013-fastcontext"
status: planned
strategy: tdd
---

# Plan — 0013-fastcontext FastContext fork source swap

This is a pure dependency-SOURCE swap: the git URL for the `fastcontext` dep moves
from `microsoft/fastcontext` to `DCSTOLF/fastcontext`. The pinned rev
(`1522d6d6b5e040e817b468e12826662aa069a8b0`) is UNCHANGED. The RED test is a
metadata-assertion test that parses `pyproject.toml` (and scans `uv.lock` +
docs) and asserts the new source + unchanged rev — it fails against the current
`microsoft` URL and goes green after the edit.

Verified facts before planning:
- `pyproject.toml:60` — git source under `[tool.uv.sources]` keyed `fastcontext`
  (TOML path: `tool.uv.sources.fastcontext.git` / `.rev`).
- `uv.lock:657` — `[[package]] name = "fastcontext"` `source = { git = "...?rev=<hash>#<hash>" }`.
- `uv.lock:943` — dependency-edge marker `{ name = "fastcontext", git = "...?rev=<hash>" }`.
- `README.md:77` and `FASTCONTEXT_INSTALL.md:40,47` — clone-URL refs.
- New test file home: `harpyja/test_fastcontext_source.py` (sibling to
  `harpyja/test_package_skeleton.py`, per "tests live next to code" convention).

## Test-first sequence

### Step 1 — Metadata assertion test for the git source (RED)
- Add `harpyja/test_fastcontext_source.py`:
  - Module-level constants (single source of truth for the assertions):
    - `EXPECTED_URL = "https://github.com/DCSTOLF/fastcontext"`
    - `EXPECTED_REV = "1522d6d6b5e040e817b468e12826662aa069a8b0"`
    - `LEGACY_HOST = "github.com/microsoft/fastcontext"`
  - `test_pyproject_fastcontext_git_source_is_dcstolf_fork` — parse
    `pyproject.toml` with stdlib `tomllib` (read bytes, `rb`); locate
    `data["tool"]["uv"]["sources"]["fastcontext"]`; assert
    `entry["git"] == EXPECTED_URL`.
  - `test_pyproject_fastcontext_rev_is_unchanged_pin` — same entry; assert
    `entry["rev"] == EXPECTED_REV` (guards AC3: rev must not drift during the
    URL swap).
  - `test_pyproject_has_no_microsoft_fastcontext_url` — assert
    `LEGACY_HOST not in pyproject_text` (raw text scan; AC4 for pyproject).
- Resolve `pyproject.toml` via a path anchored on the test file
  (`pathlib.Path(__file__).resolve().parents[1] / "pyproject.toml"`), not cwd,
  so it passes regardless of pytest invocation dir.
- Tests fail: current `pyproject.toml:60` still has the `microsoft` URL, so the
  `EXPECTED_URL` and "no microsoft URL" assertions fail. (The rev assertion
  already passes — that is intentional; it is a regression guard, not the RED
  driver.)

### Step 2 — Swap the git source in pyproject.toml (GREEN)
- Edit `pyproject.toml` line 60: change only the `git = "..."` value from
  `https://github.com/microsoft/fastcontext` to
  `https://github.com/DCSTOLF/fastcontext`. Leave `rev` byte-for-byte identical.
- All Step 1 tests pass.

### Step 3 — Lock + docs consistency test (RED)
- Extend `harpyja/test_fastcontext_source.py`:
  - `test_uv_lock_resolves_fastcontext_from_dcstolf_fork` — read `uv.lock` as
    text; assert `EXPECTED_URL` appears AND `LEGACY_HOST` does NOT appear
    anywhere in the lock (covers both the `[[package]]` source entry at ~line
    657 and the dependency-edge marker at ~line 943). Also assert `EXPECTED_REV`
    is still present in the lock (AC3 for the lock).
  - `test_docs_have_no_microsoft_fastcontext_url` — read `README.md` and
    `FASTCONTEXT_INSTALL.md`; assert `LEGACY_HOST` is absent from each (AC4 for
    docs). Anchor both paths on `parents[1]` like the pyproject path.
- Tests fail: `uv.lock` still carries the `microsoft` URL at lines 657/943, and
  the two docs still reference `microsoft/fastcontext`.

### Step 4 — Regenerate lock + update docs (GREEN) [NETWORK REQUIRED]
- Run `uv lock` to regenerate `uv.lock` from the new fork URL. NETWORK REQUIRED:
  uv must fetch the fork from `github.com/DCSTOLF/fastcontext` at the pinned rev.
  This is a dev-time/online step (same class as the repo's convert/provision
  steps), NOT a runtime air-gap violation. Confirm the regenerated lock keeps the
  identical rev (AC3) and now points at DCSTOLF in both the source entry and the
  edge marker.
- Edit `README.md:77` — change the `https://github.com/microsoft/fastcontext`
  link target to `https://github.com/DCSTOLF/fastcontext`. (Prose attribution
  wording like "Microsoft FastContext" is out of scope — only the URL changes.)
- Edit `FASTCONTEXT_INSTALL.md:40` and `:47` — change the two
  `uv add "git+https://github.com/microsoft/fastcontext..."` example URLs to
  `DCSTOLF/fastcontext`. Preserve the `@<commit-sha>` / bare-URL forms otherwise.
- Run `uv lock --check` — must pass (AC2: lock consistent with pyproject).
- All Step 3 tests pass.

### Step 5 — Verify + refactor (REFACTOR / VERIFY)
- Run the full unit suite: `uv run pytest harpyja -m "not integration"`.
- Run `uv run ruff check harpyja/test_fastcontext_source.py` (and `ruff format
  --check` if the repo gates formatting) — keep the new test lint-clean.
- AC5 import check: `uv run python -c "import fastcontext"` succeeds.
  NETWORK/INSTALL NOTE: requires fastcontext to be installed from the new fork
  (i.e. `uv sync` after the lock regen, which fetches from DCSTOLF — dev-time
  online step).
- AC5 Scout integration: run `uv run pytest harpyja/scout/test_fastcontext_client.py
  harpyja/scout/test_scout_integration.py`. LIVE-ENDPOINT NOTE: integration
  tests marked `integration` (and any needing a live model endpoint) may be
  env-gated/skipped offline; run them where the endpoint is available to confirm
  "tests pass unchanged" (no behavior change — identical commit, only the mirror
  host differs).
- Refactor: if the pyproject-path / lock-path / docs-path resolution duplicates
  across the four+ test functions, hoist a small `_repo_root()` helper and a
  `_read(name)` reader at module top. All tests still pass.

## Delegation

- Steps 1, 3, 5 (test authoring + ruff) → keep in-thread or delegate to a
  Python test author; pytest + `tomllib` metadata assertions are mechanical.
- Step 4 lock regen → must run in an environment with network access to
  `github.com/DCSTOLF/fastcontext`; delegate to whoever owns the dev/online lane
  (the agent running `uv lock`/`uv sync`).
- Step 5 Scout integration → delegate to an environment with the live model
  endpoint if the integration tests are not skippable offline.

## Risk

- Fork not pushed / rev absent on DCSTOLF/fastcontext → `uv lock` fails to
  resolve. Mitigation: before Step 4, confirm the fork exists and the exact rev
  `1522d6d6b5e040e817b468e12826662aa069a8b0` is present on `DCSTOLF/fastcontext`.
- Rev drift during lock regen (uv resolving a different commit) → violates AC3.
  Mitigation: Step 3's lock test asserts `EXPECTED_REV` is still present and
  `microsoft` is absent; also grep the regenerated lock for the exact hash and
  confirm no other rev appears for fastcontext.
- Offline/air-gapped CI cannot run Step 4 (`uv lock`) or Step 5 import/sync →
  false RED on lock/import tests. Mitigation: flag Steps 4–5 as dev-time online;
  run them in the networked lane and commit the regenerated lock so downstream
  air-gapped runs use the already-resolved DCSTOLF source.
- Test reads pyproject/lock via cwd-relative path and breaks under some pytest
  invocations. Mitigation: anchor all paths on `Path(__file__).resolve().parents[1]`.
