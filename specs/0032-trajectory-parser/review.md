{
  "spec_id": "0032",
  "spec_title": "trajectory-parser",
  "reviewed_at": "2026-07-08",
  "reviewers": [
    {
      "agent": "codex",
      "verdict": "approve-with-comments",
      "concerns": [
        "AC2 says build_trajectory_record must produce the same typed failure as verify_trajectory, but build_trajectory_record currently returns a dict, not a VerifierResult-style typed outcome. The spec needs to state whether it should raise VerificationError, return an error-bearing record, or delegate to a helper whose tuple result is asserted directly.",
        "AC1's 'single-definition assertion' is directionally right but underspecified. It should define what counts as a parser definition and how the test proves build_trajectory_record and verify_trajectory both use it without relying on brittle source-text greps.",
        "AC6's 'same result' is weaker than the earlier 'byte-identically' claim. Re-verifying to the same PASSED/FAILED/failure_reason is useful, but it does not prove artifact shape, tool_names_invoked ordering, or serialized output preservation.",
        "OQ2 is reasonable as an audit, but the current wording risks scope creep by saying any second divergent parse 'should be fixed in this spec.' That can turn a narrow blocker into an unbounded refactor unless the fix is similarly small and measurement-critical."
      ],
      "suggestions": [
        "Specify the canonical parser contract explicitly, e.g. extract_tool_names_from_model_turns(model_turns) -> tuple[list[str], bool, str | None], with verify_trajectory and build_trajectory_record adapting around that contract.",
        "Clarify build_trajectory_record's failure behavior for malformed tool calls before implementation.",
        "Strengthen AC6 to compare normalized verifier artifacts or selected golden fields, including schema_version, failure_reason, tool_names_invoked, terminal_bucket, model identity fields, and ordering, not only verification status.",
        "Keep OQ2 blocking for discovery and classification, but require same-spec fixes only for another duplicate parser that affects the four verifier facts or artifact measurement semantics."
      ],
      "guardrail_violations": [],
      "convention_violations": [
        {
          "rule": "Specs should have testable acceptance criteria with unambiguous observable outcomes.",
          "location": "Acceptance Criteria AC1 and AC2"
        },
        {
          "rule": "Trajectory-verified measurement must preserve durable verifier artifact semantics for the four facts.",
          "location": "Acceptance Criteria AC6"
        }
      ]
    },
    {
      "agent": "claude-p",
      "verdict": "approve-with-comments",
      "concerns": [
        "Unresolved tension between the 'cutover, not redesign' invariant (change ONLY the tool-name parsing seam; Out of Scope explicitly excludes 'Any Scout/tool/gateway behavior change') and the strict-wins invariant applied to build_trajectory_record, which explorer_backend.py calls live during real Scout tool-calling loops (not just at eval time). If strict-wins is implemented as build_trajectory_record raising/propagating a failure on a nameless tool_call, that changes ExplorerBackend's live run behavior on malformed model output -- which the spec says is out of scope. The spec doesn't specify whether the unified parser's failure signal reaches build_trajectory_record as an exception or as a non-raising sentinel field, and only one of those choices is compatible with the stated scope boundary.",
        "OQ2's action item ('if a second divergent parse exists... fix it in this spec') directly contradicts the 'cutover, not redesign' invariant's restriction to 'change ONLY the tool-name parsing seam.' A positive OQ2 finding would force the plan to either violate the invariant or defer the fix (contradicting OQ2's own instruction) -- should be reconciled before /speccraft:spec:plan, e.g. by scoping OQ2 to 'discover and file a new blocker spec' rather than 'fix here.'",
        "AC6 only claims the real astropy/django trajectories re-verify to 'the same result' (astropy empty / symbols-not-invoked) -- a coarse status/bucket-level comparison. This doesn't rule out the deduped parser producing a different tool_names_invoked list or a different failure_reason while still landing on the same terminal_bucket by coincidence, weaker proof than the spec's own 'byte-identical' framing implies."
      ],
      "suggestions": [
        "Resolve OQ1 by noting that explorer_backend.py already imports from live_verifier.py today (confirmed by grep), so the 'avoid backend->verifier import' concern motivating a shared module is largely moot -- keeping the canonical parser in live_verifier.py is the smaller, invariant-preserving change unless there's an independent reason to hoist it.",
        "Add an explicit design note (either as an AC or as OQ1a) specifying HOW build_trajectory_record surfaces the strict-wins failure -- sentinel value in the record vs. raised exception -- and require a regression test proving ExplorerBackend.run()'s live control flow on a nameless-tool_call trajectory is unchanged, to make the 'no Scout behavior change' scope boundary independently testable rather than implicit.",
        "Strengthen AC6 to diff the full pre- and post-refactor verifier artifact JSON (or VerifierResult field-by-field: model_identity, tool_names_invoked, terminal_bucket, failure_reason) against a snapshot captured before the dedup, not just the final PASSED/FAILED + bucket label.",
        "Clarify AC4's scope: 'no code path returns a partial tool list... without failing' reads as a codebase-wide universal claim, but is presumably scoped to the two known call sites plus the canonical parser. State that scope explicitly so the AC is testable without requiring an exhaustive whole-repo proof."
      ],
      "guardrail_violations": [],
      "convention_violations": []
    }
  ],
  "synthesis": {
    "verdict": "approve-with-comments",
    "agreement": "Both agents independently converge on the same three defects, one of which (the build_trajectory_record failure-surfacing ambiguity) is a genuine pre-plan blocker, not a nice-to-have.",
    "concerns": [
      "BLOCKING before /speccraft:spec:plan: The spec does not say HOW build_trajectory_record surfaces the strict-wins failure on a nameless tool_call (raise VerificationError vs. a non-raising sentinel/typed-failure field in the returned record). This is not cosmetic: explorer_backend.py calls build_trajectory_record LIVE, mid-loop, on every real Scout run (not just in eval/verify contexts) to populate self.last_trajectory. If strict-wins is implemented by raising, that changes ExplorerBackend's live control-flow behavior on malformed model output, which directly conflicts with the spec's own Out-of-Scope line 'Any Scout/tool/gateway behavior change' and the 'cutover, not redesign' invariant. If implemented as a sentinel/typed-failure-in-record, no Scout behavior changes, but AC2/AC4's language ('a tool_call lacking function.name is a FAILURE, never a silent skip') needs to say explicitly that the failure is carried as data, not raised, at this call site.",
      "OQ2's action-item wording ('if a second divergent parse exists... fixed in this spec') is in direct tension with the 'cutover, not redesign' invariant restricting the change to the tool-name parsing seam. As written, a positive audit finding forces a choice between violating the invariant or defying OQ2's own instruction. Should be resolved before planning.",
      "AC6's proof of behavior-preservation is weaker than the spec's own 'byte-identically' claim in the What section. Comparing only terminal PASSED/FAILED + terminal_bucket does not rule out the deduped parser silently producing a different tool_names_invoked list or a different failure_reason that happens to still land on the same bucket.",
      "AC1's 'single-definition assertion' and AC2's 'same typed outcome' are directionally correct but underspecified as testable criteria -- need to define what a passing assertion actually checks (import-graph/identity check vs. brittle source grep) before implementation."
    ],
    "suggestions": [
      "Add an explicit design note (OQ1a or a new AC) pinning down the build_trajectory_record failure-surfacing mechanism (sentinel/typed field, not exception) and require a regression test proving ExplorerBackend.run()'s live control flow on a nameless-tool_call trajectory is byte-for-byte unchanged -- this makes the 'no Scout behavior change' boundary independently testable.",
      "Resolve OQ1 explicitly: explorer_backend.py already imports build_trajectory_record from live_verifier.py today, so the backend->verifier import-direction concern motivating a shared module is already moot in practice; keeping the canonical parser in live_verifier.py is the smaller, invariant-preserving choice absent an independent reason to hoist it.",
      "Reword OQ2 to 'discover and file a new blocker spec if found' rather than 'fix it in this spec,' consistent with how 0032 itself was carved out of 0031 rather than folded into it.",
      "Strengthen AC6 to a field-by-field (or full-JSON) diff of the pre- and post-refactor verifier artifact/VerifierResult -- schema_version, status, failure_reason, tool_names_invoked (incl. ordering), model_identity, model_invoked, terminal_bucket, served_model, endpoint -- not just the final status/bucket label, to make the 'byte-identical on valid input' claim actually hold at the granularity the bake-off will depend on.",
      "Define AC1's 'single-definition assertion' concretely (e.g., an import-identity/is-same-function test) rather than leaving it as a prose grep proxy; scope AC4's 'no code path' language explicitly to the two known call sites plus the canonical parser, not a whole-repo universal claim."
    ],
    "guardrail_violations": [],
    "convention_violations": [],
    "cross_checks_performed_by_delegator": [
      "Read harpyja/eval/live_verifier.py directly: confirmed the two call sites exist exactly as described -- extract_tool_names (lines 265-288, strict, returns tool-names-unextractable on a nameless call) and the inline loop in build_trajectory_record (lines 336-346, silent-skip via 'if name and name not in seen').",
      "Confirmed explorer_backend.py (harpyja/scout/explorer_backend.py, line 26) already imports build_trajectory_record from harpyja.eval.live_verifier, and calls it live at line ~289-291 to populate self.last_trajectory during real Scout runs -- this is the basis for both agents' shared concern about live-behavior-change risk and is also relevant to answering OQ1.",
      "Grepped for other candidate duplicated-parse fields (model identity, tiers_run, terminal_bucket) relevant to OQ2: tiers_run is set as an explicit literal by callers (not independently re-parsed in two places), model identity is only implemented once in extract_model_identity(), and terminal_bucket is only implemented once in extract_terminal_bucket(). This suggests OQ2's audit will likely come back clean, but was not exhaustive and does not substitute for the AC7-required audit."
    ]
  },
  "recommended_next_step": "Do not proceed to /speccraft:spec:plan yet. Revise the spec to: (1) pin down whether build_trajectory_record's strict-wins failure is a raised exception or a non-raising typed/sentinel field in the returned record, and add an explicit no-live-behavior-change regression requirement for ExplorerBackend; (2) reword OQ2 to file-a-new-spec-if-found rather than fix-in-this-spec, removing the tension with the 'cutover, not redesign' invariant; (3) strengthen AC6 to a field-by-field verifier-artifact diff rather than a terminal PASSED/FAILED + bucket comparison. These are small, targeted wording/AC changes, not a scope change -- re-review is not required for a human sign-off, but the plan step should not begin until the build_trajectory_record failure-surfacing question is answered, since it determines the implementation shape of the entire dedup."
}
