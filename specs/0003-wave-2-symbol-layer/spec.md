---
id: "0003"
title: "Wave 2 — Symbol layer (tree-sitter, Python + Go)"
status: closed
created: 2026-06-26
revision: 3
authors: [claude]
packages: ["harpyja"]
related-specs: ["0002-wave-1-deterministic-core", "0001-wave-0-foundations"]
---

# Spec 0003 — Wave 2 — Symbol layer (tree-sitter, Python + Go)

## Why

Wave 1 gave Harpyja a deterministic, model-free floor: index a repo and answer
point lookups via ripgrep. But a raw line-grep can't tell the **definition** of a
symbol from the hundred places that mention it. Ask "where is `parse_config`?" and
Wave 1 returns every call site interleaved with the one line that actually defines
it, unranked. That is exactly the context-flooding the project exists to prevent.

Wave 2 adds the **symbol layer**: a tree-sitter pass over indexed files that
extracts named definitions into `symbols.jsonl`, plus symbol-aware ranking so a
query that names a symbol surfaces its **definition first**. This fills the
`symbols_indexed` / `degraded` slots Wave 1 reserved (both were hard-wired to
`0` / `[]`) and is the first tier where structure — not just text — drives the
answer. It stays **Tier 0**: no model, zero network egress, fully local parsing.
Every later tier (Scout, Deep) is still additive on top.

Per the user's scope decision, Wave 2 ships **Python and Go only** — two reference
languages taken end-to-end (parse → `symbols.jsonl` → symbol-aware ranking) to
prove the adapter pattern cheaply. The remaining five grammars (Rust, JS/TS, C#,
Java, C/C++) are a **deliberate follow-up spec** opened when this one closes.

## What

A symbol-extraction engine, its integration into the indexer, and a symbol-aware
ranking signal in the locate path — all behind the existing `harpyja_index` /
`harpyja_locate` contracts and the same manifest.

- **SymbolEngine** (`symbols/`): tree-sitter parsers for **Python** and **Go**
  that extract **definitions only** (D1) into per-file symbol records. Parsing is
  fully local; bundled grammars add **no runtime network egress** (the air-gap
  invariant and `gateway.assert_local` are untouched).
  - **Symbol record** — one JSON object per definition, written to
    `symbols.jsonl`: `path` (repo-relative), `language`, `name`, `kind`,
    `parent` (enclosing type/class name, or `null` for top-level), `start_line`,
    `end_line`. **Line semantics** (D2): `start_line`/`end_line` are **1-indexed
    and inclusive**, identical to `harpyja_read` / `CodeSpan`, so a symbol record
    is directly citable without re-deriving ranges.
  - **Kind vocabulary** (D3) — defs only, a closed, documented set classified
    **by syntactic form** (no type inference / value resolution):
    - **Python:** `function`, `method` (a `def`/`async def` whose immediate
      enclosing scope is a `class` body), `class`, and module-level `constant`.
      `async def` carries the same kind as `def`. **`constant` is defined
      precisely** (▶ **chosen for robustness**, resolves review concern P1-c):
      a **module-level** assignment (`X = …`) or annotated assignment
      (`X: T = …`) whose **single** target is a `Name` matching
      `^[A-Z][A-Z0-9_]*$`. Tuple/multiple-target unpacking (`A, B = …`) and
      augmented assignment (`X += …`) are **excluded**. A call-valued constant
      (e.g. `Color = namedtuple(...)`) is still classified `constant` — we
      classify by *syntax*, not by what the right-hand side evaluates to, and
      this limitation is documented rather than hidden.
    - **Go:** `function`, `method` (a func with a receiver), `struct`,
      `interface`, `type` (other named types — aliases, defined types), and
      package-level `const` / `var`. **Receiver normalization** (▶ **chosen for
      robustness**, resolves P1-c): a pointer receiver `(s *Foo)` and a value
      receiver `(s Foo)` both normalize `parent` to `Foo` (the pointer is
      stripped), so a method is addressable by its bare type name regardless of
      receiver form. A **generic** receiver `(s *Stack[T])` also normalizes to
      `Stack` — both the pointer **and** the type-parameter list are stripped
      (round-2 P2 — claude-p).
    - **`parent`** records the **immediately enclosing** class/type name (which
      may itself be nested); Wave 2 stores the immediate parent only, not a
      fully-qualified dotted path.
    - **Imports, references/call sites, and function-local (nested) defs are NOT
      extracted** (out of scope) — `symbols.jsonl` holds top-level and
      class/struct-member definitions only, not a usage graph and not closures.
      Excluding nested/local defs keeps the kind vocabulary closed and every
      `parent` unambiguous.
  - **Graceful degradation** (D4 / hard rule "no parser → ripgrep"): indexing
    **never fails** on a parser problem; the index completes and the condition is
    surfaced in the `degraded` array, with the two causes **distinguishable**
    (each naming the language/file). The two causes are handled distinctly
    (round-2 P1c fix — codex):
    - **Grammar unavailable** (the pinned grammar package can't be imported, or
      fails the runtime/grammar ABI load — round-2 P2, D17): every file of that
      language gets **zero symbol records** (there is no parser, so there are no
      definitions to emit) and is flagged `grammar-missing`. Ripgrep search over
      those files is unaffected.
    - **Parse error** (grammar present, partial tree). **Defined precisely**
      (▶ **chosen for robustness**, resolves review concern P0-1): tree-sitter
      returns a partial tree with `ERROR`/`MISSING` nodes rather than throwing, so
      a binary "failed/succeeded" is meaningless. A definition is **skipped** when
      an `ERROR`/`MISSING` node falls in its **own region — the definition node's
      span EXCLUDING the subtrees of any nested definitions** (round-3 P1 fix —
      claude-p). Here **"nested definition" means any nested definition
      *syntactic form*, extracted or not** (round-4 clarification — claude-p): a
      method body's nested `def` (a function-local def, not extracted, D3) is still
      an excluded region — so a method whose only error is inside a broken local
      `def` is **emitted** with its full range, not skipped (the file is still
      flagged `parse-error`). This scoping is load-bearing: a `class` with a clean
      method `A`
      and a broken method `B` must still emit the **class record and method `A`**,
      skipping only `B` — the literal "any descendant ERROR skips the def" rule
      would wrongly drop the whole class and orphan `A`. We never emit a
      possibly-wrong range for a symbol we couldn't parse cleanly, but a local
      error never suppresses a cleanly-parsed enclosing or sibling definition. The
      file is flagged `parse-error` whenever its tree contains **any**
      `ERROR`/`MISSING` node, **including one outside every definition** (e.g. a
      broken top-level statement, round-2 P1c — claude-p): the flag means "this
      file did not parse cleanly," so the partialness is **never silent** even when
      no definition was directly affected.
    This is the **opposite** of Wave 1's `rg` hard-fail (D5): ripgrep is the
    deterministic floor with no honest degraded alternative, whereas a
    missing/erroring parser **does** have one — fall back to the ripgrep line hit.
    Symbols are an enhancement, not a precondition.
- **Indexer integration** (`index/`): `harpyja_index` writes `symbols.jsonl`
  **alongside** `manifest.jsonl` in the same artifact dir (`<repo>/.harpyja/`,
  with the Wave-1 external-cache fallback unchanged).
  - **`symbols_indexed`** (D6) now reports the real count = the **total number of
    records in `symbols.jsonl` after the refresh** — i.e. total-in-index, **not**
    parsed-this-run (▶ **chosen for robustness**, resolves review concern P1-a;
    an incremental refresh that re-parses nothing still reports the full count).
    `null`-language and grammarless files contribute `0`; the returned
    `languages` map is unchanged (still a file count, not a symbol count).
  - **Per-file `degraded` persisted in the manifest** (D18) (▶ **chosen for
    robustness**, resolves round-3 P1 — the same staleness family D6 closed for
    `symbols_indexed`): each file's degradation outcome (`grammar-missing` /
    `parse-error` / clean) is recorded as a **per-file field on its
    `manifest.jsonl` entry**, written when the file is parsed. Because a file that
    passes the `(mtime, size)` gate **reuses its manifest entry** (D7), its
    degraded status is reused with it — so an incremental refresh that re-parses
    nothing still re-surfaces the **full, accurate `degraded`** array (total-in-
    index, exactly like `symbols_indexed`), never a silently empty `degraded: []`
    for a file that is still partially parsed. Pruning (D8) drops the field with
    the entry. The manifest is the natural home: it is already the per-file
    record-of-record reused across the gate and pruned in lockstep.
  - **Incremental re-parse** (D7): symbols are re-extracted **only** for files the
    manifest re-indexes (i.e. whose `hash` changed). A file that passes the
    Wave-1 `(mtime, size)` gate **reuses its prior symbol records without
    re-parsing** — tree-sitter parsing is gated by the same change-of-record as
    hashing. `harpyja_index --rehash` re-parses every file.
  - **Symbol-artifact integrity + corruption recovery** (D15) (▶ **chosen for
    robustness**, resolves review concern P0-2 — raised by both reviewers):
    `symbols.jsonl` is paired with a tiny sidecar `symbols.meta.json` so the
    record file stays pure and byte-reproducible. The symbol artifact is treated
    as **untrusted derived input** on the read path. The sidecar **authenticates
    a specific records generation** — it carries `schema_version`,
    `engine_identity`, `languages`, **and a `record_count` plus a `content_digest`
    (`"sha256:…"`) computed over the exact bytes of `symbols.jsonl`** (round-3 P0
    fix; the same `sha256` family Wave 1 uses for the manifest). A **full symbol
    rebuild** (re-parse every file's symbols, **without** `--rehash` and
    independently of the manifest `(mtime, size)` gate) is forced whenever **any**
    of these hold:
    - `symbols.jsonl` is **missing, unreadable, or truncated** (a line fails to
      parse as JSON);
    - `symbols.meta.json` is **missing or unreadable** while `symbols.jsonl` is
      present (an inconsistent half-state → rebuild, never trust the records);
    - the meta's **`engine_identity`** does not match the running engine;
    - **the records do not match the sidecar's fingerprint** — the actual line
      count ≠ `record_count`, **or** the recomputed `sha256` of `symbols.jsonl` ≠
      `content_digest` (round-3 P0 fix — both reviewers). This is the check that
      makes the artifact genuinely self-verifying: a clean newline-aligned
      truncation (still valid JSONL, undetected by the per-line parse) **and** a
      records-first/meta-last crash residue (fresh records under a stale meta)
      **both** fail the digest/count and rebuild. AC8's "always correct and
      complete" is therefore true by construction, not by assumption.
    - **Engine identity, not just format version** (P0b fix — claude-p):
      `engine_identity` = the tree-sitter runtime version **plus each pinned
      grammar's version** (`tree-sitter`, `tree-sitter-python`, `tree-sitter-go`),
      alongside a `schema_version` for the record *format*. The rebuild check keys
      on the **full** identity — so **bumping a grammar invalidates the cache**
      even when `(mtime, size)` and `schema_version` are unchanged. Without this, a
      grammar upgrade would silently reuse stale records the new grammar parses
      differently. **A grammar that is absent or fails to load records a stable
      sentinel** for its slot — `"missing"`, or `"load-error:<abi-code>"` for an
      ABI/version-skew load failure (round-4 clarification — codex) — never an
      empty/undefined value, so a degraded run still writes a **reproducible**
      sidecar and the identity comparison stays deterministic across machines.
    - **Absent→present grammar recovery** (round-4 clarification — claude-p): when
      a previously-absent grammar becomes installed, its slot flips from the
      sentinel to a real version, so `engine_identity` changes and the rebuild
      above fires — which both re-parses the now-parseable files **and clears the
      stale `grammar-missing` flags** D18 persisted for them. This is the one
      interaction that stops D18 from re-surfacing a `grammar-missing` for a file
      that is unchanged on disk but now has a grammar; it is load-bearing, so it is
      stated explicitly here rather than left to be derived.
    - **Two-file write ordering** (P1a fix — claude-p): the two artifacts are a
      multi-file commit, so order is load-bearing. The **records (`symbols.jsonl`)
      are committed into place first, then `symbols.meta.json` last** — both via a
      same-dir temp file + `os.replace` (the Wave-1 R4/R8 atomic-commit pattern;
      `os.replace`, not `rename`, for cross-platform atomicity over an existing
      destination). A crash after the records commit but before
      the meta rename leaves fresh records under a *stale/old* meta; that meta's
      `content_digest`/`record_count` no longer match the new records, so the
      fingerprint check above **detects the mismatch and rebuilds** (the meta's
      `engine_identity` alone would not have caught it — the fingerprint is what
      binds the meta to *this* records generation). The reverse order (meta first)
      stays forbidden: it could publish a fresh meta over stale records.
    - **Deterministic sidecar** (P1b fix — both reviewers / convention): like
      `manifest.jsonl`, `symbols.meta.json` is byte-reproducible — fixed key
      order and a **stable-sorted `languages`** array — so an unchanged tree
      yields a byte-identical sidecar too. **`languages` is the set of distinct
      languages that produced ≥1 symbol record** (round-3 P2 fix), matching the
      `symbols_indexed` accounting (D6); a grammar-missing language with zero
      symbols simply does not appear, so the sidecar never couples to grammar
      availability.
    - **Read-path cost** (claude-p note): integrity detection JSON-parses every
      line of `symbols.jsonl` on each refresh, including the no-reparse
      incremental path — an O(records) scan, not an O(1) gate. This is accepted:
      correctness of the cache outranks a micro-optimization, and the parse is
      cheap relative to a walk.
  - **Pruning** (D8): when a tracked file is deleted (or renamed), a refresh
    **removes its symbol records** from `symbols.jsonl`, mirroring manifest
    pruning — no symbol record ever cites a path no longer on disk.
  - **Deterministic + atomic** (D9): two indexes of an unchanged tree produce a
    **byte-identical** `symbols.jsonl`, written via a same-directory temp file +
    `os.replace` (the Wave-1 R4/R8 pattern, reused). To guarantee a **total
    order** even when symbols collide on `(path, start_line)` — decorators,
    one-line defs, co-located symbols (▶ **chosen for robustness**, resolves
    review concern P1-b) — records are ordered by the full key
    `(path, start_line, end_line, kind, name)`.
- **Symbol-aware locate** (`orchestrator/`): `harpyja_locate` stays **Tier 0**
  (`tiers_run == [0]`, zero model calls). The symbol layer is exposed as a
  `Locator` and composed with the ripgrep `Locator`:
  - **SymbolEngine behind the shared protocol** (D16) (▶ **chosen for
    robustness**, resolves review concern P0-5 / the lone convention violation):
    `SymbolEngine` implements the shared **`Locator` protocol** and returns the
    common `CodeSpan`/`Citation` shapes — the orchestrator **does not branch on
    "is there a symbol engine?"**. It composes the symbol and ripgrep Locators
    into one `CodeSpan` stream and the **Citation Formatter** applies the
    definition boost as a ranking signal over that unified stream. `SymbolEngine`
    stays an internal implementation detail behind the protocol, exactly like
    `RipgrepEngine`.
  - **Query → symbol-name matching, exact-only** (D10a) (▶ **chosen for
    robustness**, resolves review concern P0-3 and round-2 P0a): the query is
    first split on whitespace into **segments**; matching is then defined over
    segments so the two matchers don't fight (round-3 P2 fix — claude-p). For
    **name** matching, each segment is split into identifier tokens on
    non-identifier characters `[^A-Za-z0-9_]` (the separators `.`/`::` are
    consumed here too). A symbol matches when an identifier token **equals** a
    symbol `name` by **exact, case-sensitive** comparison. Case-sensitivity is
    deliberate and load-bearing — Go's exported/unexported distinction *is* the
    leading case (`Parse` ≠ `parse`), and Python convention agrees. Method
    addressing (D10c) runs a **separate pass over the raw segment** that preserves
    the `.`/`::` separator, so `Foo.bar` yields both the plain-name candidates
    `Foo` and `bar` **and** the method-address candidate `(parent=Foo, name=bar)`.
    **Substring/partial matching is explicitly NOT in Wave 2** (round-2 P0a fix —
    flagged by both reviewers; codex marked it a guardrail violation): a fuzzy
    partial match could promote the *wrong* definition above a correct text hit —
    an unverified confident citation — and it created a third match-state the
    no-match invariant (D10b) did not cover. Exact-name + method addressing
    deliver the spec's whole "definition first" justification with zero ambiguity;
    substring matching is **deferred to the Wave-2.1 follow-up** (see Out of
    scope) where it can carry its own ACs.
  - **Method addressing** (D10c): a method is addressable as `Parent.name` or
    `Parent::name`. The matcher recognizes **only an ordered, adjacent
    `<identifier><sep><identifier>` pair within a single (whitespace-delimited)
    query segment**, with the separator limited to `.` or `::` (round-2 P1c fix —
    codex): the left token must equal a symbol's `parent` and the right its `name`.
    Two identifiers separated by **whitespace** (different segments) or any other
    character do **not** form a method address (so `Foo bar` and `bar Foo` never
    match). A chain of 3+ identifiers (`Foo.bar.baz`) is handled by evaluating
    **every adjacent pair** — `(Foo, bar)` and `(bar, baz)` — each as an
    independent `(parent, name)` candidate (round-4 clarification — claude-p);
    since `parent` is immediate-only (D3) there is no fully-qualified-path match.
  - **Definition promotion** (D10): when the query matches a **symbol name** (per
    D10a) or a **method address** (per D10c), that symbol's **definition** citation
    is ranked **above** raw ripgrep line hits (e.g. call sites) for the same token.
  - **No-match degradation** (D10b) (▶ **chosen for robustness**, resolves review
    concern P2): when the query matches **no** symbol name and **no** method
    address, locate degrades to the **exact Wave-1 ripgrep-only path and ranking**
    — the symbol layer is purely additive and never suppresses or reorders a plain
    text result. Because matching is exact-only (D10a), "no match" is now a clean
    binary with no fuzzy middle state. This is the common case and is asserted as
    an invariant.
  - **Ranking** (D11): the symbol-definition boost is layered **on top of** the
    Wave-1 formatter signals (`prior` + match density), with a stable total-order
    tie-break on `(path, start_line, end_line, kind, name)` (D9) **preserved** —
    determinism is unchanged.
    **Placeholder weights** (D12, mirroring Wave 1 P5): the boost magnitude is a
    documented placeholder tuned later, but the placeholder MUST preserve the
    ordering the ACs assert (definition above call site), so a future re-tune
    can't silently break it.
  - **Ensure-index** (D13): the Wave-1 incremental refresh that `locate` runs
    before searching now **also** refreshes `symbols.jsonl`, so a query right
    after an edit reflects the new symbols with no explicit re-index call.
  - **`mode` / `language_hint` unchanged in contract** (D14): `mode` is still
    accept-validate-flag (no routing effect — still Tier 0), but its note is
    updated to be honest about the symbol tier, e.g. `"Wave 2: deterministic +
    symbol-aware Tier 0; mode has no effect"`. `language_hint` is still honored
    against the manifest language; symbol records inherit the file's language for
    hint filtering. `max_results` is still a mandatory clamp.

## Acceptance criteria

1. **`symbols.jsonl` written** (D1/D2): `harpyja_index --repo R` parses Python and
   Go files via tree-sitter and writes `symbols.jsonl` alongside `manifest.jsonl`;
   each line has `path` (repo-relative), `language`, `name`, `kind`, `parent`
   (nullable), `start_line`, `end_line` — the latter **1-indexed and inclusive**,
   matching `harpyja_read`. A symbol record's range, fed to `harpyja_read`,
   returns that definition.
2. **Defs-only kind vocabulary** (D3): a Python fixture yields `function`,
   `method`, `class`, and module-level `constant`; a Go fixture yields `function`,
   `method`, `struct`, `interface`, `type`, and package-level `const`/`var`.
   Import statements, call sites, and **function-local (nested) defs** produce
   **no** records. Boundary cases are pinned by fixtures: `async def` → same kind
   as `def`; a Python `constant` is recognized only for a single `UPPER_SNAKE`
   target (plain or annotated) and **not** for tuple-unpacking/augmented
   assignment; a Go method with a pointer receiver `(s *Foo)` and one with a value
   receiver `(s Foo)` both record `parent == "Foo"`. Methods carry their immediate
   enclosing type in `parent`; top-level defs have `parent == null`.
3. **`symbols_indexed` is total-in-index** (D6): `harpyja_index` returns
   `symbols_indexed` equal to the **total** number of `symbols.jsonl` records
   after the refresh (no longer `0`), **not** the count parsed this run — an
   incremental refresh that re-parses nothing still reports the full total.
   `null`-language and grammarless files contribute `0`; the `languages` map
   remains a file count (unchanged from Wave 1).
4. **Graceful degradation, two distinct causes** (D4/D5): `harpyja_index`
   **succeeds** on any parser problem. (a) **Grammar unavailable** — a file of a
   language whose grammar can't be imported/loaded gets **zero** symbol records
   and is flagged `grammar-missing`; ripgrep over it is unaffected. (b) **Parse
   error** — a file whose tree carries `ERROR`/`MISSING` nodes: a **definition**
   whose subtree is error-spanned is **skipped** (no possibly-wrong range emitted)
   while cleanly-parsed sibling definitions are **still emitted**, and the file is
   flagged `parse-error` whenever its tree has **any** `ERROR`/`MISSING` node —
   **including one outside every definition**. The two flags are
   **distinguishable** (each naming the language/file). Error-spanning is scoped to
   a definition's **own region, excluding nested-definition subtrees** (D4). Tests:
   (i) one file with a broken def + a clean def → clean def indexed, broken absent,
   flagged `parse-error`; (ii) a file whose only error is a broken top-level
   statement (all defs clean) → all defs indexed **and** still flagged
   `parse-error` (partialness never silent); (iii) a grammar-missing file → zero
   symbols, flagged `grammar-missing`; (iv) a **class with a clean method `A` and a
   broken method `B`** → the **class record and method `A` are emitted**, only `B`
   is skipped, and the file is flagged `parse-error` (a nested error never
   suppresses its clean enclosing class — round-3 P1). (Contrast: Wave 1's `rg`
   absence hard-fails locate.)
5. **Incremental re-parse with an injectable parser seam** (D7): a file that
   passes the `(mtime, size)` gate reuses its prior symbol records **without
   re-parsing**; a file whose `hash` changed is re-parsed and its records
   replaced; `harpyja_index --rehash` re-parses every file. The parser/engine is
   an **injected collaborator** (per conventions) so the test passes a spy and
   asserts **zero** parse calls on the unchanged path. ("Zero parse calls" is
   distinct from "zero file reads": the no-reparse path still reads `symbols.jsonl`
   once to recompute the D15 digest — `(mtime, size)` avoids re-parsing, not the
   integrity scan.)
6. **Symbol pruning** (D8): after a tracked file is deleted (or renamed) on disk,
   a refresh **removes its symbol records** — no `symbols.jsonl` line cites a path
   no longer present.
7. **Deterministic + atomic artifacts** (D9/D15): two indexes of an unchanged
   tree produce a **byte-identical** `symbols.jsonl` **and** `symbols.meta.json`
   (the sidecar has fixed key order + a stable-sorted `languages` array), each
   ordered by the total key `(path, start_line, end_line, kind, name)` for records,
   written via same-directory temp file + `os.replace`. A fixture with **two
   real colliding symbols** — module-level constants written `A = 1; B = 2` (two
   `constant` records sharing both `start_line` and `end_line`) — still yields a
   stable, byte-identical order across runs.
8. **Self-verifying integrity recovery forces full rebuild** (D15): the sidecar
   carries `record_count` + a `content_digest` (`"sha256:…"`) over the bytes of
   `symbols.jsonl`. A refresh rebuilds symbols in full (re-parsing, **without**
   `--rehash` and independently of the `(mtime, size)` gate) in **each** of these
   cases, each covered by a test — (a) `symbols.jsonl` truncated mid-line (a
   non-JSON line); (b) **`symbols.jsonl` truncated cleanly at a newline boundary**
   — still valid JSONL, but its line count ≠ `record_count` and/or its `sha256` ≠
   `content_digest`, so it rebuilds rather than trusting a short-but-valid file
   (round-3 P0); (c) `symbols.meta.json` missing or unreadable while
   `symbols.jsonl` is present; (d) the meta's `engine_identity` (tree-sitter
   runtime **+ each grammar version**) does not match the running engine —
   **including a grammar-only version bump** with `schema_version` and
   `(mtime, size)` unchanged, which MUST still rebuild; and (e) a previously-absent
   grammar becomes **installed** — its `engine_identity` slot flips from the
   `"missing"` sentinel to a real version, firing the rebuild that re-parses the
   now-parseable files **and clears their stale `grammar-missing` flags** (D18), so
   an unchanged-on-disk file is no longer reported `grammar-missing` (round-4
   clarification — claude-p). A further test asserts the **records-first, meta-last**
   write order: simulating a crash after `symbols.jsonl` is committed but before
   `symbols.meta.json` leaves fresh records under a stale meta whose
   `content_digest`/`record_count` no longer match — the fingerprint check detects
   the mismatch and **rebuilds** (never read as valid). The result is always
   correct and complete, never a silently stale, short, or partial symbol set.
9. **Exact-only symbol search behind the `Locator` protocol** (D16/D10a): the
   symbol engine implements the shared `Locator` protocol and returns
   `CodeSpan`/`Citation` shapes; a name lookup returns definition records whose
   `name` **exactly, case-sensitively** equals an identifier token — `Parse` does
   **not** match `parse`, **nor** does it match `ParseConfig` or `reParse`
   (substring matching is **not** in Wave 2, D10a); results are bounded by the
   configured search limits. The orchestrator composes Locators and never branches
   on whether a symbol engine is present.
10. **Definition promotion in locate** (D10/D10a/D10c/D11): `harpyja_locate` for a
    query naming a symbol returns that symbol's **definition** citation ranked
    **above** raw ripgrep line hits (call sites) for the same token — still Tier 0,
    `tiers_run == [0]`, **zero model calls**. Method addressing is exercised both
    ways: `Foo.bar` promotes method `bar` with `parent == "Foo"`, while `Foo bar`
    (whitespace-separated, not a `.`/`::` pair) does **not** form a method address
    (D10c). The placeholder boost weights preserve this ordering (D12).
11. **No-match degrades to Wave-1 exactly** (D10b): a query matching **no** exact
    symbol name and **no** method address returns the **identical** citations and
    ordering as the Wave-1 ripgrep-only path — the symbol layer never suppresses or
    reorders a plain text result when nothing matches. (Exact-only matching, D10a,
    makes "no match" a clean binary — there is no fuzzy partial state to leak.)
12. **Determinism preserved** (D11): the symbol boost layers on Wave 1's
    `prior` + match-density ranking with the `(path, start_line, end_line, kind,
    name)` total-order tie-break intact; a query for a symbol defined in multiple
    files orders the definitions deterministically (byte-stable across runs).
13. **Ensure-index refreshes symbols** (D13): a `harpyja_locate` issued right after
    a Python/Go file is added or modified reflects the new/changed symbols with **no
    explicit re-index call**; with no prior `symbols.jsonl` it is built from scratch.
14. **Contract honesty preserved** (D14): `harpyja_locate` with an invalid `mode`
    is still rejected; with a valid `mode` it runs Tier 0 and sets `notes` to a
    string that honestly reflects the symbol-aware tier and that `mode` has no
    routing effect. `language_hint` still filters by manifest language;
    `max_results` is still a mandatory clamp.
15. **Pinned, air-gap-safe grammar packaging** (D17): the build pins the
    individual `tree-sitter-python` and `tree-sitter-go` grammar packages (plus the
    `tree-sitter` runtime) at explicit versions — **not** the aggregate
    `tree-sitter-languages` wheel (▶ **chosen for robustness**, resolves Open
    Question 1). When a pinned grammar package is **absent at runtime** — or
    fails to load against the tree-sitter runtime (an **ABI / version-skew**
    mismatch between the runtime and the individually-pinned grammar, round-2 P2 —
    claude-p) — that language degrades via D4 (grammar-unavailable, flagged in
    `degraded`) rather than raising; tests exercise both the absent-package and the
    load-failure paths.
16. **`degraded` is total-in-index across incremental refreshes** (D18): a file's
    degradation outcome is persisted on its `manifest.jsonl` entry, so an
    incremental refresh that re-parses **nothing** still returns the **full,
    accurate** `degraded` array (not `[]`). A test indexes a tree containing a
    `parse-error` file, runs a second refresh in which that file passes the
    `(mtime, size)` gate (no re-parse), and asserts the `parse-error` file is
    **still** reported in `degraded` — exactly as `symbols_indexed` stays
    total-in-index (D6). Pruning a file drops its persisted flag.
17. **Air-gap preserved**: tree-sitter parsing runs fully locally with bundled
    grammars; no runtime network egress is introduced, and `gateway.assert_local`
    and the Wave-0 inbound-bind defaults are untouched. (A test/audit confirms no
    new outbound calls in the index/locate path.)

## Out of scope

- **The other five languages** — Rust, JS/TS, C#, Java, and C/C++ symbol grammars
  are a **deliberate follow-up spec** opened when this spec closes (user decision).
  Wave 2 ships **Python + Go** only; the SymbolEngine is built so adding a grammar
  is additive.
- **Substring / fuzzy symbol matching** — Wave 2 matches symbol names by **exact,
  case-sensitive** identity only (D10a). Substring/prefix/fuzzy matching is
  **deferred to the Wave-2.1 follow-up** (round-2 review): it needs its own
  ranking rules and ACs, and folding it in now would create a fuzzy match-state
  that risks promoting the wrong definition over a correct text hit (an unverified
  confident citation). Exact + method addressing covers the spec's justification.
- **Imports, references, and call graphs** — `symbols.jsonl` holds **definitions
  only**. No usage/xref index, no "find all callers", no cross-file resolution.
- **Function-local (nested) definitions and closures** — only top-level and
  class/struct-member definitions are extracted; defs nested inside a function
  body are not indexed (keeps the kind vocabulary closed and `parent`
  unambiguous, D3).
- **Value/type inference for `constant`** — Python `constant` is classified by
  syntactic form only; a call-valued upper-case binding (e.g.
  `Color = namedtuple(...)`) is still `constant` rather than a `type` (D3).
- **Signatures / docstrings / type info** — records carry `name`, `kind`,
  `parent`, and range only; richer per-symbol metadata is deferred.
- **Higher tiers and real `mode` routing** — Scout (Wave 3), Deep (Wave 4), and
  the verification gate / classifier / escalation (Wave 5) remain out. Locate is
  still Tier-0-only; `mode` stays accept-validate-flag.
- **Tuning the symbol-boost weights** — the boost *structure* ships now; the
  numbers are placeholders tuned later against real repos (must preserve AC
  ordering, D12).
- **Validated regex search** — still deferred from Wave 1; search remains
  literal-by-default.
- **Symbol-level incremental sub-file diffing** — re-parse granularity is the
  whole file (gated by the manifest hash); no intra-file symbol diff.

## Open questions

_none — all three cross-review rounds are fully resolved in-spec._

**Round 0** (each flagged **▶ chosen for robustness**): parse-error threshold
(D4/AC4), corrupt-artifact recovery (D15/AC8), query→name matching with case
sensitivity (D10a/AC9–10), `Locator`-protocol composition (D16/AC9), the
`(path, start_line, end_line, kind, name)` total-order tie-break (D9),
`symbols_indexed` total-in-index (D6), the `constant`/receiver/nested boundary
rules (D3), and grammar packaging via **pinned individual** `tree-sitter-python`
/ `tree-sitter-go` packages (D17/AC15).

**Round 1** (new issues the round-0 fixes introduced, all closed): substring
matching **deferred to Wave 2.1** so "no match" stays a clean binary and no fuzzy
match can promote a wrong definition (D10a, Out-of-scope; the round-1 guardrail
concern); the rebuild trigger now keys on full **`engine_identity`** — runtime +
each grammar version — so a grammar bump invalidates the cache (D15/AC8); the
two-file write is **records-first, meta-last** with inconsistency → rebuild
(D15/AC8); the `symbols.meta.json` sidecar is **byte-reproducible** (D15/AC7,
closing the round-1 convention concern); D4 cleanly separates **grammar-missing
→ zero symbols** from **parse-error**, and a parse-error flags the file on **any**
`ERROR`/`MISSING` node even outside a definition (D4/AC4); method addressing is an
ordered adjacent `.`/`::` pair only (D10c/AC10); Go **generic** receivers strip
the type-parameter list (D3); and grammar **ABI/load-skew** routes through D4
grammar-unavailable (D17/AC15).

**Round 2** (gaps the round-1 corruption-recovery fix left, all closed): the
sidecar now **self-verifies** — `record_count` + a `sha256` `content_digest` over
`symbols.jsonl` bytes — so a clean newline-aligned truncation **and** a
records-first/meta-last crash residue both fail the fingerprint and rebuild,
making AC8's "always correct and complete" true by construction (D15/AC8); D4
error-spanning is scoped to a definition's **own region excluding nested-definition
subtrees**, so a broken method never suppresses its clean enclosing class
(D4/AC4-iv); per-file `degraded` status is **persisted on the manifest entry** so
an incremental no-reparse refresh still reports the full `degraded` array, total-
in-index like `symbols_indexed` (D18/AC16); the sidecar `languages` set is **the
distinct languages with ≥1 record** (D15); and the query is split into
whitespace **segments** with a separator-preserving pass so D10a's name tokenizer
and D10c's `.`/`::` method-address matcher don't collide (D10a/D10c).

**Round 3** (fourth review — both reviewers **approved-with-comments**, quorum met,
spec advanced to `reviewed`): the D15 corruption-recovery design was independently
stress-tested (bit-flips caught by the digest, interrupted `os.replace` leaves
whole-old-or-whole-new, two-file commit deliberately not jointly-atomic with the
digest detecting the only inconsistent intermediate) and confirmed correct by
construction. Six non-blocking clarifications were folded in editorially: an
`engine_identity` sentinel (`"missing"` / `"load-error:<abi>"`) for an
absent/load-failed grammar so degraded runs write a reproducible sidecar (D15/D17);
the **absent→present grammar recovery** that clears stale `grammar-missing` flags
via the `engine_identity` rebuild, now explicit + tested (D15/AC8e); "nested
definition" pinned to **any** nested definition syntactic form, extracted or not
(D4/AC4); the `Foo.bar.baz` chain handled by evaluating **every adjacent pair**
(D10c/AC10); `os.replace` named literally per convention (D9/D15); and AC5's "zero
parse calls" kept distinct from "zero file reads" (the no-reparse path still scans
records for the digest).
