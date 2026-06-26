---
spec: "0003"
closed: 2026-06-26
---

# Changelog — 0003 Wave 2 — Symbol layer (tree-sitter, Python + Go)

## What shipped vs spec

All 17 acceptance criteria and all 36 tasks landed. The symbol layer is live as a
Tier-0, model-free, fully-local enhancement behind the existing `harpyja_index` /
`harpyja_locate` contracts and the same manifest.

- **SymbolEngine + extractor** (`symbols/`): tree-sitter parsers for Python and Go
  extract **definitions only**, classified by syntactic form (no type inference).
  Python emits `function` / `method` / `class` / module-level `constant`
  (single `UPPER_SNAKE` target only); Go emits `function` / `method` / `struct` /
  `interface` / `type` / package-level `const` / `var`. Receiver normalization
  strips both the pointer and the generic type-parameter list, so a method is
  addressable by its bare type name regardless of receiver form (AC1, AC2).
- **Self-verifying symbol cache** (`symbols.meta.json` sidecar): the records file
  stays pure JSONL; the sidecar carries `engine_identity` (tree-sitter runtime +
  each grammar version) + `record_count` + a sha256 `content_digest` over
  `symbols.jsonl`. A rebuild is forced — independently of the `(mtime, size)` gate
  — on any missing/unreadable/truncated record file, missing/unreadable meta,
  engine-identity mismatch, or fingerprint (count/digest) mismatch. Commit order is
  records-first / meta-last via same-dir temp + `os.replace`, so a crash residue
  (fresh records under stale meta) fails the digest and rebuilds (AC7, AC8, AC15).
- **Parse-error own-region scoping** (AC4): a definition is skipped only when an
  `ERROR`/`MISSING` node falls in its own span *excluding nested-definition
  subtrees*, so a broken method never suppresses its clean enclosing class or
  sibling. The file is flagged `parse-error` on *any* error node, even one outside
  every definition. Grammar absent / load-fail → zero symbols + `grammar-missing`.
- **`symbols_indexed` and `degraded` are both total-in-index** (AC3, AC16): the real
  record count and the per-file degradation outcome are reported after every
  refresh. `degraded` is persisted per-file on the `manifest.jsonl` entry (D18) so a
  no-reparse incremental refresh re-surfaces the full, accurate array — same
  staleness family already closed for `symbols_indexed`.
- **SymbolEngine behind the shared `Locator` protocol** (AC9, AC10): `search(pattern,
  scope)` mirrors `RipgrepEngine`; the orchestrator composes both into one
  `CodeSpan` stream and never branches on engine type. Exact-only, case-sensitive
  name matching; method addressing is an ordered adjacent `.`/`::` pair, every
  adjacent pair in a chain evaluated independently.
- **Definition boost in the formatter** (AC10–12): a span carrying a `symbol` ranks
  above raw text hits of equal `prior`, between prior and density, so a definition
  outranks a denser call-site cluster. Definitions are never merged into an
  enclosing class span. Tie-break is the widened total order
  `(path, start_line, end_line, kind, name)`. No-symbol-match degrades
  byte-identically to the Wave-1 ripgrep-only path.
- **Ensure-index, contract honesty, air-gap** (AC13, AC14, AC17): `locate` refreshes
  `symbols.jsonl` alongside the manifest before searching; the Wave-2 `mode` note is
  `"Wave 2: deterministic + symbol-aware Tier 0; mode has no effect"`;
  `CodeSpan.kind` is added (additive optional). Parsing is in-process — no new
  outbound egress; `gateway.assert_local` and the inbound-bind defaults are
  untouched, confirmed by an air-gap audit test.

Test suite **141 → 231** (all green); ruff clean. `tree-sitter`,
`tree-sitter-python`, and `tree-sitter-go` pinned individually in `pyproject.toml`
(not the aggregate `tree-sitter-languages` wheel).

## Deviations from spec

- **Method name vs method address (test-assumption correction):** a method's bare
  `name` already matches by the exact-name path, so method addressing (`Foo.bar`)
  yields an *additional* `(parent, name)` candidate, not the only path to a method.
  An in-flight test that assumed the bare name should NOT match a method was
  corrected — `Foo.bar` promotes the method via both the plain-name token `bar` and
  the method-address pair `(Foo, bar)`.
- **Group J (app / CLI) tests are confirmation tests:** the app and CLI surfaces
  carry no symbol logic of their own — they thread the real `symbols_indexed` /
  `degraded` produced by the lower layers. Their tests confirm the values surface
  end-to-end rather than re-deriving them.
- No behavioral deviations from the ACs; the spec's four cross-review rounds were
  resolved in-spec before implementation.

## Files touched

New (`harpyja/symbols/`):
- `engine_identity.py`
- `extract.py`
- `symbols_io.py`
- `symbol_locator.py`
- `test_engine_identity.py`, `test_extract.py`, `test_symbols_io.py`,
  `test_symbol_locator.py`, `test_air_gap.py`

Changed:
- `harpyja/index/indexer.py` (symbol integration: extraction wiring, incremental
  re-parse gate, full rebuild on integrity/engine-identity mismatch, prune)
- `harpyja/index/manifest.py` (additive per-file `degraded` field, D18)
- `harpyja/orchestrator/format.py` (definition boost + widened tie-break)
- `harpyja/orchestrator/locate.py` (Locator composition + Wave-2 mode note)
- `harpyja/server/types.py` (`CodeSpan.kind`)
- pyproject.toml / uv.lock (pinned grammars)
- test updates: `index/test_indexer.py`, `index/test_manifest.py`,
  `orchestrator/test_formatter.py`, `orchestrator/test_locate.py`,
  `server/test_app.py`, `server/test_locate_tool.py`, `test_cli.py`

## ADR proposed for history.md

2026-06-26 — Wave 2 symbol layer shipped (tree-sitter, Python + Go)
- Decision: symbol extraction → `symbols.jsonl` + self-verifying `symbols.meta.json`
  sidecar → SymbolEngine behind the `Locator` protocol → definition boost in the
  formatter; both follow-ups (5 remaining grammars; Wave-2.1 substring matching)
  deferred to their own specs.
- Why: surface a symbol's definition above its call sites without a model, and make
  the derived cache trustworthy on read.
- Consequence: Tier 0 is now deterministic + symbol-aware; the durable lesson is the
  self-verifying fingerprint (an untrusted derived artifact must authenticate its own
  generation, not just its producer).

## Conventions proposed

- New: a derived artifact that is untrusted on read must self-authenticate via a
  content fingerprint (sha256 over its exact bytes + record count) **and** a producer
  identity (engine/grammar versions), with a records-first / meta-last multi-file
  commit so a crash residue fails the fingerprint and rebuilds.
  Rationale: D15's corruption-recovery design changed three times across review; the
  fingerprint is what makes "always correct and complete" true by construction
  rather than by trusting the producer.
- New: additive dataclass fields are appended last with a default for back-compat,
  so a legacy artifact still reads and an unchanged tree stays byte-reproducible.
  Rationale: the manifest `degraded` field (D18) and `CodeSpan.kind` both shipped
  this way.
