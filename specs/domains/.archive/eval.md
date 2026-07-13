# Domain requirement archive

Verbatim superseded requirement text demoted from a domain file by spec consolidation. Append-only.

## eval | spec 0041 | MODIFY
- Run-integrity precondition for ANY live measurement driver: EXCLUSIVE use of the model endpoint for the run's duration — check `/api/ps` for foreign pinned residents (the dev Ollama pins models with infinite keep-alive; 14.3 GB of co-pinned residents silently converted environment latency into fake capability observations: wall-clock expiries recorded as honest `empty` buckets, HTTP timeouts typed `model-unreachable`) and never run the test suite or any live-calling workload concurrently (its requests QUEUE on the shared endpoint and its integration tests touch/pin other model tags); a contaminated run is invalidated OUTCOME-BLIND at RUN granularity (criterion: "recorded during the contaminated environment", including located cells — never "cells whose outcome looks wrong") and re-run fresh, with the invalidated ledger archived as evidence. Pin coverage HEADROOM above a derived pre-check minimum (a pilot set at exactly the minimum lets any single environment degrade force `INSUFFICIENT_PILOT_EVIDENCE`). (spec 0040)

## eval | spec 0044 | MODIFY
- `VERIFIER_SCHEMA_VERSION` is "0043/1" (additive over 0038/1): `submission_outcome` + `detector_version` thread BOTH assembly seams — `build_trajectory_record` (parameter; present-and-None when no gold available, never fabricated) AND `run_verified_case`'s hand-assembled written artifact (computed from trajectory + gold via the one detector) — written-JSON test-pinned (the 0033/0034/0038 dual-seam class); `submission_outcome` is presence-REQUIRED on a 0043/1 artifact (value may be None) while every legacy version validates unchanged. (spec 0043)

