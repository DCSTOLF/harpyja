---
spec: "0002-wave-1-deterministic-core"
title: "Wave 1 — Deterministic core (indexer + ripgrep)"
date: 2026-06-26
round: 2
reviewers: [codex, claude-p]
quorum: 1 approve-or-approve-with-comments
verdict: approve-with-comments
generated: 2026-06-26T00:00:00Z
---

# Cross-model review — 0002-wave-1-deterministic-core (Round 2)

## codex

**Verdict:** changes-requested

Concerns:
- Default artifact location writes `<repo>/.harpyja/` + `.harpyja/.gitignore` into the target repo, flagged as conflicting with the read-only locator guardrail.
- `rg` made a hard precondition for `harpyja_index` even though indexing (walker + hashing + manifest write) is pure Python and does not need ripgrep; unnecessarily couples index creation to search availability.
- External cache fallback underspecified: `$XDG_CACHE_HOME` unset/unavailable/platform-dependent behavior not defined; `<repo-hash>` derivation not specified; collision behavior not addressed.
- `harpyja_locate` "build if stale" — "stale" not defined precisely enough to implement or test; no AC exercises stale-then-rebuild distinctly from the missing-index path.
- Symlink handling in the manifest unclear: are symlink files excluded during the walk, included as metadata-only, or rejected only at read time?

Suggestions:
- Scope `rg` hard-precondition to locate/search paths only; `harpyja_index` should succeed without `rg`.
- Define cache-dir resolution explicitly (`$XDG_CACHE_HOME` else `~/.cache`; stable repo hashing via abs realpath; collision behavior).
- Add an AC for locate refreshing stale manifests after modify/delete/rename.
- State whether symlinks are skipped during indexing (`follow_symlinks=false` already in spec, but manifest policy is unspoken).
- Add one-line acknowledgement that `<repo>/.harpyja/` is a derived-artifact exception, not a repo modification.

Guardrail violations flagged: read-only locator @ B6 / AC17 — DROPPED in synthesis (see below).
Convention violations flagged: graceful-degradation-over-raising @ RipgrepEngine / AC9 — DROPPED in synthesis (see below).

---

## claude-p

**Verdict:** approve-with-comments

Concerns:
- `(mtime, size)` gate false-negative: a same-second, same-size content edit (coarse mtime on some filesystems) is silently missed; the hash (the stated change-of-record) is never computed in that case. No force-rehash or full-reindex escape hatch is specified.
- Orchestrator "stale" undefined: AC10 says locate builds the index "if missing or stale" but staleness detection is not pinned, nor is it specified whether "ensure index" always runs a full incremental refresh (re-walks the tree). No AC exercises stale-to-rebuild as a distinct case from AC2.
- Unrecognized `language_hint` value unspecified: an unsupported hint (e.g. `'klingon'`) silently filters to empty — close to the no-false-capability-claims trap. P6's note covers null-language exclusion, not an unrecognized hint; the two cases must be distinguishable to the caller.
- Atomic-write (P4) breaks across filesystems: if the temp file is not in the same directory as the final manifest, `rename` degrades to copy+unlink — which is exactly the external-cache fallback (B6) case. Temp file must be co-located with the final manifest.
- Read-only-guardrail tension on the default `<repo>/.harpyja/` path: architecture.md blesses derived artifacts and B6 mitigates (self-ignore, untouched root `.gitignore`, cache fallback), so it is defensible — but writing into the repo dir by default deserves an explicit one-line note, not silent treatment.

Suggestions:
- Pin `harpyja_read` line-index semantics (1- vs 0-indexed, inclusive/exclusive end, returned range = requested or clamped).
- Define what `<repo-hash>` hashes (e.g. abs realpath of the repo dir).
- Specify deterministic manifest ordering and tie-break (the spec calls it "ranked" but gives no ordering for the manifest file itself, distinct from result ranking).
- Clarify `files_indexed` vs `languages` relationship: null-language files are counted in `files_indexed` but excluded from the `languages` map, so `sum(languages.values()) <= files_indexed`; make this explicit.
- Add a test-shape note for the `rg`-absent error: it should be a typed, actionable error and `doctor` should name ripgrep specifically.

Guardrail violations flagged: none.
Convention violations flagged: none.

---

## Synthesis

### Dropped false positives (recorded here to prevent re-litigation in any future round)

**codex read-only guardrail violation — DROPPED.**
`.speccraft/architecture.md` explicitly classifies `manifest + symbol index` as "derived artifacts," and SPEC §4.1 places them under `.harpyja/` in the repo. Writing derived artifacts to a self-ignoring gitignored subdirectory is architecturally sanctioned and does not violate the read-only locator guardrail (which targets mutations to the target repo's source code and tracked files). claude-p independently assessed this as defensible. The narrower, agreed point — that the spec should acknowledge the derived-artifact exception explicitly with one sentence — is captured as R10 below.

**codex graceful-degradation convention violation — DROPPED.**
Ripgrep is the Wave-1 deterministic floor. When the floor binary is absent there is no degraded answer Harpyja can honestly provide; failing loudly and actionably (via `doctor`) is strictly better than returning a silent empty result that the caller reads as "nothing found." This matches the conventions.md principle that a degraded answer must be honest — an empty result that masquerades as a real search outcome is not honest. claude-p reasoned the same and declined to flag this. The rg-floor tension is captured as a one-line note in R10.

### Accepted refinements to fold in before planning

These do not block the `reviewed` status but must be applied as clarifications in `spec.md` before implementation planning begins. None require redesign.

**R1 — Scope `rg` precondition to locate/search only.**
`harpyja_index` (walker + hashing + manifest write) is pure Python; it does not invoke `rg`. The current spec text at B4/AC9 conflates `harpyja_index` with `harpyja_locate` as joint failure points. Restrict the hard `rg`-precondition to `harpyja_locate` and the `RipgrepEngine.search` path; `harpyja_index` should succeed without `rg` present.

**R2 — Define "stale" or commit to always-incremental-refresh.**
AC10 says locate builds the index "if missing or stale" without defining stale. Either pin a concrete definition (e.g. any manifest entry whose `mtime`/`size` no longer matches disk, or a manifest older than N minutes) or state that "ensure index" always runs a full incremental refresh (re-walks the tree, re-uses unchanged entries). Add a distinct AC that exercises stale-to-rebuild separately from the missing-index path of AC2.

**R3 — Distinguish unrecognized `language_hint` from null-language exclusion.**
An unrecognized hint (e.g. `'klingon'`) and a valid hint applied to a repo with no matching files both produce empty results, but for different reasons. The spec and notes must make these distinguishable to the caller: unrecognized hint should surface a warning in `notes` (e.g. "language_hint 'klingon' is not a known language; no files were filtered"); null-language exclusion is separately surfaced per P6.

**R4 — Atomic-write temp file must be co-located with final manifest.**
P4 specifies write-to-temp-then-rename. For `rename` to be atomic the temp file must be on the same filesystem as the target. In the external-cache fallback case (B6), the temp file must be in the same directory as `manifest.jsonl`, not in a system `/tmp`. Spec should say: "temp file is written to the same directory as the final manifest before rename."

**R5 — `(mtime, size)` gate escape hatch.**
The two-level gate is intentionally cheap but can miss same-second, same-size edits. Add an honest AC note acknowledging this limitation and specify an escape hatch: either a `--rehash` / `--full-reindex` flag that forces hash recomputation for all files, or documentation that `(mtime, size)` gate is approximate and the hash is only the change-of-record when the gate fires.

**R6 — Pin `harpyja_read` line-index semantics.**
AC15 specifies the `{path, start, end, language, content, truncated}` return shape but does not pin whether `start`/`end` are 1-indexed or 0-indexed, whether `end` is inclusive or exclusive, and whether the returned range is exactly `[start, end]` or clamped. One sentence is sufficient: e.g. "1-indexed, end inclusive, returned range is clamped to file length with `truncated=true` when clamping occurs."

**R7 — Define `<repo-hash>` and cache-dir resolution.**
AC17 references `$XDG_CACHE_HOME/harpyja/<repo-hash>/` without defining either component. Specify: `<repo-hash>` = a stable short hash of the absolute realpath of the repo dir (e.g. first 12 hex chars of SHA-256 of the abs realpath); cache-dir resolution = `$XDG_CACHE_HOME` if set, else `~/.cache` (POSIX) / `%LOCALAPPDATA%` (Windows) / `~/Library/Caches` (macOS). Collision behavior (two repos hashing to the same prefix) should be noted as astronomically unlikely but the full hash is available if needed.

**R8 — Deterministic manifest ordering and tie-break.**
The spec defines result-ranking order (`prior` + match density, tie-break on `(path, start_line)`) but does not specify the order of lines in `manifest.jsonl` itself. If the manifest ordering is significant for reproducibility or diffing, state it (e.g. lexicographic by `path`). If it is not significant, say so explicitly.

**R9 — `files_indexed` vs `languages` relationship.**
AC6 specifies `{files_indexed, symbols_indexed: 0, languages: {<lang>: <count>}, ...}`. Null-language files are counted in `files_indexed` (AC5) but have no key in `languages`. Make the relationship explicit: `sum(languages.values()) <= files_indexed`; the gap is the count of null-language files.

**R10 — One-line notes on derived-artifact exception and rg-floor tension.**
Add one sentence to §What / Artifact location (B6): "Writing to `<repo>/.harpyja/` is not a violation of the read-only-locator guardrail; the manifest and symbol index are classified as derived artifacts by architecture.md." Add one sentence to §What / RipgrepEngine: "When `rg` is absent, there is no honest degraded answer (an empty result would be indistinguishable from 'nothing found'); hard failure with an actionable error is the correct posture."

**R11 — Symlink policy in manifest.**
The indexer sets `follow_symlinks=false`. The spec should state the consequence for the manifest: symlinks encountered during the walk are skipped and do not appear as manifest entries. (Path confinement at read time via `realpath` is already covered by B5/AC16 and handles the case where a user passes a symlink path directly to `harpyja_read`.)

---

## Verdict rationale

Quorum is met: claude-p approved with comments. codex's verdict of changes-requested reflects round-1-style blockers that were substantively addressed in the revised spec; the two guardrail/convention violations codex flagged are false positives per the adjudication above and do not carry over. The remaining concerns from both reviewers are clarifications and precision improvements — none require redesign of the architecture, data model, or AC structure. The spec as revised correctly closes all six round-1 blockers (B1–B6) and all six polish items (P1–P6). R1–R11 above are editorial refinements to be folded into `spec.md` during planning.

**Status: reviewed. No third review round required unless a redesign emerges during planning.**

**Action:** Fold R1–R11 into `spec.md` as inline clarifications (one to two sentences each). Update the spec `status` field from `draft` to `reviewed`. Proceed to planning once edits are applied.
