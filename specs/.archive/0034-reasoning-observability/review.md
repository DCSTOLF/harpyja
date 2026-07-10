{
  "spec_id": "0034",
  "spec_title": "reasoning-observability",
  "reviewed_at": "2026-07-09",
  "reviewers": [
    {
      "agent": "codex",
      "verdict": "changes-requested",
      "concerns": [
        "EVIDENCE-PROVENANCE GAP (independently verified): the Why/AC2 cite the max_tokens=20 / num_predict / completion_tokens=20 / 51-char reasoning-first probe -- this is NOT present in the committed findings.md, which documents only the N=2 cap-8192 experiment. Unverified against the project's machine-evidence standard. Fix: commit the probe evidence as a durable artifact, or soften the claim.",
        "The observability-only invariant conflicts with a request-body-changing think knob unless recording vs configuration are explicitly separated and the knob is pinned default-inert.",
        "explorer_enable_thinking reconciliation is too loose for a behavior-affecting generation-control surface; needs one canonical effective-thinking-mode artifact field with enumerated values (omitted/default, native-think-true, native-think-false, chat-template-disabled, unknown).",
        "AC5 is model-contingent (true for qwen3:14b/Ollama today, not portable) -- make conditional/skip-clean, asserting recording correctness rather than universal reasoning emission.",
        "Schema mechanics under-specified: name 0034/1 explicitly, add to _KNOWN_VERIFIER_SCHEMA_VERSIONS, specify legacy defaults and whether missing reasoning fields in a new-schema artifact reject or default."
      ],
      "suggestions": [
        "Commit the probe evidence (max_tokens=20 reasoning-first result) as a durable findings artifact before citing it as pinned fact in Why/AC2, or soften the claim to match what's actually committed.",
        "Separate 'recording' from 'configuration' explicitly in the invariants so the think knob's request-body effect doesn't contradict the observability-only framing.",
        "Define a single canonical effective-thinking-mode enum field and route explorer_enable_thinking reconciliation through it.",
        "Make AC5 conditional/skip-clean rather than asserting universal reasoning emission across models/backends.",
        "Name the schema version target (0034/1) and its version-gate mechanics explicitly in the spec."
      ],
      "guardrail_violations": [],
      "convention_violations": [],
      "notes": "No guardrail or convention violations flagged."
    },
    {
      "agent": "claude-p",
      "verdict": "changes-requested",
      "concerns": [
        "Invariant 1 ('never what the model generates') is contradicted by the spec's own What/Why, which frame this as 'exposing and CONTROLLING' -- the invariant becomes false the moment the think knob is flipped. Reword to what's actually claimable: default-config outbound request bodies are byte-identical pre/post-0034; the knob is default-omit/no-op and operator opt-in only.",
        "The per-turn capture plumbing is hand-waved and the named route CANNOT work as described: wrapped_model_call sets _last_served_model per-RUN (a last-write scalar, not per-turn); LoopResult.history == session.messages(), which is DOUBLE-DUTY as the outbound wire messages -- annotating it mutates the request body, violating Invariant 1 -- and it strips _Session.records extras. A NEW backend-side per-turn accumulator is required; OQ2 must be resolved in-spec toward it, not left open.",
        "AC2's discriminator is UNREACHABLE via history capture: on finish_reason='length' the loop returns BEFORE session.add of the assistant message -- the truncated turn never enters model_turns. Only a backend-side model_call wrapper sees that response.",
        "Per-turn finish_reason is checked by the loop today and then DISCARDED -- it lands nowhere in the trajectory. AC2's shape is not expressible IN THE RECORD as things stand; the spec must name the recorded field explicitly.",
        "AC4's 'byte-unchanged' claim is a category error: VerifierResult.to_dict() stamps the CURRENT schema version, so re-serialized legacy re-verification is NOT byte-identical post-bump. Pin outcome-EQUALITY (status/failure_reason/four facts) instead, and disclaim byte identity.",
        "AC5 is model-contingent with no fallback -- the same finding as the 0033 AC7 issue -- and also a convention violation against the 0023 input-validity-precondition rule. Add a not-exercised fallback with a positive precondition probe.",
        "Reasoning-length UNIT is unspecified: the probes measured CHARS, but the cap is enforced in TOKENS. Chars can prove presence but cannot quantify budget share. Name the unit explicitly and pin 0-vs-None semantics."
      ],
      "suggestions": [
        "Resolve OQ2 in-spec toward a backend accumulator that appends (reasoning_length, finish_reason, think-mode) per response -- this sees every response including the truncated final one, and keeps wire messages byte-untouched.",
        "Surface usage.completion_tokens additively in the same gateway change (the cap's actual currency) -- without it, any future max_tokens revisit has only chars to work with.",
        "Resolve OQ1 now toward coexist-with-one-recorded-effective-mode, since index.md still documents llama.cpp as a supported target.",
        "Extend AC3 with a default-omit request-body pin so the invariant is testable and rots false on drift, not just prose.",
        "OQ3: drop the opt-in full-text side-channel for now.",
        "Tighten epistemic language: 'thinks by default' -> instance-relative 'qwen3:14b on this Ollama'; 'cap pressure' -> 'invisible-truncation-RISK' per findings.md's actual support."
      ],
      "guardrail_violations": [],
      "convention_violations": [
        {
          "rule": "resolve-OQ-toward-the-invariant (the 0033 precedent: open questions that keep a fix-location option alive contrary to a stated invariant must be resolved in-spec before planning)",
          "location": "Invariant 1 / Open Question 2 (per-turn capture routing left open despite Invariant 1's observability-only claim)"
        },
        {
          "rule": "0023 input-validity-precondition (model-contingent acceptance criteria need a not-exercised fallback with a positive precondition probe)",
          "location": "Acceptance Criteria AC5"
        }
      ],
      "notes": "All concerns code-verified against the current implementation (wrapped_model_call, LoopResult.history/session.messages(), VerifierResult.to_dict(), the loop's finish_reason handling)."
    }
  ],
  "synthesis": {
    "verdict": "changes-requested",
    "agreement": "Both agents independently flag the tension between the observability-only invariant and the request-body-changing think knob: codex wants recording and configuration explicitly separated; claude-p supplies the concrete testable mechanism (reword the invariant to a default-omit/no-op pin and extend AC3 with a request-body byte-identity test) -- the two are compatible, with claude-p's version being the more implementable form. Both agents also independently flag AC5 as model-contingent with no fallback, and both want the schema target (0034/1, version-gate mechanics) named explicitly rather than left to plan time. Where they diverge: claude-p uniquely established the structural capture findings (concerns 2, 3, 4 above) through direct code verification -- these are the highest-severity items because they show the spec's named per-turn capture route (LoopResult.history / session.messages()) is not just underspecified but actively unworkable, making AC2 unreachable and AC4's byte-unchanged claim false as stated. Without resolving these, the spec is unimplementable as currently routed. codex uniquely established the evidence-provenance gap: the max_tokens=20/reasoning-first probe cited as empirically pinned in Why/AC2 is not present in the committed findings.md, which only documents the N=2 cap-8192 experiment -- this is a machine-evidence-standard violation independent of the structural issues.",
    "concerns": [
      "BLOCKING (claude-p, code-verified): the named per-turn capture route cannot work. wrapped_model_call's _last_served_model is a per-run scalar, not per-turn; LoopResult.history is session.messages(), which does double duty as the outbound wire messages, so annotating it would mutate the request body (violating Invariant 1) and strips _Session.records extras. A new backend-side per-turn accumulator is required; OQ2 must be resolved in-spec toward it before planning.",
      "BLOCKING (claude-p, code-verified): AC2's discriminator is unreachable via history capture -- on finish_reason='length' the loop returns before session.add of the assistant message, so the truncated turn never enters model_turns. Only a backend-side model_call wrapper observes that response. Relatedly, finish_reason is currently checked and discarded by the loop and must be named as a recorded field for AC2's shape to be expressible in the record at all.",
      "BLOCKING (codex, independently verified): the max_tokens=20 / reasoning-first / 51-char probe cited in Why and AC2 as empirically pinned is not present in the committed findings.md (which documents only the N=2 cap-8192 experiment). Must be committed as a durable evidence artifact or the claim softened, per the project's machine-evidence standard.",
      "Invariant 1 ('never what the model generates') is falsified by the spec's own framing of the think knob as something this spec 'controls.' Both agents want it reworded to what's actually claimable; claude-p's concrete form (default-config request bodies byte-identical pre/post-0034, knob default-omit/no-op and opt-in) is the more testable version and should be paired with an AC3 request-body pin.",
      "AC4's 'byte-unchanged' claim is a category error given VerifierResult.to_dict() stamps the current schema version on any re-serialization -- must be restated as outcome-equality (status/failure_reason/four facts) with byte-identity explicitly disclaimed.",
      "AC5 is model-contingent (qwen3:14b/Ollama-specific) with no fallback -- flagged by both agents, and claude-p additionally identifies this as a convention violation against the 0023 input-validity-precondition rule (same class of issue as 0033's AC7 finding). Needs a not-exercised fallback with a positive precondition probe.",
      "Schema/unit precision gaps: the verifier schema version (0034/1), version-gate mechanics, and legacy-default behavior are unnamed (codex); the reasoning-length unit is unspecified where probes measured chars but the cap is enforced in tokens, with 0-vs-None semantics undecided (claude-p) -- usage.completion_tokens should be surfaced additively alongside chars.",
      "explorer_enable_thinking reconciliation (OQ1) is left too open for a behavior-affecting generation-control surface; needs one canonical effective-thinking-mode enum field, resolved toward coexist given llama.cpp is still documented as a supported gateway target."
    ],
    "suggestions": [
      "Resolve OQ2 in-spec toward a backend-side per-turn accumulator appending (reasoning_length, finish_reason, think-mode) per response -- this is the only route that observes every response including the truncated final turn while keeping wire messages byte-untouched.",
      "Reword Invariant 1 to a default-omit/no-op pin (default-config outbound bodies byte-identical pre/post-0034) and extend AC3 with an explicit request-body byte-identity test so the invariant rots false on drift rather than staying prose.",
      "Name per-turn finish_reason as a recorded trajectory field so AC2's cap-pressure-attribution shape is actually expressible in the record.",
      "Restate AC4 as outcome-equality (status/failure_reason/four facts unchanged) with byte-identity explicitly disclaimed, given VerifierResult.to_dict()'s current-schema-version stamping.",
      "Add a 0023-style not-exercised fallback with a positive precondition probe to AC5.",
      "Name the reasoning-length unit (chars) explicitly and surface usage.completion_tokens (tokens) additively in the same gateway change; pin 0-vs-None semantics.",
      "Name the schema version target (0034/1), add it to _KNOWN_VERIFIER_SCHEMA_VERSIONS, and specify legacy-default and missing-field behavior explicitly.",
      "Resolve OQ1 toward coexist-with-one-recorded-effective-mode (a single canonical effective-thinking-mode enum field), since llama.cpp remains a documented supported target.",
      "Drop OQ3 (opt-in full-text side-channel) for now.",
      "Commit the max_tokens=20 reasoning-first probe evidence as a durable artifact (fixing the stale 0033 ref path -- 0033 now lives under specs/.archive/) before citing it as pinned fact; tighten epistemic language to instance-relative claims ('qwen3:14b on this Ollama' rather than 'thinks by default') and 'invisible-truncation-risk' rather than 'cap pressure' per what findings.md actually supports."
    ],
    "guardrail_violations": [],
    "convention_violations": [
      {
        "rule": "resolve-OQ-toward-the-invariant",
        "location": "Invariant 1 / Open Question 2",
        "raised_by": "claude-p"
      },
      {
        "rule": "0023 input-validity-precondition",
        "location": "Acceptance Criteria AC5",
        "raised_by": "claude-p (independently corroborated by codex's model-contingency concern)"
      }
    ]
  },
  "recommended_next_step": "Do not proceed to /speccraft:spec:plan yet, but this does not require a full re-review round -- apply the following ~10 targeted edits (wording/AC-precision plus committing the probe evidence; no scope change), then mark reviewed without a full re-round, per the 0032/0033 flow: (1) commit the max_tokens=20 reasoning-first probe evidence as a durable findings artifact and fix the stale 0033 ref path (0033 now lives under specs/.archive/0033-scoped-grep-paths/); (2) reword Invariant 1 to a default-omit/no-op pin (default-config outbound request bodies byte-identical pre/post-0034, knob opt-in) and extend AC3 with an explicit request-body byte-identity test; (3) resolve OQ2 in-spec toward a backend-side per-turn accumulator (not the LoopResult.history/session.messages() route, which is unworkable); (4) name per-turn finish_reason as a recorded trajectory field so AC2's cap-pressure-attribution shape is reachable; (5) restate AC4 as outcome-equality (status/failure_reason/four facts), explicitly disclaiming byte-identity given VerifierResult.to_dict()'s schema-version stamping; (6) add a 0023-style not-exercised fallback with a positive precondition probe to AC5; (7) name the reasoning-length unit (chars) explicitly and surface usage.completion_tokens (tokens) additively; pin 0-vs-None semantics; (8) name the schema version target 0034/1, its version-gate mechanics, and legacy-default/missing-field behavior; (9) resolve OQ1 toward coexist-with-one-recorded-effective-mode (single canonical effective-thinking-mode enum field); drop OQ3; (10) tighten epistemic language throughout (instance-relative claims, 'invisible-truncation-risk' rather than 'cap pressure')."
}
