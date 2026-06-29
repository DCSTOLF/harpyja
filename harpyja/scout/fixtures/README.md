# Scout fixtures — FastContext `citation=False` (spec 0011)

These ground the citation-shape unit tests in the **observed** FastContext output
shape (AC11), not an assumed one.

## Files

- `fc_citation_false_raw_samples.txt` — verbatim `agent.run(citation=False)`
  return values captured live (FastContext-4B via Ollama, 2026-06-28). Evidence
  for the spec-0011 gating check (Open Question 1). See its header for provenance
  and the key facts established.
- `fc_citation_false_final_answer.txt` — the curated fixture the unit tests load.
  Built from the observed grammar in the raw samples (newline-delimited
  `path[:start[-end]] (explanation)` entries inside `<final_answer>`), with one
  line per parser edge case.

## Gating-check outcome (Open Question 1) — seam (a) LOCKED

Confirmed live: `citation=True` raises `TypeError: string indices must be
integers` (FC's `format_citations` on the dict-fallback from a missing
`<final_answer>`); `citation=False` returns the model's raw final message and
**cannot reach that formatter**, so it never hits the crash. The model does emit
`<final_answer>` blocks (samples A/B/D) and also bare absolute paths with no line
(sample C) — so the file-level case is real. Seam (a) holds; seam (c) fallback
not needed.

## Delimiting structure (for the AC22-safe parser)

A citation line is `<no-space-path-token>[:start[-end]] [(explanation)]`,
end-to-end. The path token never contains a space; the explanation is
parenthesized. Parse **per line, anchored** — never a naked optional `:\d+` over
free text — so an incidental prose filename is dropped, not promoted.

## `fc_citation_false_final_answer.txt` line → AC map

| Line | Shape | AC |
|------|-------|----|
| `auth.py:1-2 (...)` | spanned (range) | AC2, AC3 |
| `validate.py:20 (...)` | spanned (single line) | AC2 |
| `db.py (...)` | bare path → file-level (`None` lines) | AC1, AC3, AC4 |
| `parser.py:abc (...)` | non-numeric line → file-level | AC5 |
| `the relevant change ... app.py:42` | prose w/ embedded filenames → **dropped** | AC22 |
