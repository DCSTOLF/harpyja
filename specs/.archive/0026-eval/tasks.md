---
spec: "0026"
---

# Tasks

- [x] T1 — Dataset schema-version gate: RED (constant + terse guard-field + legacy-loads tests) [unit]
- [x] T2 — Dataset schema-version gate: GREEN (`DATASET_SCHEMA_VERSION`, additive EvalCase guard fields, version-gated `_parse_case`) [unit]
- [x] T3 — `case_id` JOIN over sha256-pinned raw fixture: RED (pin-before-join, no second transcription, base_commit side-data) [unit]
- [x] T4 — `case_id` JOIN: GREEN (`terse_dataset.load_terse_dataset` + minimal committed terse fixture) [unit / fixtures]
- [x] T5 — Token-subset tripwire + loud guard rejection (Layer a): RED [unit]
- [x] T6 — Token-subset tripwire: GREEN (`compute_leaked_tokens` recomputed against joined source issue) [unit]
- [x] T7 — Authoring-provenance sidecar shape + pin (2) blindness: RED [unit]
- [x] T8 — Authoring-provenance sidecar: GREEN (`authoring_provenance.py`, loud validator, `assert_author_input_blind`) [unit]
- [x] T9 — Offline two-model authoring tool: RED (injected seam, withheld gold, leaky→reauthor/drop, non-product import guard) [unit]
- [x] T10 — Offline two-model authoring tool: GREEN (`terse_authoring.py`, dev-time operator module, no product `ModelGateway`) [unit]
- [x] T11 — Classification-by-intent + labeled excluded-count + size/pairing floor: RED [unit]
- [x] T12 — Classification + excluded-count + floor: GREEN (`validate_terse_set_floor` cites committed constants, multi-repo) [unit]
- [x] T13 — Representativeness/language-monoculture caveat + report SCHEMA_VERSION bump: RED [unit]
- [x] T14 — Representativeness caveat + schema bump: GREEN (`report.SCHEMA_VERSION` → `0026/1`, centralized default) [unit]
- [x] T15 — AC8 frozen/hashed pilot config + signal-bearing flip + typed outcome: RED [unit]
- [x] T16 — AC8 pilot config + verdict: GREEN (`ac8_pilot.py`, `PREREGISTERED_AC8_CONFIG`, `decide_ac8`, oracle-based signal flip) [unit]
- [x] T17 — AC6 scoring end-to-end via provisioning path: RED→GREEN (`terse_probe.run_terse_locate_probe` delegating unchanged `run_locate_probe`) [integration, skip-not-fail]
- [x] T18 — AC8 live pilot go/no-go run: RED→GREEN (`terse_probe.run_ac8_pilot`, two reference models, projection, typed `Ac8Outcome` + config hash) [integration, delegated — live run pending operator]
- [x] T19 — Refactor: one-oracle reuse assertion for AC8 signal flip [unit] (sha256-hoist deferred — would couple the light loader to the heavy HF-importing swebench module for 3 lines; recorded deviation)
