---
spec: "0038"
reviewers: [codex, claude-p]
quorum: 1
verdict: approve-with-comments
generated: 2026-07-10T00:00:00Z
---

# Cross-model review — 0038-reconciliation

## claude-p

**Verdict:** approve-with-comments

Concerns:
- Transport residency is implied but never stated: the spec says "the explorer's gateway call" but does not require the probe-proven `/api/chat` path ship as a `ModelGateway` method. An implementer could add a parallel HTTP client in `harpyja/scout/` and satisfy every AC while creating a second outbound caller — a hole at exactly the seam the air-gap guardrail depends on.
- AC4's blast-radius list omits the two gateway-level invariants every new outbound path must carry: `gateway.assert_local` on the resolved endpoint BEFORE any I/O, and the finite per-socket-op `timeout_s` bound (the B3/spec-0017 rule). A new endpoint that inherits neither would pass the enumerated regressions.
- `explorer_think=None` semantics under a transport switch are ambiguous: "None preserves current default behavior" could mean (a) None stays on `/v1` while only True/False route via `/api/chat` (two transports, per-request), or (b) the whole explorer moves and None simply omits `think` on the new endpoint. These have very different blast radii; the spec should pick one or explicitly delegate the choice to the probe with both branches scoped.
- The 0034 pin "None ⇒ outbound request body byte-identical to pre-0034 (params == {max_tokens: 2048})" cannot survive a full endpoint switch (`max_tokens` becomes `options.num_predict`, the URL changes). That exact pin is nowhere in the blast radius; per the exact-pin reconciliation convention it must be amended deliberately in the same change, with rationale — not left to fail as a surprise.
- AC7's "0037 conditional AC2/AC3 auto-arm" mechanics are underspecified. Those tripwires load the machine-recorded outcome from `probe_result.json`, which is drift-pinned by `test_think_probe_result.py` and now lives under `specs/.archive/0037-.../` post-close. If wiring moves off `/v1`, the spec must state whether the tripwires test "the wired path" (requiring the flipped outcome to live somewhere — editing archived, drift-pinned evidence, or a new 0038 artifact) or are simply superseded/retired.
- Native `/api/chat` `tool_calls` have historically omitted `id` fields on some Ollama versions; the 0029 answer-all-N protocol answers each call BY its `tool_call_id`. If ids are absent this is an endpoint-migration concern (synthesized-id/positional scheme), not a field rename — worth naming as an explicit probe question; OQ2 currently frames the format question too generically.
- The 0038 probe's typed outcome enum is not enumerated in the spec. The tripwire convention requires the committed enum be the total answer space, with its own schema version (presumably `0038/1`, not a reuse of `0037/1`).

Suggestions:
- Add an invariant that the honoring path ships as a new/extended `ModelGateway` method (single outbound abstraction), asserting `assert_local` before I/O and carrying a finite `timeout_s` — and add both to AC4's regression list.
- Resolve the None-routing question in the spec text (or make it a probe-decided branch with both outcomes scoped), and name the 0034 request-body byte-identical pin as a deliberately reconciled casualty of the switch.
- Enumerate the 0038 probe outcome enum + schema version in the spec text, and author its artifact pin against `specs/.archive/0038-.../` per the path-pin convention (0037's close proved live-path pins break at archive time).
- State whether `derive_think_mode` needs a transport dimension: post-switch, "native-think-true/false" become genuinely effective while the enum's semantics were minted under `/v1` — confirm the 0034 enum still disambiguates, or extend it in the same change.
- Consider recording the serving transport (endpoint identity) as an optional trajectory-artifact field under a `0038/1` verifier bump, so the four-facts invariant is checkable per-transport rather than assumed.

## codex

**Verdict:** changes-requested

Concerns:
- AC1/AC3 require a `completion_tokens` delta, but native Ollama `/api/chat` does not necessarily expose the OpenAI `/v1` `usage.completion_tokens` shape; the spec must explicitly define the native usage-to-`completion_tokens` mapping (likely from `eval_count`) before making it proof-bearing.
- The spec says `None` preserves current default behavior while AC3 requires default reasoning-present; that's plausible from 0037 on `/v1`, but native `/api/chat`'s default/on behavior still needs to be in the probe matrix, not assumed from the false-control arm.
- The endpoint migration is described well, but the spec should explicitly require the production native path to remain inside `ModelGateway`, preserving the single outbound abstraction and single `assert_local` air-gap enforcement point.

Suggestions:
- Add a small native-response contract section naming exact field mappings: request `max_tokens` → `num_predict`, response `done_reason` → `finish_reason`, `eval_count` (or equivalent) → `completion_tokens`, native thinking field → `reasoning`, native tool calls → the existing loop shape.
- Split the probe artifact outcome into path plus evidence — e.g. `chosen_path`, `outcome`, `usage_mapping`, and per-arm observed facts — so future drift can distinguish endpoint failure from adapter failure.
- Add an explicit negative test that Deep/RLM does not call the native `/api/chat` adapter and still emits no `think` field.

## Guardrail violations

None reported by either agent.

## Convention violations

Both agents independently and identically flagged the **same frontmatter violation**:

- **Rule:** Spec frontmatter uses the canonical schema and nothing else (`id`, `title`, `status`, `started_at_sha`, `created`).
- **Location:** Frontmatter block (lines 1-9) — missing `started_at_sha`; carries non-canonical keys `authors`, `packages`, `related-specs`; `packages: []` is empty though gateway/scout/config will clearly be touched.
- **Status:** Convergent, mechanical fix, no design judgment required. Fix before `/speccraft:spec:plan`.

claude-p additionally flagged a second convention concern (not raised by codex): the 0034 exact-pin reconciliation convention ("a deliberate change to a code-enforced exact pin is reconciled in one change") is at risk because the None⇒byte-identical outbound-request pin is invalidated by any endpoint switch but is not named for reconciliation anywhere in the blast radius.

## Synthesis

Both agents land on approve-ish territory in substance — codex's formal verdict is changes-requested, claude-p's is approve-with-comments — but their concerns converge tightly on three points, which is the strongest signal in this review:

1. **ModelGateway residency must be explicit.** Both agents independently identified the same latent hole: the spec talks about "the explorer's gateway call" and "adapt the tool-calling request/response shape" but never states that the new/extended path must be a `ModelGateway` method carrying `assert_local` and a finite `timeout_s`. Without this stated as an invariant and reflected in AC4's regression list, an implementer could satisfy every AC as written while opening a second, unguarded outbound caller — undermining the exact seam the air-gap guardrail depends on. This is the single highest-priority fix.

2. **Frontmatter convention violation.** Identical finding from both agents, mechanical to fix: add `started_at_sha`, drop `authors`/`packages`/`related-specs` (or fold `related-specs` content into `Ref:` prose per convention if it doesn't have a canonical home), and populate `packages` correctly if it is canonical.

3. **`None`/default behavior needs precision on both axes.** claude-p's routing-ambiguity concern and codex's native-default-must-be-probed concern are two faces of the same underspecification: the spec assumes native `/api/chat`'s None/default behavior mirrors `/v1`'s without either (a) stating which transport None ultimately lands on, or (b) requiring the native default arm be observed in the probe matrix rather than inferred from the false-control arm. Tied to this is the 0034 byte-identical outbound-request pin, which a full endpoint switch necessarily breaks and which is not currently named anywhere in the blast radius for deliberate reconciliation.

Beyond the convergent items, each agent raised valid non-overlapping concerns worth folding into the spec: codex's native-response field-mapping contract (`eval_count`→`completion_tokens`, `done_reason`→`finish_reason`, etc.) and split probe-artifact shape; claude-p's tool_call `id`-presence question, the underspecified 0037 auto-arm mechanics against a drift-pinned/archived `probe_result.json`, and the missing 0038 probe outcome enum/schema version. None of these are design flaws — the overall shape of the spec (probe-first, two-factor proof, explicit mechanism-change invariant, Deep isolation, recording-survives) is sound and correctly inherits 0037's lessons. They are enumeration and precision gaps that should close before planning turns into implementation surprises.

Quorum is met (claude-p's approve-with-comments satisfies the 1-approve rule), so this spec is not blocked from proceeding. However, codex's changes-requested concerns are substantive and should be treated as required pre-plan edits, not optional comments — burying them under the quorum-met label would defeat the purpose of running two reviewers.

**Action:** Overall disposition — proceed to `/speccraft:spec:plan` ONLY after the spec author makes the following edits (ordered by importance):

1. **Add the ModelGateway-residency invariant.** State explicitly that the honoring path ships as a new/extended `ModelGateway` method — the single outbound abstraction — carrying `assert_local` before any I/O and a finite `timeout_s`. Add both to AC4's regression list. (Convergent — both agents.)
2. **Fix the frontmatter.** Add `started_at_sha`; remove or re-home `authors`, `packages`, `related-specs` per the canonical schema; populate `packages` if kept. (Convergent — both agents; mechanical.)
3. **Resolve the None/default-behavior question, on both the routing axis and the probe-evidence axis.** State definitively whether `None` moves fully to the new transport or stays split across two transports (or make it an explicitly probe-decided branch with both outcomes scoped in the spec). Require the probe matrix to observe native `/api/chat`'s actual default/on behavior rather than inferring it from the `think:false` control arm. In the same edit, name the 0034 byte-identical-outbound-request pin as a deliberate reconciliation casualty of the switch, per the exact-pin reconciliation convention.
4. **Add a native-response field-mapping contract** (codex): explicit mappings for `max_tokens`→`num_predict`, `done_reason`→`finish_reason`, `eval_count`(or equivalent)→`completion_tokens`, native thinking field→`reasoning`, native tool_calls→existing loop shape — and split the probe artifact into `chosen_path`/`outcome`/`usage_mapping`/per-arm observed facts so drift can later distinguish endpoint failure from adapter failure.
5. **Specify 0037 auto-arm mechanics** (claude-p): state whether AC7's "0037 conditional AC2/AC3 auto-arm" is keyed to the `/v1` top-level `think` finding (in which case it never legitimately flips and the honest close is "superseded by 0038") or to "the wired path" (in which case state where the flipped outcome is recorded, given `probe_result.json` is drift-pinned and archived).
6. **Enumerate the 0038 probe outcome type** — the typed enum (e.g., path chosen / STILL_BLOCKED / etc.) and its schema version (`0038/1`, not a reuse of `0037/1`) — directly in the spec text.
7. **Name the tool_call `id`-presence question explicitly in OQ2** (claude-p) and **add the Deep/RLM negative test** — that Deep does not call the native adapter and still emits no `think` field (codex) — as an explicit AC or invariant addition.
