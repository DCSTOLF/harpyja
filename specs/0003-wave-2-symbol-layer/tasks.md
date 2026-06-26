---
id: "0003"
title: "Wave 2 — Symbol layer (tree-sitter, Python + Go)"
plan: specs/0003-wave-2-symbol-layer/plan.md
created: 2026-06-26
---

# Tasks 0003 — Wave 2 — Symbol layer (tree-sitter, Python + Go)

Execution order. Every RED precedes its GREEN. See `plan.md` for detail.

- [x] 1.  GREEN: Pin tree-sitter + tree-sitter-python + tree-sitter-go in pyproject  (codex)
- [x] 2.  RED:   engine_identity shape, runtime+grammar versions, missing/load-error sentinels
- [x] 3.  GREEN: engine_identity() with schema_version + stable sentinels
- [x] 4.  RED:   Python kind vocabulary + parent + import/call/nested exclusions
- [x] 5.  GREEN: Python extractor + SymbolRecord (1-indexed inclusive)
- [x] 6.  RED:   Go kind vocabulary + pointer/value/generic receiver normalization
- [x] 7.  GREEN: Go extractor + receiver normalization
- [x] 8.  RED:   parse-error own-region scoping (cases i–iv) + grammar-missing/load-error
- [x] 9.  GREEN: error-scoped skip + ExtractResult(records, degraded)
- [x] 10. RED:   symbols.jsonl fixed key order + total-key order + byte-identical (A=1;B=2) + meta sidecar
- [x] 11. GREEN: write_symbols/write_meta/read_symbols (records-first, meta-last, os.replace)
- [x] 12. RED:   integrity rebuild triggers (truncation, count/digest, meta-missing, engine-identity, crash residue)
- [x] 13. GREEN: load_symbols_or_none / self-verifying integrity gate
- [x] 14. RED:   manifest degraded field default + key order + legacy read + byte-identical
- [x] 15. GREEN: add degraded to ManifestEntry + _KEY_ORDER (additive, back-compat)
- [x] 16. RED:   index writes symbols + symbols_indexed total-in-index + languages unchanged
- [x] 17. GREEN: wire extraction into index_repo, populate symbols_indexed
- [x] 18. RED:   incremental no-reparse (zero parse calls) + changed reparse + rehash + prune + digest read
- [x] 19. GREEN: gate symbol re-parse by change-of-record + prune + rehash-all
- [x] 20. RED:   degraded total-in-index + persistence/reuse + integrity & engine-identity rebuild + absent→present
- [x] 21. GREEN: persist per-file degraded + integrity-driven full rebuild + clear stale grammar-missing
- [x] 22. RED:   SymbolEngine exact case-sensitive name + method-address (.//::) + chain + bounds
- [x] 23. GREEN: SymbolEngine behind Locator search(pattern, scope), spans carry symbol/parent/kind
- [x] 24. RED:   formatter definition boost above call site + widened tiebreak + no-match parity
- [x] 25. GREEN: definition boost on prior+density, tiebreak (path,start,end,kind,name)
- [x] 26. RED:   locate composes Locators, promotes def, degrades to Wave-1, Wave-2 note, hint filter
- [x] 27. GREEN: compose SymbolEngine+Ripgrep, Wave-2 mode note, Tier-0 unchanged
- [x] 28. RED:   ensure-index reflects new symbols without reindex + builds from scratch
- [x] 29. GREEN: ensure-index also refreshes symbols.jsonl into SymbolEngine
- [x] 30. RED:   app surfaces real symbols_indexed/degraded + wires symbol engine + Wave-2 note
- [x] 31. GREEN: thread SymbolEngine via engine_factory + surface counts
- [x] 32. RED:   CLI index summary shows real symbols_indexed + degraded
- [x] 33. GREEN: CLI summary prints real symbols_indexed/degraded
- [x] 34. RED:   air-gap audit — no outbound call in index/locate; assert_local/bind untouched
- [x] 35. GREEN: confirm local-only tree-sitter parsing, no egress
- [x] 36. REFACTOR: ruff fix/format + full pytest incl -m integration + regression gate  (codex)
