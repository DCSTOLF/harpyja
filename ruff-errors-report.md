# Ruff error report — 34 findings

Generated 2026-07-09 against `main` (post spec 0033, `2cc5900`+). Baseline context: 36 at
spec 0032 close; spec 0033 net-fixed 2 (the F841 unused-`e` was the actual cause-swallowing
bug). `[*]` = auto-fixable via `ruff check --fix`. All findings are in 0030/0031-era files
except where noted; none are load-bearing defects except the two **B023**s, which are a
real (test-only) bug class.

## harpyja/eval/live_verifier.py — 3

1. `5:1 UP035 [*]` — `Mapping` imported from `typing`; modern form is `collections.abc.Mapping`.
   Style-only, zero runtime impact; one-line fix.
2. `442:5 I001 [*]` — the big function-local import block inside `run_verified_case` is
   unsorted (0031-era stub-completion code). Sort-only fix; hoisting to module level would be
   a behavior-adjacent change (lazy imports avoid a heavy import chain) — keep local, just sort.
3. `451:12 F401 [*]` — `import json` inside `run_verified_case` is never used (leftover from
   the 0031 stub). Safe delete.

## harpyja/eval/test_harness_live.py — 1

4. `51:101 E501` — the `_MODEL_OVERRIDE_REASON` prose string runs 103 chars. Cosmetic;
   rewrap the string literal.

## harpyja/eval/test_live_verifier.py — 7

5. `3:1 I001 [*]` — top import block unsorted (`pytest` before stdlib, 0031-era). Sort-only.
6. `5:8 F401 [*]` — `os` imported, never used (0031-era). Safe delete.
7. `14:5 F401 [*]` — `VerifierResult` imported at top, never referenced in this file
   (tests exercise it via `verify_trajectory` returns). Safe delete.
8. `396:44 F401 [*]` — function-local `build_trajectory_record` import in the 0031 AC6 test
   is shadowed by the later module-level 0032 import; the local one is now redundant. Safe delete.
9. `405:101 E501` — a long fixture line (model_turns literal) at 119 chars. Rewrap.
10. `427:101 E501` — assertion message line at 102 chars. Rewrap.
11. `428:101 E501` — sibling assertion line at 103 chars. Rewrap.

## harpyja/eval/test_live_verifier_integration.py — 4

12. `3:1 I001 [*]` — top import block unsorted (0031-era: `json/pytest/tempfile` ordering).
    Sort-only.
13. `11:5 F401 [*]` — `verifier_preflight` imported, unused since the preflight moved inline
    into the test body (0031-era). Safe delete.
14. `60:101 E501` — the astropy gold-span tuple line, 118 chars (0031-era test_cases literal).
    Rewrap.
15. `61:101 E501` — the django gold-span tuple line, 112 chars. Rewrap.

## harpyja/eval/test_symbols_lift_live.py — 13 (all 0030-era; densest debt cluster)

16. `13:8 F401 [*]` — `json` imported, unused. Safe delete.
17. `43:101 E501` — long docstring/comment line (101). Rewrap.
18. `51:5 I001 [*]` — function-local import block unsorted. Sort-only.
19. `81:101 E501` — long line (106). Rewrap.
20. `139:24 B023` — **real bug class**: the `logged_answer` closure references loop variable
    `original_answer` without binding it — every iteration's closure sees the LAST loop value.
    Currently masked (single-iteration factory), but rots on any second case. Fix: bind as a
    default arg (`original_answer=original_answer`).
21. `139:70 B023` — same defect for loop variable `settings` in the same closure line. Same fix.
22. `173:101 E501` — long line (102). Rewrap.
23. `230:101 E501` — long print line (115). Rewrap.
24. `231:101 E501` — sibling print line (116). Rewrap.
25. `239:11 F541 [*]` — f-string with no placeholders (plain string in disguise). Drop the `f`.
26. `254:15 F541 [*]` — same. Drop the `f`.
27. `255:101 E501` — long line (107). Rewrap.
28. `257:15 F541 [*]` — same f-string-without-placeholder. Drop the `f`.

## harpyja/eval/test_symbols_lift_report.py — 3

29. `11:8 F401 [*]` — `tempfile` imported, unused (0030-era). Safe delete.
30. `12:21 F401 [*]` — `pathlib.Path` imported, unused. Safe delete.
31. `14:8 F401 [*]` — `pytest` imported, unused (no skips/raises in this file). Safe delete.

## harpyja/scout/explorer_backend.py — 1

32. `117:101 E501` — a long tool-schema description string (103 chars, 0030-era `symbols`
    schema text). Rewrap the string.

## harpyja/scout/test_explorer_backend.py — 2

33. `507:101 E501` — long scripted model-response line in the 0031 trajectory-capture test
    (101). Rewrap.
34. `509:101 E501` — sibling line (106). Rewrap.

## Summary by class

| Code | Count | Nature | Auto-fix |
|---|---|---|---|
| E501 line-too-long | 14 | cosmetic rewraps | no |
| F401 unused import | 10 | dead imports, safe deletes | yes |
| I001 unsorted imports | 5 | sort-only | yes |
| F541 pointless f-string | 3 | drop the `f` | yes |
| B023 loop-var closure | 2 | **real bug class** (test-only, currently masked) | no |
| UP035 typing import | 1 | modernization | yes |

Recommended order if cleaning: the two B023s first (genuine defect, manual fix), then
`ruff check --fix` for the 19 auto-fixables, then the 14 E501 rewraps. All of it is
0030/0031-era debt in eval/scout test files plus `live_verifier.py`'s stub-era imports —
nothing touches production control flow.
