# History

Append-only. Newest first.

## 2026-06-27 — Wave 4 Deep (Tier 2) shipped — dspy.RLM, sandbox, layered explorer-loop bounds

**Spec:** specs/0006-wave-4-deep-rlm/
**Decision:** Land Harpyja's strongest, most expensive tier — Tier 2 Deep, a
`dspy.RLM` explorer running inside a Deno/Pyodide sandbox whose **entire world** is
four bounded, read-only host tools — reached only via `mode=deep`, and make the
Wave-3 provisional `deep` real by shipping routing **and** implementation together.
`mode=auto` stays byte-identical and model-free; `mode=fast` stays Scout. Eight
durable choices were pinned. (1) **Layered explorer-loop enforcement — no single
ignorable counter is load-bearing.** An untrusted code-writing loop is bounded at
different seams: *externally enforced* (the backend cannot evade) `deep_max_tool_calls`
(host-tool wrappers stop dispatching), `deep_token_ceiling` (the Gateway refuses
further completions), and `deep_wall_clock_ms` (a host deadline) are the load-bearing
trio; `deep_max_depth` / `deep_max_subqueries` are *host-mediated* at the spawn seam
with **recorded residual risk** (if the runtime exposes no spawn/recurse hook they
become cooperative) and are **transitively contained** by the external trio — every
sub-query spends tool-calls, tokens, and wall-clock, so a recursion storm terminates
even if the mediation seam is cooperative. A bound the third party can ignore is not
a bound. (2) **Wall-clock requires an out-of-band, host-terminable subprocess.** A
same-thread/same-event-loop deadline can never fire while a synchronous WASM busy
loop blocks it; `DeepRunner` therefore splits an in-process counter facet
(unit-testable, no process) from an out-of-band `run_isolated` worker the host
**hard-kills** — enforcement by termination, never cooperative cancellation; proven
against a genuine `while True: pass` (AC10) and a real RLM runaway (AC10a). (3)
**Typed-failure-only degradation boundary.** Deep degrades to Scout best-effort
**only** on a typed `DeepUnavailable` (`sandbox-absent` / `rlm-down` / `backend-error`);
weak or zero citations are an honest Tier-2 result, **not** a degrade — treating weak
output as a reason to drop a tier would be the ungated escalation the deferred Wave-5
Verification Gate is meant to govern, and must not be smuggled in here. (4)
**`deep-truncated:<bound>` is a stable, caller-visible non-degrade note** (one of
`depth` / `subqueries` / `tool-calls` / `tokens` / `wall-clock`) — a budget
truncation is never silently indistinguishable from a complete run and never a
tier-degrade. (5) **RlmBackend air-gap via `assert_local` on the endpoint.** The real
`dspy.RLM` owns its own `dspy.LM` (litellm) and accepts no model_fn, so it cannot be
routed through `gateway.complete` as the spec assumed; instead `RlmBackend` calls
`gateway.assert_local(settings.lm_api_base)` **before** constructing the LM (single
air-gap helper, no parallel check) and the air-gap is **proven** by the network-deny
integration test (AC12) — assumption-verified-by-test, not asserted. (6) **`DeepEngine`
dual surface.** It self-seeds Tier-0 before the backend and exposes both `.search` for
`Locator` conformance and `run() -> (citations, truncated_bound)` because the
truncation bound is metadata the bare `list[CodeSpan]` contract cannot carry. (7)
**Sandbox isolation verified by test, residual risk recorded.** In the real sandbox an
ambient `open()` (outside *and* inside the repo — the latter would bypass `read_span`'s
clamps) and a non-loopback socket connect all fail (AC8b); the four-tool surface is
also pinned by a deno-less positive-equality `[unit]` whitelist (AC8a). The
runtime-change residual risk is recorded, exactly as the Wave-3 FastContext in-process
egress risk was. (8) **Lockstep guard inversion shipped atomically:** the two Wave-3
guards asserting `deep` emits *no* Tier-2 marker were deleted and replaced by the
inverse invariant in the same change — the suite never holds both sides.
**Why:** The hardest retrieval — trace a request across packages, find every consult
of a budget — needs *iteration* (search, read, partition, spawn sub-queries, pull only
what matters into token space), which a single Scout pass cannot do without blowing the
context window. Because the RLM *writes and runs code* against the host tools, it is an
untrusted **caller** and untrusted **code**: the confinement Wave 3 hardened at the
FastContext boundary now applies one layer deeper, at every host tool, and the bounds
had to be enforced where the backend cannot evade them.
**Consequence:** Deep is **not cached** (model-backed/non-deterministic, no
engine-identity slot — like Scout). Verified live against dspy 3.2.1 + Deno 2.9.0 +
Ollama (loopback) + ripgrep 15.1.0 (cold ~50s, warm ~15s); a weak 4B model means the
live ACs assert pipeline *shape* (valid possibly-empty `CodeSpan`s), not citation
quality. Open follow-ups carried forward: the **Verification Gate + Tier-0→1→2
auto-escalation ladder** (Wave 5 — `mode=auto` still does not climb); the **FastContext
package** for Scout is still absent (Wave-3 live AC1 still skips); and, still open from
Wave 2, **Wave-2.1 substring/fuzzy matching**.

## 2026-06-27 — Wave 3 Scout (Tier 1) + Model Gateway request path shipped

**Spec:** specs/0005-wave-3-scout/
**Decision:** Land Harpyja's first model-backed tier (Scout, Tier 1) and the Model
Gateway **request path** — the single outbound seam every later tier builds on — as an
explicit-opt-in capability that leaves `mode=auto` byte-identical to Wave 2 with **zero**
Gateway calls. Six durable choices were pinned. (1) **A four-state degradation floor.**
A Scout call resolves to exactly one caller-visible state that never collapses into
another: model-down → Tier-0 citations (`confidence="degraded"`, `tiers_run=[0]`,
`scout-degraded:<cause>` note); Tier-0-has-results vs Tier-0-honestly-empty are kept
distinct by a `+no-matches` suffix; and a Tier-0 hard precondition absent
(`RipgrepMissingError`) **propagates loudly**, never swallowed into a degraded-empty.
(2) **Seed-before-backend ordering makes the loud case win by construction.** `ScoutEngine`
runs its own Tier-0 self-seed *before* the backend (under `mode=fast` the caller skipped
`auto`'s pass), with no try/except around `seed_fn`, so `rg`-missing-and-model-down
surfaces state 4 deterministically — the dangerous composition is impossible by ordering,
not luck. (3) **Resolution-time air-gap reused from Wave 0, with a new guarded request
path.** Rather than the spec's named `NonLoopbackEndpointError`, the new
`ModelGateway.complete()` reuses the single air-gap helper (`assert_local` + `AirGapError`)
and asserts loopback on **resolved** addresses **before** an injected transport is touched
— a non-loopback endpoint raises a loud floor error, deliberately *not* one of the four
degrade states. (4) **`ScoutBackend` Protocol + `FastContextBackend` (injected client)
keep the FastContext dependency swappable** — no top-level hard import, so the sole open
question (FastContext package/version) can never break the suite, and Scout sits behind
the shared `Locator`/`CodeSpan` boundary so callers never branch on engine identity. (5)
**`auto` byte-identical / zero-Gateway lock** landed before any routing (T19) and was
re-checked after the `_tier0_seed` refactor (T27); `index`/`read`/`auto` make zero model
calls. (6) **`mode=deep` lockstep guard** (no-false-capability): `deep` provisionally
mirrors `fast`, attaching a `Deep pending` note and asserting **no** Tier-2 marker (no `2`
in `tiers_run`, no Tier-2 identity/cache key) so its later divergence is not a surprise
regression.
**Why:** Tier 0 goes blind on conceptual / natural-language queries that name no symbol
or literal — the honest Tier-0 answer is "nothing found," and a naive Scout fallback would
silently re-create that phantom. The floor and the seed-ordering exist precisely so a
model-down run can never read as a clean zero. Being the first model wave, the air-gap and
the degradation floor — previously cheap — became load-bearing and are now specified at
the Gateway request path and at resolution time, one helper, auditable in one place.
**Consequence:** Scout is **not cached** (model-backed/non-deterministic, no engine-identity
slot — the Wave-2 cache-slot question does not apply). Open follow-ups carried forward:
**FastContext package/version pinning** (the sole genuinely-open item, de-risked behind the
Protocol); a **process/WASM sandbox** for FastContext's in-process egress (tool injection
can't stop third-party in-process code opening its own socket — Scout has no sandbox unlike
Tier 2 Deep; the containment is an assumption verified by the network-deny integration test
AC11, not an asserted guarantee); and, still open from Wave 2, **Wave-2.1 substring/fuzzy
matching**.

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
