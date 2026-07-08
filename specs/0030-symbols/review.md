# Review: Spec 0030 (Tier-0 symbols as a callable explorer tool)

**Date:** 2026-07-07  
**Verdict:** `approve-with-comments` (all design-level checks passed; precision/naming clarifications incorporated)  
**Reviewers:** codex (2× — initial review, re-review post-edits)  
**Quorum:** Met (approve-with-comments)

---

## Summary

Both reviewers endorse the **direction and scope** of spec 0030: file-local symbol lookup (no cross-file resolution), pull-not-push (on-demand tool), reuse of Tier-0's existing parser, and the core hypothesis (astropy as a structural control, django as the lift-measurement target). No guardrail violations were flagged.

The requested changes are **precision/completeness clarifications** to prevent implementer confusion, not a structural rework. The spec's strongest element is AC5's lift-measurement design — both agents endorse the approach and the honesty guard (AC6).

---

## Convergent Findings (highest confidence — both agents independently raised these)

### 1. Seam ambiguity: which `symbols(path)` are you wrapping?

**Finding:** The spec says "wrap Tier-0's `symbols(path)`," but the codebase contains **two related things with overlapping names:**
- `SymbolEngine.search()` in `harpyja/symbols/symbol_locator.py` — a pattern/name-token **matcher** across the repo
- `symbols(path)` in `harpyja/deep/host_tools.py` — a flat linear **filter** over pre-extracted `SymbolRecord` rows by exact path match

These answer different questions: "where *is* symbol X defined (any file)" vs. "what's defined *in this file*."

**Action:** Spec should explicitly name that the explorer tool mirrors the **latter** pattern (`deep/host_tools.py::symbols(path)`'s `SymbolRecord`-filter), not the former. This prevents an implementer from accidentally building against `SymbolEngine.search()` and creating a second, subtly-different code path.

**AC mapping:** Relates to AC1 (Tier-0 wrapper clarity) and Invariant 2 (file-local scope).

---

### 2. Output-clamp is NOT free reuse — it's a new `Settings` field

**Finding:** The spec says output-clamping comes from "reuse Tier-0," but the existing `deep/host_tools.py::symbols(path)` has **no clamp at all** (returns unbounded). AC2's requirement to clamp (to prevent context flood) therefore requires introducing a **new `Settings` field**, following the established pattern (`scout_glob_max_paths`, `scout_ls_max_entries`, etc.).

**Action:** Spec should state plainly: "introduce a new `Settings.explorer_symbols_max_entries` field (or similar) to bound the output, following the naming convention for `scout_*` tool limits." Don't imply the clamp is inherited; it's new work.

**AC mapping:** AC2 (output-clamped) — current text glosses over the implementation cost.

---

### 3. AC4 under-specifies the convention reconciliation

**Finding:** AC4 says "both hard-count tests updated," but per spec 0027's established precedent (recorded in `.speccraft/conventions.md`), "a deliberate change to an exact-count guard is reconciled in **one change** — the convention text **AND** every hard-count test move together, **each with a rationale.**"

AC4 as written names only the tests, not the `.speccraft/conventions.md` prose edit that must accompany them.

**Action:** Tighten AC4 to explicitly require both:
1. Amend `.speccraft/conventions.md` to record the 4→5 change and its rationale (Tier-0 symbol localization, measured on 0029 baseline cases).
2. Update every hard-count test in the suite (naming which tests, `@pytest.mark.`-tagged for easy discovery).

**AC mapping:** AC4 (exact-tool-count convention amended 4→5).

---

### 4. AC3 (graceful degradation) and AC5 (lift measurement) gaps

#### AC3 — Where is parse-failure provenance surfaced?

**Finding:** AC3 says "a parse-failure file falls back to ripgrep... returned as a normal tool result." But the actual parse failure happens at **index build time** (when Tier-0 walks the repo), not when the explorer **calls** `symbols(path)`. The spec should clarify:
- Where is the "degraded set" stored / surfaced during index build?
- When the explorer calls `symbols(path)` on a file that was degraded at build, what does the tool return — a default, a provenance marker, or something else?

**Action:** Name the degraded-provenance surface (e.g., `manifest.degraded_paths` or a field on `SymbolRecord`). Make clear that the call-time behavior (what the explorer sees) is predictable.

#### AC5 — Make the asymmetric-outcome rule self-contained

**Finding:** AC5 says "compare to the 0029 baseline" but doesn't spell out the success condition *in the spec itself*. The asymmetric-outcome rule (degrade on both cases = spec fails; clean wrong-file + django-lifts = success; astropy stays wrong-file = expected) is currently scattered across the spec (Invariants, AC6, "Key insight for review" text).

**Action:** 
1. State in AC5 itself: "Success is defined as: django RIGHT_FILE_WRONG_SPAN → CORRECT (the hypothesis this tool targets). astropy WRONG_FILE → WRONG_FILE is expected and is NOT a failure (the tool cannot fix file-navigation, only span-precision within a file). Any degrade across either case is a harness failure, not a tool failure."
2. Require the lift report to be a **durable, provenance-complete artifact**, not prose-only (codex's addition): model tag, endpoint/loopback proof, settings overrides, case IDs, before/after buckets, degrade status. Consistent with the repo's established "measurement report is a pinned/loud schema" convention (see spec 0026).

**AC mapping:** AC5 (integration lift measurement) and AC6 (honest lift record).

---

### 5. Path normalization: confined-path risk

**Finding (codex):** The Deep precedent's exact string comparison (`r.path == path`) could false-negative on equivalent-but-differently-spelled confined paths — e.g., `pkg/../pkg/file.py` vs. `pkg/file.py`. The spec should require path normalization (canonicalization via `Path.resolve()` or equivalent) as part of the tool's input validation.

**Action:** Add a note to AC1 or AC2: "Path input is normalized (resolved) before lookup; the lookup is performed on the canonical path. A test is included for path-equivalence edge cases (e.g., `pkg/../pkg/file.py` → `pkg/file.py`)."

---

## Agent-Specific Additional Points

### codex

- **Integration surface (AC3 clarity):** Clarify where parse-failure/degraded provenance is stored (e.g., is it a field on `SymbolRecord`, a separate `.degraded` map in the manifest, or plumbed through `search_engine`?).
- **Path normalization test requirement:** AC1 or AC2 should require a test for path-equivalence edge cases.
- **Durable lift-report schema (AC5):** Lift report should be a pinned artifact (JSON schema, not prose), consistent with spec 0026's "measurement report" pattern.

### claude-p

- **Wiring integration point (AC4/What):** `build_explorer_tools(repo_path, settings, search_engine)` will need `symbol_records` (and possibly `manifest`) threaded in. The spec should name this as a known integration point ("no blast radius" is not the same as "doesn't exist").
- **AC8-style asymmetric-outcome rule (AC5):** Spell out self-contained (don't require a cross-reference to spec 0029). Example phrasing: "Degrade on either case ⇒ harness failure. Clean WRONG_FILE on astropy ⇒ expected (tool is file-local). Clean with django lift ⇒ tool proved its hypothesis."
- **Deep's own `symbols()` consistency (non-blocking):** If clamping is added to the explorer tool, consider retroactively adding the same clamp to Deep's `symbols()` for consistency (nice-to-have, not blocking).

---

## Design Strength: AC5 Lift Measurement

Both reviewers endorse the core hypothesis and measurement design:
- **Hypothesis clarity:** "right-file-wrong-span → correct" is a specific, measurable lift.
- **Control design:** astropy as a structural control (file-local tool cannot fix wrong-FILE navigation) is sound.
- **Honesty guard (AC6):** pre-empting overfitting ("N=2 is signal, not proof; do not overfit") is exceptionally strong.

This is the spec's best section. Codex emphasizes that the lift report should be durable/provenance-complete (not prose-only).

---

## Guardrails & Conventions

No guardrail violations flagged by either reviewer.

Convention alignment checks:
- **exact-tool-count convention (0027):** AC4 needs tightening (see Finding #3 above).
- **measurement report schema (0026):** AC5 needs AC5 to require a durable artifact, not prose (see Finding #4 above).
- **integration-point clarity:** AC naming in wiring (claude-p's note) follows the repo's pattern of making integration surfaces explicit.

---

## Recommended Edits to spec.md

Before moving to `/speccraft:spec:plan`, make these revisions:

1. **What section — name the target pattern explicitly:**
   ```
   Add a `symbols` explorer tool wrapping Tier-0's *file-local* symbol index 
   (matching the `deep/host_tools.py::symbols(path)` pattern of filtering 
   pre-extracted SymbolRecord rows by path, NOT cross-file name resolution via 
   SymbolEngine.search()).
   ```

2. **AC1 — add path normalization:**
   ```
   AC1: [unit] Tier-0 wrapper, no new parser, path-normalized:
   - symbols() tool wraps the existing Tier-0 symbols(path) engine
   - Returns kind+span CodeSpans for a known multi-symbol fixture across ≥2 of 9 languages
   - Input paths are normalized (resolved) before lookup; test includes path-equivalence 
     edge cases (pkg/../pkg/file.py ≠ pkg/file.py collision).
   ```

3. **AC2 — make the clamp cost explicit:**
   ```
   AC2: [unit] Read-only, repo-confined, output-clamped (NEW SETTING):
   - Out-of-repo paths rejected; SymbolRecords are clamped per a new 
     Settings.explorer_symbols_max_entries field (following scout_glob_max_paths / 
     scout_ls_max_entries naming pattern)
   - A large symbol list is clamped per tool budget (no context flood)
   - Same boundary enforcement as the other four tools
   ```

4. **AC3 — clarify parse-failure provenance:**
   ```
   AC3: [unit] Graceful degradation, provenance-tracked:
   - A file that failed parsing at index-build time falls back to ripgrep (Tier-0's existing fallback)
   - The degraded set is recorded in [SPECIFY: manifest.degraded_paths? SymbolRecord.fallback_source?]
   - When explorer calls symbols(path) on a degraded file, [SPECIFY: returns what? A marker? A default?]
   - Fallback is recorded in tool output provenance, never a crash
   ```

5. **AC4 — require convention edit in the commit:**
   ```
   AC4: [unit] Exact-tool-count convention amended 4→5 IN LOCKSTEP:
   - Edit .speccraft/conventions.md to record the 4→5 change with rationale 
     ("Tier-0 symbol localization, measured on 0029 baseline cases")
   - Update ALL hard-count tests (list by file/marker: [tests/t_scout_toolcount.py::test_exact_tools_count, ...])
   - Both changes committed together; each has a rationale in the commit message
   ```

6. **AC5 — make outcome rule self-contained + require durable report:**
   ```
   AC5: [integration] LIFT MEASUREMENT (the deliverable) — DURABLE ARTIFACT:
   - astropy-12907 AND django-12774 re-run on the 14B WITH symbols available
   - Success criterion (self-contained): django RIGHT_FILE_WRONG_SPAN → CORRECT 
     (the hypothesis this tool targets). astropy WRONG_FILE → WRONG_FILE is EXPECTED 
     and is NOT a failure (the tool is file-local only; it cannot fix wrong-FILE navigation).
   - Any degrade across either case ⇒ harness failure, not tool failure.
   - Lift report is a durable, provenance-complete artifact (not prose-only):
     - Model tag, endpoint/loopback proof, settings overrides, case IDs
     - Per-case bucket: before/after outcome (using 0029 WRONG_FILE / RIGHT_FILE_WRONG_SPAN / CORRECT labels)
     - Harness degrade status (none expected, AC8-equivalent holds with 5th tool)
     - Recorded as a pinned schema (JSON or structured), following spec 0026's measurement-report pattern
   ```

7. **What section — name the integration point:**
   ```
   ... Wire it into the explorer loop's tool suite alongside the existing four; 
   it participates in parallel tool_call handling (0029) like any other tool.
   The integration requires threading symbol_records (and possibly manifest) into 
   build_explorer_tools(repo_path, settings, search_engine); the exact signature 
   change is determined during /speccraft:spec:plan.
   ```

---

## Next Step

✓ **Verdict:** `changes-requested` (precision/completeness, not design rejection)  
→ **Next:** Edit `specs/0030-symbols/spec.md` with the revisions above, then re-run `/speccraft:spec:review`.

Once review passes (quorum met with approve or approve-with-comments), run `/speccraft:spec:plan` to turn the spec into TDD steps.
