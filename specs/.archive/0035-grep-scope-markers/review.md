{
  "spec_id": "0035",
  "spec_title": "grep-scope-markers",
  "reviewed_at": "2026-07-09",
  "reviewers": [
    {
      "agent": "codex",
      "verdict": "approve-with-comments",
      "concerns": [
        "Deep search should be audited for ASYMMETRIC outcomes, not \"the same gap\": file scopes are already engine-supported (post-0033), so there is no file-scope gap to fix on the Deep side; a nonexistent scope likely raises FileNotFoundError at the subprocess cwd instead of silently returning [] -- a different failure shape than grep's, and the spec's \"same gap\" framing undersells it.",
        "OQ1 should resolve toward the wrapper-returned marker, not the 0029-exception route: routing through the existing per-call degrade catch would misclassify a navigation mistake as an execution error and bury the stable identifier inside a generic `tool-call-degraded:execution-error:` prefix.",
        "OQ2 should be promoted from open question to in-scope fix: `ls` has the identical silent-`[]` shape for a nonexistent path and belongs in this spec, not deferred."
      ],
      "suggestions": [
        "State the mechanism in-spec rather than leaving it for plan: marker strings, with `_spans_of` tolerating the non-list value and `session.add` stringifying it -- zero loop changes required.",
        "Split the Deep AC into per-shape outcomes (file-scope: no gap, pinned as already-correct; nonexistent-scope: fixed or excluded-with-rationale) instead of one \"same gap\" clause.",
        "Pin `confine_path`'s non-strict `resolve()` behavior with a fixture, so a future switch to strict resolution can't silently change the contract this spec depends on.",
        "If the explorer's file-scope exclusion is kept as-is, name it explicitly as deliberate policy rather than leaving it implicit."
      ],
      "guardrail_violations": [],
      "convention_violations": [],
      "notes": "Verified independently (ran Python): confine_path does NOT raise on nonexistent in-repo paths; both observed shapes (file scope, nonexistent scope) land on the one is_dir() branch. No violations filed."
    },
    {
      "agent": "claude-p",
      "verdict": "changes-requested",
      "concerns": [
        "THE DESIGN FORK: post-0033 the engine natively searches FILE scopes (parent-dir + filename arg, producing real repo-relative matches) -- grep's `is_dir()` early-return is now a policy choice blocking a strictly better outcome, not a genuine gap. The 0033 astropy run (grepped the RIGHT file twice) would have gotten REAL matches under delegation. The spec hard-commits to a file-scope marker in an invariant plus AC1 without naming the delegation alternative. Recommendation: DELETE the file-scope guard and delegate to the engine; keep the marker ONLY for the nonexistent-scope shape.",
        "CODE-WINS convention violation: Deep does NOT have \"the same gap\" as claimed. File scope is engine-handled on the Deep side (no gap). Nonexistent scope is an UNCAUGHT FileNotFoundError at the subprocess cwd, with no typed catch in `host_tools.search` or `RlmBackend.run` -- a hard-failure guardrail gap, not a silent `[]`. An audit instructed to look for \"the same gap\" (silent-`[]`) would wrongly close this as not-applicable and miss the crash.",
        "OQ1 is effectively already decided by the code: option (b), exception-through-the-0029-degrade-catch, ALSO skips `note_navigation` because the degrade path returns before it runs -- silently defeating loop detection on repeated bad scopes. This eliminates option (b); marker-string (a) or marker-dict (c) are both free of this defect.",
        "AC6's harness piggyback (persistent live-artifact writer) needs its real justification stated explicitly (AC5 consumes it) plus harness-vs-SUT fencing, so the eval-set spec can still claim SUT-byte-frozen; timestamp format and fake-repo/out_dir `TemporaryDirectory` separation are underspecified; the artifact base path must NOT become a `Settings` field (eval-knobs-disjoint convention).",
        "Epistemics: the Why's causal phrasing (\"sent the model into\", \"one affordance away\") leaks N=1 counterfactual claims that the spec's own stated invariant explicitly withholds -- needs rephrasing to observational language.",
        "`ls` on a nonexistent path is verifiably the same fix class as grep's nonexistent-scope shape (confirmed via code read) -- should be committed to in-scope now rather than left as an open question; OQ2 should narrow to only the separate question of ls-on-a-FILE semantics."
      ],
      "suggestions": [
        "Delete the file-scope early-return guard in grep and delegate file scopes to the engine (parent-dir + filename), converging with the Deep side and turning the strongest fixture (the 0033 astropy right-file run) into a positive regression test instead of a marker case.",
        "Reserve the typed marker for the nonexistent-scope shape only.",
        "Resolve OQ1 in-spec toward marker-string/marker-dict (not the 0029-exception route), citing the note_navigation loop-detection defeat as the reason to eliminate the exception route.",
        "Rewrite the Deep AC per-shape: file scope = no gap, pinned as correct by delegation; nonexistent scope = fix the uncaught FileNotFoundError as a graceful-degradation defect (typed catch, marker or equivalent), not merely audited for a silent-[] pattern.",
        "State AC6's justification (AC5 consumption) explicitly and add harness-vs-SUT fencing, timestamp format, and TemporaryDirectory separation; keep the artifact base path out of Settings.",
        "Rephrase Why's causal language to observational framing consistent with the spec's own withheld-causal-claim invariant.",
        "Commit the ls nonexistent-path fix in this spec now; narrow OQ2 to ls-on-a-file semantics only."
      ],
      "guardrail_violations": [
        {
          "rule": "graceful degradation",
          "location": "What / Deep `search` audit clause -- nonexistent-scope shape crashes with an uncaught FileNotFoundError rather than degrading"
        }
      ],
      "convention_violations": [
        {
          "rule": "code-wins",
          "location": "Invariants / \"Deep's `search` host tool is explicitly audited for the same gap\" -- the code shows an asymmetric, not identical, gap"
        }
      ],
      "notes": "All concerns code-verified against the current implementation (grep wrapper's is_dir() branch, confine_path's non-strict resolve, RipgrepEngine file-scope handling post-0033, host_tools.search / RlmBackend.run's lack of a typed FileNotFoundError catch, and the loop's degrade-catch vs note_navigation ordering)."
    }
  ],
  "synthesis": {
    "verdict": "changes-requested",
    "agreement": "Both agents independently confirmed the premise by reading/running the code: confine_path does not raise on nonexistent in-repo paths, and both the file-scope and nonexistent-scope fixtures land on grep's single is_dir() early-return branch today. Both agents converge on OQ1: resolve toward a wrapper-returned marker (marker string or marker-dict), not the 0029 exception-through-degrade-catch route -- codex on classification/prefix-burial grounds, claude-p with the sharper code-verified argument that the exception route also skips note_navigation and silently defeats loop detection on repeated bad scopes. Both agents also converge on ls: the nonexistent-path shape is the identical fix class and belongs in this spec now, narrowing OQ2 to the separate question of ls-on-a-file semantics. Both flag that the spec's \"Deep is audited for the same gap\" framing undersells or misstates what the code actually does; claude-p goes further and identifies the nonexistent-scope shape on the Deep side as a genuinely NEW defect -- an uncaught FileNotFoundError, a hard-failure guardrail gap, not a silent-[] -- filing it as a graceful-degradation violation and a code-wins convention violation (an audit instructed to look for \"the same silent-[] gap\" would wrongly close this as not-applicable). The two agents diverge on the file-scope fork: codex's stance is to keep the marker on file scopes but name the exclusion as deliberate policy if it stays; claude-p's stance, backed by the concrete code evidence that the engine now handles file scopes natively post-0033 (parent-dir + filename, real repo-relative matches), is to delete the file-scope guard entirely and delegate to the engine, reserving the marker for the nonexistent-scope shape only. This synthesis resolves the fork toward DELEGATION: real matches strictly dominate a redirect-to-read_span marker, it converges the grep and Deep sides onto the same policy, it uses engine capability the codebase already has post-0033, and it turns the strongest fixture in the spec's own Why section (the 0033 astropy right-file run) into a positive regression test rather than a marker case. Additional items unique to claude-p -- the AC6 harness-fencing gaps and the epistemic causal-language leak in Why -- are folded into the required edits below as non-blocking precision fixes.",
    "concerns": [
      "BLOCKING (claude-p, code-verified): the file-scope early-return in grep is a policy choice, not a gap -- the engine already handles file scopes natively post-0033 with real repo-relative matches. The spec hard-commits to a file-scope marker in an invariant and AC1 without naming or evaluating the delegation alternative, foreclosing a strictly better outcome that the spec's own headline fixture (the 0033 astropy run) would benefit from.",
      "BLOCKING (claude-p, code-verified) / corroborated (codex, independently verified): Deep's search does NOT have \"the same gap\" as grep. File scope is already engine-handled on the Deep side (no gap at all); nonexistent scope surfaces as an uncaught FileNotFoundError at the subprocess cwd -- a hard-failure crash, not a silent-[] -- a graceful-degradation guardrail violation and a code-wins convention violation as currently worded. An audit told to find \"the same gap\" would wrongly close this.",
      "OQ1 is effectively decided by the code and should be resolved in-spec, not left open: the exception-through-0029-degrade-catch route also bypasses note_navigation (claude-p), defeating loop detection on repeated bad scopes, and separately buries the stable identifier in a generic execution-error prefix (codex). Both agents converge on marker-string/marker-dict as the correct route.",
      "OQ2 (ls) should be promoted to an in-scope fix now rather than left open: both agents independently identify ls's nonexistent-path silent-[] as the same fix class as grep's. Narrow the remaining open question to ls-on-a-file semantics only.",
      "AC6's harness piggyback (persistent live-artifact writer) needs explicit justification (AC5 consumption) and harness-vs-SUT fencing so the eval-set spec's SUT-byte-frozen claim survives; timestamp format, fake-repo/out_dir TemporaryDirectory separation, and keeping the artifact base path out of Settings (eval-knobs-disjoint) are underspecified (claude-p).",
      "Epistemic overreach in Why: causal phrasing (\"sent the model into\", \"one affordance away\") leaks N=1 counterfactual claims the spec's own stated invariant explicitly withholds; needs observational rephrasing (claude-p)."
    ],
    "suggestions": [
      "Resolve the file-scope fork toward DELEGATION: delete grep's is_dir() file-scope early-return guard and let the engine handle file scopes (parent-dir + filename, real matches); reserve the typed marker for the nonexistent-scope shape only. Rewrite Invariant \"tool surface unchanged\" and AC1 accordingly, and reframe the 0033 astropy fixture as a positive delegated-match regression test rather than a marker case.",
      "Rewrite the Deep clause per-shape rather than as one \"same gap\" audit: file scope = no gap, pinned as already-correct via engine delegation; nonexistent scope = fix the uncaught FileNotFoundError as a graceful-degradation defect (typed catch producing the equivalent marker or degrade signal), stated as a newly discovered defect fix, not merely an audit outcome.",
      "Resolve OQ1 in-spec toward the marker-string/marker-dict mechanism (not the 0029 exception-degrade-catch route), citing both the note_navigation loop-detection defeat and the execution-error-prefix misclassification as the reasons the exception route is eliminated. State the mechanism explicitly: `_spans_of` tolerates the non-list marker value, `session.add` stringifies it, zero loop changes required.",
      "Fold ls's nonexistent-path fix into this spec's in-scope work now (same fix class, code-verified by both agents); narrow OQ2 to only the separate question of ls-on-a-file semantics.",
      "Add a `confine_path` non-strict-resolve fixture pinning current behavior, so a future switch to strict resolution can't silently change this spec's contract (codex).",
      "State AC6's justification explicitly (AC5 consumes the persistent-artifact harness), add harness-vs-SUT fencing, name the timestamp format, separate fake-repo/out_dir TemporaryDirectory usage from the persistent-artifact path, and confirm the artifact base path is not a Settings field.",
      "Rephrase Why's causal language (\"sent the model into\", \"one affordance away\") to observational framing consistent with the spec's own withheld-causal-claim invariant."
    ],
    "guardrail_violations": [
      {
        "rule": "graceful degradation",
        "location": "What / Deep `search` audit clause",
        "raised_by": "claude-p"
      }
    ],
    "convention_violations": [
      {
        "rule": "code-wins",
        "location": "Invariants / \"Deep's `search` host tool is explicitly audited for the same gap\"",
        "raised_by": "claude-p"
      }
    ]
  },
  "recommended_next_step": "Do not proceed to /speccraft:spec:plan yet, but this does not require a full re-review round -- apply the following targeted edits (scope-resolving plus wording/AC-precision; the file-scope fork is resolved toward delegation, not left as a choice), then mark reviewed without a full re-round, per the 0032/0033/0034 flow: (1) delete grep's is_dir() file-scope early-return guard and delegate file scopes to the engine (parent-dir + filename, real matches); reserve the typed marker for the nonexistent-scope shape only; update the 'tool surface unchanged' invariant and AC1 to name delegation, and reframe the 0033 astropy fixture as a positive delegated-match regression test; (2) rewrite the Deep clause (Invariants + What + AC4) per-shape: file scope = no gap, pinned correct via engine delegation; nonexistent scope = fix the uncaught FileNotFoundError as a graceful-degradation defect (typed catch + marker/degrade signal), stated as a defect fix, not an audit outcome; (3) resolve OQ1 in-spec toward the marker-string/marker-dict mechanism, citing the note_navigation loop-detection defeat and execution-error-prefix misclassification as why the exception-degrade-catch route is eliminated; state the mechanism (`_spans_of` tolerance, `session.add` stringification, zero loop changes); (4) fold ls's nonexistent-path fix into in-scope AC work now; narrow OQ2 to ls-on-a-file semantics only; (5) add a confine_path non-strict-resolve fixture; (6) state AC6's justification explicitly, add harness-vs-SUT fencing, name the timestamp format, separate TemporaryDirectory fake-repo/out_dir usage from the persistent-artifact path, and confirm the artifact base path stays out of Settings; (7) rephrase Why's causal language to observational framing."
}
