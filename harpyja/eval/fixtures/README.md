# Eval fixtures (spec 0009-6a)

`seed.jsonl` is the versioned eval dataset; `legacy/` is the small vendored
legacy-style repo it labels. This seed is a **starter set** — its `seed_n` is well
below the provisional `EvalConfig.n_floor` (30), so any run over it is reported
`indicative_only: true`. It exists to exercise the harness end-to-end and to seed
OQ2 calibration; a real calibration needs a larger curated set (see D1 — a vendored
OSS legacy repo with hand-labeled spans).

## Dataset format

One JSON object per line:

```json
{
  "case_id": "unique-id",
  "query": "natural-language locate query",
  "repo": "legacy",
  "expected_spans": [{"path": "net/retry.py", "start_line": 4, "end_line": 5}],
  "classification": "point" | "broad"
}
```

- `expected_spans` paths are **repo-relative** (relative to the labeled repo root).
- Line ranges are 1-indexed and inclusive.
- `classification` is `point` (a specific symbol/location — gate-eligible) or
  `broad` (a cross-cutting question — routes straight to Deep, excluded from the
  gate catch / false-escalation denominators per D1).

## Adding a case

1. If the location lives in a new repo, vendor it under `fixtures/<name>/` at a
   pinned revision.
2. Hand-label the expected span(s): open the file, find the lines that *answer* the
   query, and record `{path, start_line, end_line}`.
3. Append one JSON line to `seed.jsonl`. Run `load_dataset` — it rejects a
   malformed row loudly, so a bad case fails fast rather than silently dropping.
4. For meaningful gate metrics, keep the point subset balanced: include cases the
   retriever should get right (correct-Tier-1) **and** genuinely hard/ambiguous
   ones (wrong-Tier-1), so both gate denominators stay non-zero (D2).
