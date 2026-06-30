# History archive

Verbatim records demoted from history.md by /speccraft:history:compact. Append-only.

## 2026-06-26 — Wave 2 symbol layer completed (all 10 grammars) + no-silent-coverage lockstep

**Spec:** specs/0004-symbol-layer-remaining-grammars/
**Decision:** Close the Wave-2 follow-up by adding the remaining eight tree-sitter
grammars — Rust, Java, C#, JavaScript, TypeScript, TSX, C, C++ — behind the
**unchanged** `SymbolEngine` / `Locator` / formatter path, so only more languages
produce records (locate/orchestrator/contract untouched; AC15 held by construction).
Three durable choices were pinned: (1) **No-silent-coverage lockstep invariant.**
Wave 1 already shipped a latent no-false-capability violation — `classify._EXT_TO_LANG`
over-routed all 9 languages while `indexer.SYMBOL_LANGUAGES` was only `{python, go}`,
so a `.rs`/`.ts` file returned `([], None)`: a silent clean-zero indistinguishable
from a genuinely symbol-less file ("we never looked" masquerading as "we looked and
found nothing"). The fix is a permanent invariant `classify.KNOWN_LANGUAGES ==
indexer.SYMBOL_LANGUAGES`, asserted by a new `index/test_routing.py` and re-checked at
every tier boundary: a language's **routing + `engine_identity` slot + extraction
rules ship in the same change**; an unshipped tier stays null-language/ripgrep-only,
never silent zero. (2) **`.h`→C is a scoped, not absolute, guarantee.** Both reviewers
flagged the original "never a wrong-range record" overclaim; impl confirmed it —
tree-sitter-c *tolerates* a bare `class Foo {}` (parses it, no ERROR), so the test
uses `template<…>`, which reliably triggers an ERROR. The shipped guarantee: degrade
only when an `ERROR`/`MISSING` node is present; a C-legal subset of a C++ header
parsing cleanly as `c` is the documented cost of the `.h`→C default, not claimed as
rejected. (3) **Per-grammar identity slots, coupled where the package couples.**
`engine_identity` now enumerates all 10 slots via a `_GRAMMAR_SLOTS` map
(slot → dist, module, language-fn) that replaced the flat `_GRAMMARS` tuple;
`typescript` and `tsx` ship from one `tree-sitter-typescript` package, so they are
two identity keys with one version that bump/absent together (loaded via
`language_typescript()` / `language_tsx()`, not `language()`).
**Why:** Until this spec, the index advertised a symbol tier it delivered for only two
of seven languages — a Rust `fn` or Java method fell to ripgrep line hits, the exact
context-flooding Wave 2 exists to prevent. The lockstep invariant generalizes the
project's no-false-capability rule to *coverage*: routing a capability ahead of its
extraction is itself a false claim. Reuse kept the surface small — `_strip_go_type`
(generic/pointer parent normalization), the `^[A-Z][A-Z0-9_]*$` constant filter, and
`_own_region_errored` (parse-error scoping) were reused verbatim, with a shared
`_emit_named` helper backing Java/C#/JS/C-family.
**Consequence:** Tier 0 now covers all 10 grammars; the symbol-layer adapter is fully
cashed in. Two accepted, documented limitations remain: a C-legal subset of a `.h`
C++ header is parsed as `c`, and `parent` is immediate-only, so two same-named members
under different outer types/namespaces both match `Foo::bar` (a known addressing
ambiguity, not a regression). The 5-grammar follow-up opened at 0003's close is now
closed by this spec; **Wave-2.1 substring/fuzzy matching** remains the sole open
follow-up (still needs its own ranking rules + ACs). Method addressing stays a
formatter-ranking signal (a subset of name results glued by `.`/`::`), not a
membership filter.

## 2026-06-26 — Wave 2 symbol layer shipped (tree-sitter, Python + Go)

**Spec:** specs/0003-wave-2-symbol-layer/
**Decision:** Add a Tier-0, model-free symbol layer that surfaces a symbol's
**definition above its call sites**, filling the `symbols_indexed` / `degraded`
slots Wave 1 reserved. (1) A tree-sitter extractor (`symbols/`) parses **Python and
Go only** — defs-only, classified by **syntactic form** (no type inference) — into a
byte-reproducible `symbols.jsonl` ordered by the total key
`(path, start_line, end_line, kind, name)`; the other five grammars are a deliberate
follow-up spec. (2) The records file is paired with a tiny self-verifying
`symbols.meta.json` sidecar carrying `engine_identity` (tree-sitter runtime + each
pinned grammar version) + `record_count` + a sha256 `content_digest` over the
records' exact bytes; a refresh forces a full symbol rebuild — independently of the
`(mtime, size)` gate — on any missing/truncated record file, missing meta,
engine-identity mismatch, or fingerprint mismatch, committing **records-first,
meta-last** via same-dir temp + `os.replace`. (3) Graceful degradation has two
distinct, persisted causes: `grammar-missing` (absent/load-fail grammar → zero
symbols) and `parse-error` (scoped to a definition's **own region excluding
nested-definition subtrees**, so a broken method never suppresses its clean
enclosing class); `degraded` is persisted per-file on the manifest entry so a
no-reparse refresh re-surfaces it (total-in-index, like `symbols_indexed`). (4)
`SymbolEngine` implements the shared **`Locator` protocol** (exact, case-sensitive
name matching + `.`/`::` method addressing; substring matching deferred to Wave 2.1);
the orchestrator composes it with the ripgrep Locator into one `CodeSpan` stream and
never branches, and the formatter applies a placeholder **definition boost** between
`prior` and density. A no-symbol-match query degrades byte-identically to the Wave-1
ripgrep-only path.
**Why:** A raw line-grep can't tell a definition from its hundred call sites — the
exact context-flooding the project exists to prevent. The symbol layer is the first
tier where structure, not just text, drives the answer, while staying zero-cost and
fully local (air-gap untouched, audited). The self-verifying sidecar is the durable
lesson from four cross-review rounds (D15 changed three times): **an untrusted
derived artifact must authenticate its own generation — a content fingerprint — not
just its producer's identity**; engine-identity alone misses a records-first/meta-last
crash residue and a clean newline truncation, the fingerprint catches both.
**Consequence:** Tier 0 is now deterministic + symbol-aware: index → (ripgrep +
symbols) → citation formatter, all behind the same `harpyja_locate` contract. Two
deliberate follow-ups are opened: the **five remaining grammars** (Rust, JS/TS, C#,
Java, C/C++ — the extractor is built so adding a grammar is additive) and **Wave-2.1
substring/fuzzy matching** (it needs its own ranking rules + ACs and would otherwise
create a fuzzy match-state that could promote the wrong definition over a correct
text hit). Symbol-boost weights are documented placeholders tuned later but must
preserve the AC ordering.

## 2026-06-26 — Wave 1 deterministic core shipped

**Spec:** specs/0002-wave-1-deterministic-core/
**Decision:** Replace the Wave 0 `harpyja_locate` stub with a model-free Tier-0
locator and pin seven choices that the deterministic floor stands on:
(1) `.gitignore` is matched via the `pathspec` library's `gitwildmatch` — never by
invoking `git` — so non-git directories index correctly and nested per-dir
`.gitignore`, negation, dir-only, anchored, and `**` rules all work.
(2) Incremental indexing is a two-level scheme: a cheap `(mtime, size)` gate avoids
re-hashing, the sha256 hash is the change-of-record, deleted files are pruned, and
`--rehash` is the documented escape hatch for the coarse-mtime same-second/same-size
edge. (3) "Ensure-index" is *defined as* a full incremental refresh on every
`locate` — staleness is not a separate heuristic; the incremental pass *is* the
reconciliation, and it builds from scratch when no manifest exists. (4) `rg` on
`PATH` is a hard precondition for **search/locate only** (typed `RipgrepMissingError`,
named in `doctor`), never for `harpyja_index`, which is pure Python. (5) Index
artifacts default to `<repo>/.harpyja/` (self-ignoring `.gitignore`=`*`, root
`.gitignore` untouched) and fall back to `${XDG_CACHE_HOME:-~/.cache}/harpyja/<repo-hash>/`
(sha256 prefix of the abs realpath) when the repo is unwritable. (6) Ripgrep search
is literal-by-default (`--fixed-strings`); validated regex is deferred. (7) The
locate contract treats its three fields distinctly — `max_results` is a mandatory
clamp, `mode` is accept-validate-flag (inert in Wave 1 but never a silent no-op), and
`language_hint` is best-effort with *distinct* notes for an unrecognized hint vs
null-language exclusion.
**Why:** Establish an honest, reproducible, zero-cost deterministic floor that every
later tier (Scout, Deep, the verification gate) is purely additive on top of. The
hard `rg` fail and the distinct hint notes both follow the same honesty principle:
a silent empty result that reads as "nothing found" is worse than a loud, actionable
failure. Matching `.gitignore` without `git` keeps indexing dependency-free and
correct on non-git trees.
**Consequence:** Wave 2+ adds the symbol layer (`symbols_indexed`/`degraded` are the
reserved slots) and higher tiers behind the same `harpyja_locate` contract and the
same manifest. The `(mtime, size)` gate's coarse-granularity miss is a known,
documented approximation gated by `--rehash`. Toml config stayed flat (mirroring
`Settings` fields) rather than SPEC §5's `[search]/[tools]/[index]` tables — a future
nested-table need must add a flattening layer behind its own test.

## 2026-06-26 — Wave 0 foundations shipped

**Spec:** specs/0001-wave-0-foundations/
**Decision:** Ship the agent↔server skeleton with a stub-first MCP contract and
four foundational choices: (1) the air-gap is enforced in exactly one helper,
`gateway.assert_local`, reused for both the outbound endpoint and — via
`DEFAULT_HTTP_HOST=127.0.0.1` plus the CLI `--allow-remote-bind` opt-out — the
inbound HTTP listener; loopback = `127.0.0.0/8` / `::1` / literal `localhost`.
(2) `harpyja_locate` is registered and returns a schema-valid empty
`LocateResult` (`confidence="low"`) per SPEC §2.1 — no retrieval. (3) Config
resolves with precedence defaults < `harpyja.toml` < `HARPYJA_*` env <
per-request override, on a frozen `Settings` dataclass. (4) Tests live next to
the package under test (`test_*.py`); no top-level `tests/` root.
**Why:** Pin the riskiest integration surface (MCP registration, which differs
between Claude Code and Codex) early and make later waves purely additive; keep
the air-gap guarantee auditable in one place rather than scattered across layers.
**Consequence:** Wave 1+ adds retrieval behind the existing `harpyja_locate`
contract without touching transport, config, or the air-gap. The inbound bind
default and `assert_local` are the security-load-bearing surfaces to preserve.

## 2026-06-26 — speccraft adopted

**Spec:** specs/0001-speccraft-v1/
**Decision:** Adopt speccraft for spec-first TDD workflow.
**Why:** Establish disciplined spec-first development from day one.
**Consequence:** All future code changes go through `/spec:new`.

