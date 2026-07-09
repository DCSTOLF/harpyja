# Close notes — agreed items for 0034's closure (recorded 2026-07-09; NOT closed yet)

User-agreed at implementation review (explicitly not a blanket closure approval):

## 1. Named follow-up for the 0034 changelog/close: persistent live-test artifacts

Three times a live-test artifact went to a `TemporaryDirectory` and a follow-up question
("which bucket was that run?") forced a fresh stochastic re-run: 0033-T14 (bucket
unanswerable), the 0034 AC5 run (bucket unanswerable), plus the original 0032 AC6
astropy artifact loss. The per-field print fixes are reactive patches; the structural
fix is live integration tests writing artifacts to a persistent gitignored location
(`eval_work/live_artifacts/<test>/<timestamp>/` — same outside-repo atomic writer)
instead of `TemporaryDirectory`. Small change, own line item at close; candidate to
fold into the eval-set spec's harness work if closer to that seam.

## 2. Named input to the EVAL-SET spec: the silent-`[]` grep affordance gap

Two live observations, now attributable thanks to 0033+0034 instrumentation:
- A FILE-scope grep returns bare `[]` by wrapper rule (0033 astropy run: the model
  grepped `scope="astropy/modeling/separable.py"` twice, read "no matches").
- A NONEXISTENT-scope grep also returns bare `[]` (0034-era run: turn-1
  `grep(scope="repo")` — a hallucinated directory — silently empty; the 6554-char
  reasoning turn produced the bogus scope, the model pivoted to the wrong subsystem
  and finished honest-empty).
Both shapes are indistinguishable from "searched and found nothing." A one-line
in-conversation marker ("scope not found" / "scope is a file — use read_span") is the
candidate fix — an explorer-tool affordance change, OUT of 0034's scope, sized for the
eval-set spec (or a small sibling) where its effect on bucket distributions can be
measured, not assumed.

## Context for the close: astropy running tally (all instrumented runs to date)

`empty` ×4 (two honest, one found-then-dropped pre-0033, one honest with the bogus-scope
detour), `wrong-file` ×2, `right-file-wrong-span` ×1 (the first-ever right-file +
first symbols use, thinking-experiment run 2). Symbols invoked in 2 runs total. Every
failure mode is now visible and attributable in the artifacts — the instrument stack
(0031 verifier → 0032 parser dedup → 0033 path fix + counts → 0034 reasoning
observability) is complete for the eval set to consume.
