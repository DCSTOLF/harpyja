---
id: "0008"
title: "Wave 5 — Verification Gate + Auto-Escalation"
status: closed
created: 2026-06-27
authors: [claude]
packages: [harpyja/orchestrator, harpyja/config]
related-specs: ["0005", "0006", "0007"]
---

# Spec 0008 — Wave 5 — Verification Gate + Auto-Escalation

## Why

All three tiers (0 / 1 / 2) are live and verified end-to-end, but `mode=auto`
still can't climb between them. Wave 3 deferred the Verification Gate; Wave 3/4
deferred the escalation ladder. This wave makes `auto` trustworthy: run the
cheapest tier that works, and escalate only when needed.

Ref: history.md 2026-06-27 (Wave 3/4 patterns); ARCHITECTURE.md §2.2 / §2.7 / §3
(router, gate, planning matrix); SPEC.md §3.1.

### Invariant (deliberate break)

Wave 0's "`auto` byte-identical, zero model calls" regression lock is
**intentionally retired this wave**. It was a scaffolding lock that held only
while `auto` had nowhere to climb. The replacement `auto` contract is pinned
**explicitly** (AC1), not left implicit — the old lock and the new contract swap
in lockstep so there is never a window where `auto`'s behavior is unspecified.

### Cross-spec posture (not novel risk)

The gate is **one new outbound model call** governed by the three disciplines
every prior tier-spec already landed, applied unchanged:

- **Air-gap before egress** — `gateway.assert_local` on the resolved endpoint
  before the judge call (Scout 0007 / Deep 0006 pattern). See AC10.
- **Stable machine-readable markers** — the gate's flags are enumerated
  identifiers, never prose (cf. `scout-degraded:{…}` / `deep-truncated:<bound>`).
  See B3 / AC9.
- **Typed-failure ≠ honest-result** — a typed-unavailable tier degrades; an
  honest-empty result does not escalate; only a *malformed* result does. See the
  empty-case split / AC8.

## What

Wire the Orchestrator's classifier, planning matrix, Verification Gate, and
escalation ladder so `mode=auto` runs the cheapest tier that can answer and
climbs only on a real signal. Tier internals (Scout / Deep / Tier-0) are
**unchanged** — this wave is orchestration only.

### Resolved decision — gate scoring backend (OQ1)

**`verify_method` defaults to `scout_model` reuse.** The gate reuses the
already-loaded Scout fine-tune (`scout_model`) as a relevance judge: no new model
to serve on the single-GPU profile, sharper intent-match than raw embedding
similarity, and the air-gap path is exactly the one 0007 already proved. The cost
is one hot-path model call per gated query; **OQ3's bounded top-N scan is what
keeps that affordable** (a generative judge over an unbounded citation set would
put a result-set-sized model cost on the hot path — see the gate scope below).
The seam stays pluggable (`verify_method`) so `embedding` / `model_judge` can be
added later without reworking the ACs (they assert thresholding behavior, not a
specific scorer).

### Query classifier — point vs broad

A heuristic classifier labels each query `point` or `broad` per SPEC §3.1
heuristics. **Ambiguous → `point`** (bias to the cheap path; the gate and ladder
catch under-classification by escalating on a gate-fail). The classifier is
**pluggable** — a clean seam for a model classifier later — but this wave **ships
the heuristic only** (the model classifier is out of scope; only the seam is
built).

### index_ready — the matrix's third dimension

`index_ready` = the repo's manifest + symbol index have been built (via `index`).
The **Tier-0 seed** — the ranked Tier-0 lookup that Scout/Deep self-seed from —
requires that index. When `index_ready` is **false** the seed step is **skipped**
and the model tier runs **query-only**; the planned sequence drops its leading
`0`. A not-ready index is a **routing variant, not a floor failure**: `index` is
not a hard precondition for `locate` (only `rg` is — mirroring the Wave-1
posture), so a query-only run is honest, and pure-ripgrep retrieval still backs
the degradation floor (it is just not used as a *seed*).

### Planning matrix — all 12 rows enumerated

The matrix is the **single source of truth** for routing: it maps
`(mode × classification × index_ready)` → the **planned tier ladder**. The
ladder executes that sequence; for `auto`, the gate decides whether the final
Tier-2 step actually runs (so the *realized* `tiers_run` is a prefix of the
planned ladder). The escalation-trigger bullets below are **derived from this
table**, not a second authority — the table wins on any apparent conflict.

| mode | class | index_ready | planned ladder | realized `tiers_run` / notes |
|------|-------|-------------|----------------|------------------------------|
| auto | point | true  | `[0,1,2]` | gate between 1→2: pass ⇒ `[0,1]`; fail / Scout-malformed / **gate-scoring-failed** ⇒ `[0,1,2]`; Scout typed-unavailable ⇒ `[0]` degrade; Scout honest-empty ⇒ `[0,1]` + `gate-skipped:scout-empty` (gate skipped — nothing to score — returns seed, no climb) |
| auto | point | false | `[1,2]`   | seed skipped; same gate rule, pass ⇒ `[1]`, fail / malformed / gate-scoring-failed ⇒ `[1,2]` |
| auto | broad | true  | `[0,2]`   | broad routes **straight to Deep**; Scout skipped; **no gate** in path; deterministic |
| auto | broad | false | `[2]`     | seed skipped; straight to Deep |
| fast | point | true  | `[0,1]`   | ceiling = Tier-1; gate is **informational only**, never climbs; gate-would-fail ⇒ `gate-low-confidence` flag |
| fast | point | false | `[1]`     | seed skipped; Scout query-only; never climbs |
| fast | broad | true  | `[0,1]`   | **fast wins over broad** (caller chose the ceiling): Scout only, never Deep; gate-would-fail (likely) ⇒ `gate-low-confidence` |
| fast | broad | false | `[1]`     | seed skipped; Scout only; never climbs |
| deep | point | true  | `[0,2]`   | seed → Deep, Scout skipped (Wave-4 unchanged); classification ignored |
| deep | point | false | `[2]`     | seed skipped; straight to Deep |
| deep | broad | true  | `[0,2]`   | identical to `deep`+`point` (deep ignores classification) |
| deep | broad | false | `[2]`     | seed skipped |

Every row is asserted (AC3); the realized-prefix outcomes are asserted by
AC1 / AC9.

### VerificationGate

The gate reads the **cited lines back** from disk and scores their relevance to
the query via `scout_model`. `passed = score ≥ verify_threshold`.

- **Scope — bounded top-N (OQ3, resolved).** The gate scores the **top-N ranked
  Tier-1 citations** (`verify_top_n`), not the whole set — required to keep the
  generative judge affordable on the hot path. When the citation set exceeds N,
  the **dropped count is logged** (no-silent-truncation: a bounded scan must
  never read as "verified everything"). N is provisional (OQ2-adjacent), tuned
  against the eval repo.
- **Air-gap (B1) — route through `ModelGateway`, not a parallel client.** The
  gate is **in-house orchestrator code**, not a third-party tier, so its judge
  call goes through **`ModelGateway.complete()`**, which already asserts the
  air-gap at resolution time (Wave 3) — the gate does **not** construct a parallel
  judge client (that would violate "the Gateway is the only outbound caller").
  The gate **additionally** calls `gateway.assert_local` on the resolved
  `scout_model` endpoint **before** the call as an explicit belt-and-suspenders
  check (still the *one* helper, no parallel air-gap type). A non-loopback
  endpoint is a loud `AirGapError` floor, never a degrade. Proven by a
  network-deny integration test (AC10).
- **Failure → best-effort, never block (pinned contract).** A judge-call error
  never hard-blocks and never silently passes; the result carries
  `gate-scoring-failed`. Because the gate cannot vouch for the citation, the
  realized path mirrors a gate-fail **exactly**:
  - **`auto`, a further tier available** → **escalate** to Tier-2 (`[0,1,2]`),
    `source_tier=2`, `gate-scoring-failed` retained as diagnostic metadata,
    `confidence=low`.
  - **no further tier** → return the **best-effort un-gated Tier-1 result** +
    `gate-scoring-failed`, `confidence=low`. In practice this is the **`fast`**
    path: in `auto` the gate fires only at the `1→2` step where Tier-2 always
    remains, so `auto` always takes the escalate branch above.
  This is the same home the matrix gives gate-fail — `gate-scoring-failed` is a
  diagnostic flag *on top of* that path, not a separate route.

**Three additive `Settings` fields**, appended **last** with defaults, standard
precedence (defaults < `harpyja.toml` < `HARPYJA_*` < per-request):

- `verify_method` — scoring backend selector. **Default `"scout_model"`** (OQ1).
  **Only `"scout_model"` ships this wave.** Per the no-false-capability rule, an
  unsupported value (`"embedding"` / `"model_judge"` / anything else) is
  **rejected loudly** at `Settings` load with a typed, actionable error naming
  the field and the accepted set — **never** a silent fall-through to
  `scout_model` and never an inert no-op. The seam is pluggable in *code*, but
  the config surface only accepts what actually functions (AC13).
- `verify_threshold` — pass cutoff on a normalized `[0,1]` score. **Provisional
  default `0.6`** (OQ2 — tuned against the eval repo).
- `verify_top_n` — max citations scored per gate. **Provisional default `3`**
  (OQ3 bound).

### Flag taxonomy (B3) — stable identifiers, not prose

New caller-visible markers join the existing taxonomy as **stable
machine-readable identifiers** (callers/tests branch on the id, never the
wording):

- `gate-low-confidence` — `fast` mode ran the gate **informationally** (Scout
  returned scoreable citations) and it **would have failed**; the Tier-1 result
  is returned anyway (honest ceiling, not an escalation). Emitted **only** when
  the gate actually scored — **not** when Scout was typed-unavailable
  (`scout-degraded:<cause>` covers that), honest-empty (gate skipped — nothing to
  score), or malformed (degrades in `fast`).
- `gate-scoring-failed` — the judge call errored; behavior per the pinned
  failure contract above (escalates in `auto` if a tier remains, else best-effort
  Tier-1). A diagnostic flag layered on the gate-fail path, not a separate route.
- `gate-skipped:scout-empty` — Scout ran cleanly but returned **zero** citations,
  so the gate had nothing to score; the result is the **Tier-0 seed**. This is
  the honest-empty case (not a degrade, not `gate-low-confidence`) — its sole job
  is to **disambiguate** an honest-empty `[0,1]`/`[1]` from a gate-verified
  gated-pass, which share the same path tokens. Carries the existing
  `+no-matches` suffix when the seed is itself empty.

### Escalation ladder

`Tier-0 seed → Tier-1 Scout → gate → Tier-2 Deep`. In **`auto`**, escalation to
Tier-2 fires on **any** of:

- **gate fail** — top-N Scout citations score `< verify_threshold`,
- **gate-scoring-failed** — the judge call errored, so the gate cannot vouch;
  treated as a gate-fail for routing (climbs if a tier remains), with the flag
  retained (see the pinned failure contract),
- **Scout malformed** — a typed backend/parse failure that is *not* a clean
  result (see the empty-case split — this is the only "empty-ish" case that
  climbs),
- **`broad` classification** — routes straight to Deep (Scout skipped, no gate),
- **`mode=deep`** — seed → Deep directly.

What does **not** escalate: a Scout **typed-unavailable** (degrades to the
Tier-0 floor) and a Scout **honest-empty** (returns the seed result, no climb).

### Empty-case split (fixes the ladder/AC8 contradiction)

The earlier blanket "empty Tier-1 → escalate" was wrong. The three distinct
outcomes of a Tier-1 run are kept separate, matching the typed-failure-vs-honest
convention:

1. **`typed-unavailable`** (e.g. `ScoutUnavailable:<cause>`) → **degrade** to the
   existing Tier-0 floor with the existing `scout-degraded:<cause>` note. **No
   escalation** (a down tier is not a wrong answer).
2. **`honest-empty`** (Scout ran cleanly, parsed zero citations) → gate skipped
   (nothing to score), **return the Tier-0 seed** tagged `gate-skipped:scout-empty`
   (+ `+no-matches` when the seed is also empty). **No escalation** (honest
   "nothing found", never a silent or escalated false climb). The flag is what
   keeps this `[0,1]`/`[1]` path from being read as a high-confidence gated-pass.
3. **`malformed`** (ran but produced an un-scoreable / typed-bad result) →
   **escalate** to Tier-2 in `auto` (the gate cannot vouch for it).

### mode semantics

- **`auto`** — full ladder (seed → Scout → gate → Deep as triggered above).
- **`fast`** — Tier-1 is an explicit **cost ceiling the caller chose**: stop after
  Tier-1, **never escalate** — even for a `broad` query (fast wins over broad).
  The gate runs **informationally**; if it would have failed, return the Tier-1
  result tagged `gate-low-confidence` (honest, not escalated).
- **`deep`** — `Tier-0 seed → Tier-2` (skip Scout after the seed). Classification
  is ignored. Unchanged from Wave 4.

### confidence + tiers_run

`confidence` (`high` / `medium` / `low`) and `tiers_run` are **derived from the
actual path taken**, not assumed. The level is a function of the **terminal tier
+ flags**, independent of whether a seed ran (so `index_ready=false` query-only
prefixes map identically to their seeded counterparts):

| realized path | confidence |
|---------------|------------|
| gated-pass (gate verified, no flag) — `[0,1]` / `[1]` | `high` |
| Scout honest-empty (`gate-skipped:scout-empty`) — `[0,1]` / `[1]` | `medium` (seed has matches) / `low` (`+no-matches`) |
| escalated to Deep — `[0,1,2]` / `[1,2]` | `medium` |
| `broad` / `deep` straight-to-Deep — `[0,2]` / `[2]` | `medium` |
| Scout degrade floor — `[0]` / query-only empty | `low` |
| **any** `gate-low-confidence` or `gate-scoring-failed` flag present | `low` (overrides the above) |

The level keys on **terminal tier + flags**, never path tokens alone — which is
why honest-empty (`gate-skipped:scout-empty`) is a distinct row from the
gated-pass it shares tokens with: a "nothing found" result must never read as
`high` (no-false-capability).

### Degradation — UNCHANGED

The existing degradation posture is **not touched** beyond the empty-case split
above (which clarifies, not changes, the existing typed-vs-honest rule):

- Typed-failure-only fallback (the existing tier floors) — tier-down only on a
  **typed unavailable**, never on weak output.
- Weak / honest-empty citations stay **honest tier results** — they do **not**
  auto-escalate as if the tier had failed.
- **Gate scoring failure → does not block.** Per the pinned failure contract:
  escalates in `auto` when a tier remains (flag retained), else best-effort
  un-gated Tier-1 + `gate-scoring-failed` — never a hard block and never a silent
  pass.

## Acceptance criteria

`[unit]` = fakes / injected, no model. `[integration]` =
`@pytest.mark.integration`, skip-not-fail.

1. **[unit] Pinned NEW `auto` contract.** Assert the **realized** `tiers_run`:
   gated-pass ⇒ `[0,1]` (Tier-2 **not** spent); escalated ⇒ `[0,1,2]` (Tier-2
   spent); `broad` ⇒ `[0,2]`; **and at least one `index_ready=false` prefix** —
   gated-pass ⇒ `[1]`, escalated ⇒ `[1,2]` — so the no-seed query-only path is
   asserted, not just claimed. This AC **replaces** the Wave-0 zero-call lock —
   the old lock is removed in the **same** change that adds this one (lockstep;
   no unspecified window).
2. **[unit] Classifier.** Representative `point` queries → `point`; broad / trace
   / audit queries → `broad`; **ambiguous → `point`**.
3. **[unit] Planning matrix — all 12 rows.** Each
   `(mode, classification, index_ready)` row → its asserted **planned ladder**
   per the table (including every `index_ready=false` row dropping the leading
   `0`, and `fast`+`broad` ⇒ `[0,1]`).
4. **[unit] Cost lever held.** A `point` query whose gate **passes** resolves at
   `[0,1]` and does **not** invoke Tier-2.
5. **[unit] Gate catch.** An injected **wrong** Tier-1 citation scores
   `< verify_threshold` → escalates to Tier-2 (`[0,1,2]`).
6. **[unit] Gate pass.** A **correct** Tier-1 citation scores
   `≥ verify_threshold` → **no** escalation (`[0,1]`).
7. **[unit] mode routing.** `broad`+`auto` routes straight to Deep (`[0,2]`,
   Scout skipped); `fast` **never** escalates — even for `broad` it returns the
   Tier-1 result tagged `gate-low-confidence` when the gate would fail; `deep`
   skips to Tier-2 after the seed (`[0,2]`).
8. **[unit] Empty-case split + degradation unchanged.** Scout **typed-unavailable**
   → degrade to Tier-0 floor (`scout-degraded:<cause>`, **no** escalation);
   **honest-empty** → gate skipped, returns the seed tagged
   `gate-skipped:scout-empty` (**no** escalation), asserted for **both**
   `index_ready=true` (`[0,1]`) and `false` (`[1]`) so seed-empty and
   query-only-empty are not collapsed; **malformed** → escalates in `auto`.
   **Gate-scoring failure** → **never** a hard block; per the pinned contract it
   **escalates in `auto`** when a tier remains (`[0,1,2]` / `[1,2]`,
   `gate-scoring-failed` retained) and returns **best-effort un-gated Tier-1** +
   `gate-scoring-failed` in `fast`.
9. **[unit] confidence + tiers_run + flag ids.** Assert the full confidence map
   (gated-pass `[0,1]`/`[1]` ⇒ `high`; **honest-empty `[0,1]`/`[1]` +
   `gate-skipped:scout-empty` ⇒ `medium`/`low` — explicitly distinguished from
   the gated-pass it shares tokens with**; escalated `[0,1,2]`/`[1,2]` ⇒
   `medium`; broad/deep `[0,2]`/`[2]` ⇒ `medium`; degrade `[0]`/query-only-empty
   ⇒ `low`; `gate-low-confidence` / `gate-scoring-failed` ⇒ `low` override);
   `gate-low-confidence` / `gate-scoring-failed` / `gate-skipped:scout-empty` are
   asserted as **stable identifier strings** (not wording).
10. **[unit + integration] Air-gap (B1).** The gate calls `gateway.assert_local`
    on the **resolved** `scout_model` endpoint **before** the judge call; a
    non-loopback endpoint → `AirGapError` with the judge **never called**
    *(unit)*. End-to-end on a loopback-only endpoint, **zero** non-loopback
    egress from the gate *(integration, network-deny — the Scout/Deep pattern)*.
11. **[unit] Bounded top-N (OQ3).** The gate scores at most `verify_top_n`
    ranked citations; when the set exceeds N, the **dropped count is logged**
    (asserted), so a bounded scan is never indistinguishable from a full one.
12. **[integration] End-to-end `auto` over the real stack.** A `point` query
    resolves cheap (`[0,1]`, no Tier-2); a `broad` query **routes** to Tier-2
    (`[0,2]`, straight to Deep — not a gate-driven climb); both return
    **confined** citations.
13. **[unit] `verify_method` inert-value rejection (no-false-capability).** An
    unsupported `verify_method` (`"embedding"` / `"model_judge"` / arbitrary) is
    **rejected loudly** at `Settings` load with a typed error naming the field +
    accepted set — **never** a silent fall-through to `scout_model` or an inert
    no-op. `"scout_model"` loads cleanly.

## Freeze gate

ACs are frozen for planning **because OQ1 has landed** (`verify_method =
scout_model`) and OQ3 has landed (bounded top-N). **OQ2** (`verify_threshold` /
`verify_top_n` exact defaults) ships **provisional** (`0.6` / `3`) and is a
tuning target against the eval repo — it does **not** block the freeze, since the
ACs assert thresholding *behavior*, not the numeric default.

## Out of scope

- **Model-based classifier** — the heuristic ships; only the pluggable seam is
  built this wave.
- **Alternative gate backends** (`embedding` / `model_judge`) — the
  `verify_method` seam exists, but only `scout_model` ships.
- **Wave-2.1 substring / fuzzy** matching.
- **Any change to tier internals** — Scout / Deep / Tier-0 are shipped and
  unchanged; this wave is orchestration only.
- **Caching of gate scores** — the gate recomputes per query.

## Open questions

1. ~~Gate scoring backend~~ — **RESOLVED: `scout_model` reuse** (`verify_method`
   default). Reuses the loaded Scout fine-tune as the judge; air-gap via the
   proven 0007 endpoint path; the hot-path cost is bounded by OQ3's top-N.
2. **`verify_threshold` / `verify_top_n` defaults** — shipped **provisional**
   (`0.6` / `3`); tune against the eval repo. Does **not** block the freeze.
3. ~~Gate scoring scope~~ — **RESOLVED: bounded top-N.** A generative
   (`scout_model`) judge over an unbounded citation set would put a
   result-set-sized model cost on the hot path; top-N is what makes the sharper
   backend affordable enough to default to. Dropped count is logged
   (no-silent-truncation).
