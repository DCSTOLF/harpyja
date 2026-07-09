{
  "spec_id": "0033",
  "spec_title": "scoped-grep-paths",
  "reviewed_at": "2026-07-08",
  "reviewers": [
    {
      "agent": "codex",
      "verdict": "approve-with-comments",
      "concerns": [
        "AC4 says Tier-0 locate is asserted unaffected on unscoped input, but production Tier-0 passes scope=req.repo_path (an absolute repo-root scope), not no-scope. The regression pin should cover repo-root scope explicitly, not just None and '.'.",
        "The blast-radius enumeration omits a shared-engine consumer: explorer_tools.symbols()'s degraded fallback calls search_engine.search(\"\", scope=str(candidate)) with a FILE path (not a directory scope). This consumer should be included and pinned, or its exclusion explicitly justified.",
        "The submitted/surviving seam is the right place for the fix, but the interface shape isn't defined: submit_citations currently returns list[CodeSpan], and LoopResult only carries spans/outcome/history/turns. Without naming the new return/field shape, the plan step will drift."
      ],
      "suggestions": [
        "Prefer the repo-root rg invocation design over per-path re-prefixing: it is naturally repo-relative, handles nested/file scopes uniformly, and avoids prefix-string edge cases.",
        "Add edge-case tests: scope='astropy', 'astropy/', a nested subdirectory, an absolute repo-root scope, rg's own './' prefixing behavior, and result-ordering stability.",
        "Name the artifact fields and version explicitly: citations_submitted / citations_surviving under VERIFIER_SCHEMA_VERSION=\"0033/1\"."
      ],
      "guardrail_violations": [],
      "convention_violations": [],
      "notes": "Independently verified the root-cause chain (rg cwd=scope, no path argument, verbatim parse) and the two-normalize-passes analysis as correct. Also independently confirmed Deep search CAN pass subdirectory scopes today and carries the same defect."
    },
    {
      "agent": "claude-p",
      "verdict": "changes-requested",
      "concerns": [
        "Invariant-2/AC2 mismatch on read_span: the tool-contract invariant claims EVERY path-returning tool including read_span must emit repo-relative paths, but AC2's test list omits read_span -- and read_span only ECHOES the caller's already-validated path back (it never discovers a new path), so the producer contract over-claims. Either exclude read_span with a stated rationale, or add it to AC2 with echoes-input (not discovers) semantics.",
        "The symbols() degraded-fallback gap (also found by codex) is worse than a missing enumeration: with the DEFAULT runner (not the injected test runner), search_engine.search(\"\", scope=str(candidate)) with a FILE candidate raises NotADirectoryError today (subprocess cwd=<file>), i.e. it is already broken outside injected-runner tests. The two OQ1 fix options (rg-from-root vs re-prefix) would change this broken behavior differently. This consumer must be enumerated and its post-fix behavior pinned, not left implicit.",
        "AC5's 'legacy artifacts still validate' is unimplementable as written: validate_verifier_artifact hard-fails on schema_version != VERIFIER_SCHEMA_VERSION via strict equality, and live_verifier.py has none of report.py's _with_defaults machinery that would let older artifacts pass. The spec must scope the validator mechanism explicitly -- either a version-gate per the 0026 DATASET_SCHEMA_VERSION pattern, or a _with_defaults map mirroring report.py -- or AC5 is aspirational and will fail at plan/implement time.",
        "Internal tension between Invariant 1 (fix at the ONE engine seam, never per-caller) and Open Questions 1/2, which keep alive a wrapper-level (explorer_tools.grep) re-prefix option that would NOT reach Deep search's use of the same engine -- i.e. a per-caller fix that the invariant itself forbids. OQ1 should be resolved in-spec toward the engine seam before /speccraft:spec:plan, not left open.",
        "Factual error in the fold-in DECIDED section describing run_verified_case's cause-swallowing bug: the code DOES already bind `except ScoutUnavailable as e:` -- it discards e, but doesn't fail to bind it -- and the ValueError raise sits OUTSIDE the except block, so `e` is out of scope at the raise site (no implicit chain is possible as described). The diagnosed symptom (cause is lost) is correct, but the described fix shape ('bind the exception... from e in place') is wrong given the actual code structure -- the fix must either capture the cause before leaving the except block or restructure the raise to be inside it. Per the repo convention that code wins over the spec's assumption about it (see spec 0021), this must be corrected before planning.",
        "AC7's pass condition ('surviving > 0 when the model cites a scoped-grep hit') is model-behavior-contingent with no fallback: a live model run that happens not to grep scoped never exercises the assertion, and the AC as written gives no guidance for that outcome.",
        "AC4 pins Deep search and Tier-0 locate only as 'unaffected on unscoped input,' but Deep's SCOPED output is intentionally supposed to CHANGE (to repo-relative) under this fix -- the AC should also positively pin the new scoped-output shape for Deep, not just the unscoped no-op case.",
        "AC1's scope=None/'.' semantics are underdefined: at the engine seam, `scope or \".\"` resolves relative to the HARPYJA PROCESS's cwd, not necessarily the repo root -- every current caller happens to paper over this by always passing an absolute scope. The spec should pin AC1 at a named seam and explicitly decide whether None should come to mean 'repo root.'"
      ],
      "suggestions": [
        "Resolve OQ1 in-spec: commit to the engine-level (rg-from-root) fix only, and note that since explorer_tools.grep's wrapper passes an ABSOLUTE scope today, an rg-from-root design needs the repo-relative scope computed once at the engine seam, not reintroduced per-wrapper.",
        "Define ls's trailing-'/' entry semantics explicitly in AC2 so the contract test isn't ambiguous about directory-entry formatting.",
        "Name submit_citations' new return shape explicitly and assert no other existing caller of submit_citations breaks under the new tuple/shape.",
        "While in run_verified_case for the cause-swallowing fix, delete the dead, shadowed `last_trajectory` assignment inside the except block.",
        "Note that rg's ordering and .gitignore/ignore-file resolution may shift under an rg-from-root invocation; pin the unscoped case byte-identical via the injected runner AND add one real-rg integration case to catch this class of drift.",
        "For AC7, add the 0023 input-validity-precondition convention's fallback: if the condition (model cites a scoped-grep hit) isn't exercised in the live run, record it as not-exercised rather than treating the AC as failed, and let AC3's hermetic fixture carry the actual proof of the mechanism."
      ],
      "guardrail_violations": [],
      "convention_violations": [
        {
          "rule": "additive-fields-with-centralized-defaults (schema evolution must route through a _with_defaults-style mechanism, not bare strict-equality version checks)",
          "location": "Acceptance Criteria AC5"
        },
        {
          "rule": "one-bounded-rg-source-of-truth (the fix location rule from conventions.md)",
          "location": "Open Questions 1 and 2 (wrapper-level re-prefix option kept alive)"
        },
        {
          "rule": "blast-radius enumeration completeness for shared-engine consumers",
          "location": "Invariant 1 / Acceptance Criteria AC4 (missing explorer_tools.symbols() degraded-fallback consumer)"
        }
      ]
    }
  ],
  "synthesis": {
    "verdict": "changes-requested",
    "agreement": "Both agents independently verified the spec's root-cause chain and the two-normalize-passes analysis as correct, and both independently found the same gap in the blast-radius enumeration: explorer_tools.symbols()'s degraded fallback calls the shared search engine with a FILE-path scope, which is a consumer of the same seam and is not mentioned in AC4's enumeration. Both agents also independently want the submitted/surviving interface shape (return type, threading through LoopResult, field names, schema version) named explicitly before planning rather than left as prose. Where they diverge is severity: codex treats these as approve-with-comments-level polish; claude-p treats the symbols() gap as more severe (the default runner already raises NotADirectoryError on it today, independent of this spec's fix) and additionally surfaces several items codex did not find -- most notably a factual error in a DECIDED section (the run_verified_case exception-binding description does not match the actual code structure) and an unimplementable-as-written AC (AC5's legacy-artifact validation claim, given validate_verifier_artifact's current strict-equality behavior).",
    "concerns": [
      "BLOCKING: DECIDED section factual error -- run_verified_case's cause-swallowing bug is described as an unbound exception ('catches ScoutUnavailable without binding it'), but the code already binds `except ScoutUnavailable as e:`; the actual defect is that `e` is discarded and the ValueError raise happens OUTSIDE the except block, so it's out of scope for an implicit chain. Per the repo's established convention that code wins over the spec's assumption about it, this must be corrected before /speccraft:spec:plan, since the described fix shape ('bind the exception... from e in place') will not compile/apply as written against the real code.",
      "BLOCKING: AC5 as written is not implementable against the current validator. validate_verifier_artifact hard-fails on any schema_version mismatch, and live_verifier.py has no _with_defaults machinery to let pre-0033 artifacts still validate. The AC needs to name a concrete mechanism (version-gate per 0026's DATASET_SCHEMA_VERSION pattern, or a _with_defaults map per report.py) or drop the 'legacy artifacts still validate' claim.",
      "Blast-radius gap (both agents, code-verified): explorer_tools.symbols()'s degraded fallback shares the RipgrepEngine seam via a FILE-path scope and is missing from AC4's enumeration. claude-p additionally found this path is already broken today under the default (non-injected) runner (NotADirectoryError), and the two OQ1 fix candidates would change that broken behavior differently -- so this consumer needs explicit pinning, not just a mention.",
      "Internal tension: Invariant 1 requires the fix live at the ONE engine seam, never per-caller, but OQ1/OQ2 keep a wrapper-level re-prefix option open that would not reach Deep search's use of the same engine. This should be resolved toward the engine seam in-spec, not deferred to plan time.",
      "Several AC-precision gaps that weaken the spec's testability: AC1's scope=None/'.' semantics are underdefined relative to process cwd vs repo root; AC2 omits read_span from the tool-contract test without stating why (it only echoes paths rather than discovering them); AC4 pins Deep/Tier-0 only for the unscoped no-op case and doesn't positively pin Deep's new scoped-output shape; AC7's pass condition is model-behavior-contingent with no stated fallback if the live run doesn't happen to exercise it.",
      "The submitted/surviving interface shape (submit_citations' return type, LoopResult's new field(s), and the exact artifact field names / VERIFIER_SCHEMA_VERSION value) is not pinned in the spec text and should be named explicitly so the plan step doesn't have to invent it."
    ],
    "suggestions": [
      "Resolve OQ1 in-spec toward the engine-level (rg-from-root) fix only, and remove the wrapper-level re-prefix option from consideration, since it conflicts with Invariant 1 and would not fix Deep search.",
      "Add explorer_tools.symbols()'s degraded fallback to AC4's enumerated + pinned consumer list, including its current (default-runner) broken behavior and what the fix changes it to.",
      "Correct the fold-in DECIDED section's description of run_verified_case's exception handling to match the actual code (exception is bound but discarded, and the raise is outside the except block), and restate the fix as either capturing the cause before leaving the except block or restructuring the raise to be inside it.",
      "Scope AC5's legacy-artifact validation to a concrete mechanism (0026-style version gate or report.py-style _with_defaults map) rather than an unqualified 'legacy artifacts still validate' claim.",
      "Name the submit_citations return shape and the new LoopResult/artifact field names explicitly (codex's citations_submitted / citations_surviving under VERIFIER_SCHEMA_VERSION=\"0033/1\" is a reasonable concrete proposal), and assert no other existing caller of submit_citations breaks under the new shape.",
      "Pin AC1's scope=None/'.' semantics at a named seam and decide whether None should mean 'repo root'; add read_span to AC2 with echoes-input semantics or explicitly exclude it with rationale; extend AC4 to positively pin Deep's new scoped-output shape, not just the unscoped no-op; add an AC7 fallback per the 0023 input-validity-precondition convention (record not-exercised if the live model never greps scoped, and rely on AC3's hermetic fixture for the actual proof).",
      "Add the repo-root scope case (matching Tier-0's actual production call pattern) to AC4/AC1's regression pins, not just None and '.'."
    ],
    "guardrail_violations": [],
    "convention_violations": [
      {
        "rule": "additive-fields-with-centralized-defaults",
        "location": "AC5",
        "raised_by": "claude-p"
      },
      {
        "rule": "one-bounded-rg-source-of-truth",
        "location": "Open Questions 1 and 2",
        "raised_by": "claude-p"
      },
      {
        "rule": "blast-radius enumeration completeness",
        "location": "Invariant 1 / AC4",
        "raised_by": "claude-p and codex (independently)"
      }
    ]
  },
  "recommended_next_step": "Do not proceed to /speccraft:spec:plan yet, but this does not require a full re-review round -- the quorum (1 approve-with-comments, from codex) is technically met, and claude-p's findings are targeted, code-verified wording/AC-precision corrections rather than scope changes. Apply these edits directly, mirroring the 0032 review flow (spec author applies + marks reviewed without re-review): (1) correct the fold-in DECIDED section's description of run_verified_case's exception handling to match the real code (exception IS bound as `e` but discarded; the raise is OUTSIDE the except block) and restate the fix accordingly; (2) scope AC5's 'legacy artifacts still validate' claim to a concrete mechanism (0026-style version gate or a report.py-style _with_defaults map); (3) add explorer_tools.symbols()'s degraded fallback (FILE-path scope call into the shared engine) to AC4's enumerated + pinned blast-radius list, including its current default-runner broken behavior; (4) resolve OQ1 in-spec toward the engine-level (rg-from-root) fix only, removing the wrapper-level re-prefix option that conflicts with Invariant 1; (5) name the submit_citations/LoopResult/artifact field shapes explicitly (e.g. citations_submitted / citations_surviving, VERIFIER_SCHEMA_VERSION=\"0033/1\"); (6) pin AC1's scope=None/'.' semantics at a named seam plus add the repo-root scope case (Tier-0's actual production pattern); (7) add read_span to AC2 with echoes-input semantics or exclude it with stated rationale; (8) extend AC4 to positively pin Deep search's new scoped-output shape (not just the unscoped no-op), and add an AC7 fallback for the case where the live model run doesn't happen to exercise a scoped-grep citation."
}
