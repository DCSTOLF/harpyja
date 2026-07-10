# Spec 0036 — close notes

## AC6 — representativeness scope (T18)

The representativeness scope of this eval set is stated by the ALREADY-PINNED
`REPRESENTATIVENESS_CAVEAT` constant (`harpyja/eval/report.py:41`), which is
stamped into every report payload (`report.py:175`). Per the round-2 review, no
parallel restatement is made here — the pinned constant is the single statement
of scope: the set fixes the QUERY-SHAPE axis (terse) on documented-OSS repos; it
does NOT fix the codebase-character axis (undocumented legacy); results are
valid for relative model ranking, not a real-world-legacy performance claim.

## AC4 — pilot gate evidence (T15/T17)

- Gate verdict: **PROCEED** — `specs/0036-terse-query/pilot/gate_report.json`
  (config_hash `114574c4ffa16e90fc3e1de54080491e7bfd396bb56952b37c419b16fc0c682a`
  = `AC8_CONFIG_HASH_0036`, committed at `98ee3d0` BEFORE the pilot ran).
- 10 pairs run, 0 excluded, 5 signal-bearing discordant flips → projected
  15 ≥ 8 (`MIN_DISCORDANT_PAIRS`).
- Per-(case, arm) ledger: `specs/0036-terse-query/pilot/pilot_results.json`;
  all 20 verifier artifacts durable under `eval_work/live_artifacts/pilot_0036/`
  (schema `0034/1`, all `PASSED` — the AC5 integration test pins this).
