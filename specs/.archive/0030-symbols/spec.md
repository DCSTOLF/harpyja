---
id: "0030"
title: Tier-0 symbols as a callable explorer tool (the pull affordance for span precision)
status: closed
started_at_sha: dd193a1
created: 2026-07-07
---

# Spec 0030: Tier-0 symbols as a callable explorer tool

## Why

0029 proved the harness drives a coherent model end-to-end cleanly (14B: no degrade, no runaway, parallel calls handled). The two live cases were both "close but not exact" — django was RIGHT_FILE_WRONG_SPAN (correct file, missed span), astropy WRONG_FILE. The right-file-wrong-span case is exactly the failure a symbol tool targets: a model that has navigated to the correct file but is guessing line numbers instead of asking "what symbols are here and at what spans." Harpyja is memory-boxed to ~16B, so tooling — not model scale — is the primary lever for capability; this tool buys span-localization capability at zero added model size. This is the staged follow-up deferred since 0024 (minimal-tools baseline first, symbol tool as a MEASURED second round), now justified by live signal. It must land BEFORE the model bake-off so the bake-off ranks models through the FINAL tool suite, not one missing its span-precision tool.

**Ref:** 0024 (explorer loop + the deferred symbol-tool staging), Tier-0 symbols/ (existing tree-sitter engine + symbols(path), 9 languages, graceful ripgrep fallback), 0027 (exact-tool-count convention, push→pull), 0029 (the live right-file-wrong-span signal), operator-run-findings.md.

## What

Add a `symbols` explorer tool wrapping Tier-0's **file-local symbol index** (matching `deep/host_tools.py::symbols(path)` — the pattern that filters pre-extracted `SymbolRecord` rows by path, NOT cross-file name resolution via `SymbolEngine.search()`): input a repo-relative file path, output the file's symbols with kind + line span (the existing CodeSpan shape), bounded/clamped, repo-confined.

- Wire it into the explorer loop's tool suite alongside the existing four; it participates in parallel tool_call handling (0029) like any other tool. The integration requires threading `symbol_records` (and possibly `manifest`) into `build_explorer_tools(repo_path, settings, search_engine)` as a known integration point.
- **MEASURE THE LIFT (the point of the spec):** re-run the SAME two 0029 cases (astropy-12907, django-12774) on the SAME 14B, WITH the symbols tool available, and report the before/after bucket delta via a durable JSON artifact (see AC5). 0029 baseline: astropy=WRONG_FILE, django=RIGHT_FILE_WRONG_SPAN. The hypothesis this spec tests: symbols lifts django RIGHT_FILE_WRONG_SPAN → CORRECT (model in the right file resolves the span via symbols).

## Invariants

### Invariant 1: Reuse Tier-0, do NOT add a second parser
The tool exposes the EXISTING Tier-0 tree-sitter symbol index (symbols(path)) as a callable, on-demand explorer tool. One parsing source of truth. No new parsing path, no semantic/AST resolution — CST/tree-sitter definitions-and-spans only, matching Tier-0's existing capability and its graceful degradation to ripgrep on parse failure.

### Invariant 2: Scope = symbols-and-spans in a given file, NOT a call graph
The tool answers "what symbols (functions/methods/classes/types/etc.) are defined in THIS file and at what line ranges." It does NOT do cross-file reference/caller resolution (the deferred semantic/graph tier). Do not let it creep toward name resolution.

### Invariant 3: Pull, not push; exact-tool-count reconciled
This is on-demand — the model calls it when it wants a file's symbols; it is NOT eager injection. The suite goes 4→5 {grep,glob,read_span,ls,symbols}; amend the exact-tool-count convention 4→5 in-lockstep with both hard-count tests (the same reconciliation 0027 did 3→4), with rationale. No eager context returns (push→pull holds).

### Invariant 4: Untrusted-caller boundary
The model is an untrusted caller — the symbols tool is read-only, repo-confined, output-clamped (a large file's symbol list must not flood context past truncation policy), and degrades to ripgrep (Tier-0's existing fallback) on parse failure, surfaced as a normal tool result, never a crash.

## Acceptance Criteria

1. **[unit] Tier-0 wrapper, no new parser, path-normalized:** `symbols` tool wraps the existing Tier-0 symbols(path) engine (no new parser); returns kind+span CodeSpans for a known multi-symbol fixture across ≥2 of the 9 languages. Input file paths are **normalized (resolved)** before lookup to prevent collisions on equivalent-but-differently-spelled paths (e.g., `pkg/../pkg/file.py` vs. `pkg/file.py`). A test covers path-normalization edge cases. Repo-confinement check is enforced **after** path resolution.

2. **[unit] Read-only, repo-confined, output-clamped (NEW SETTING):** Out-of-repo paths (post-resolution) are rejected. Output is clamped per a **new `Settings.scout_symbols_max_entries` field** (following the `scout_glob_max_paths` / `scout_ls_max_entries` naming pattern for navigation-tool output clamps; additive-last, drift-guarded). A large symbol list is clamped per tool budget (no context flood) — same boundary enforcement as the other four tools. This is **new work**, not inherited from existing tool clamps.

3. **[unit] Graceful degradation, visible provenance:** A file that **failed parsing at index-build time** falls back to ripgrep (Tier-0's existing fallback). Parse-failure provenance is recorded in **[choose one: `manifest.degraded_paths` OR a `SymbolRecord.fallback_source` field]** (implementation decision during planning). When the explorer calls `symbols(path)` on a degraded file, the tool returns the **ripgrep result + a visible `degraded: true` marker** in the tool output (not a silent swap). Fallback is recorded (degraded set / provenance), never a crash.

4. **[unit] Exact-tool-count convention amended 4→5 IN LOCKSTEP:** Both changes committed together (single commit with clear rationale): (a) Edit `.speccraft/conventions.md` to record the 4→5 change with rationale ("Tier-0 file-local symbol localization, measured on 0029 baseline cases"); (b) Update ALL hard-count tests (specific files/test markers identified during planning, e.g., `tests/t_scout_toolcount.py::test_exact_tools_count`). The new tool participates in parallel tool_call handling (0029) correctly (answered in emitted order, no unanswered call).

5. **[integration] LIFT MEASUREMENT (the deliverable) — DURABLE JSON REPORT:** astropy-12907 AND django-12774 re-run on the 14B WITH symbols available. **Success criterion (self-contained):** django RIGHT_FILE_WRONG_SPAN → CORRECT (the hypothesis this tool targets). astropy WRONG_FILE → WRONG_FILE is **EXPECTED and is NOT a failure** — the tool is file-local only; it cannot fix wrong-FILE navigation (a separate problem). Any **degrade** across either case ⇒ harness failure, not tool failure. Lift report is a **durable, provenance-complete JSON artifact** (not prose-only): model tag, endpoint/loopback proof, settings overrides, case IDs, per-case bucket (before/after outcome using 0029 labels: WRONG_FILE / RIGHT_FILE_WRONG_SPAN / CORRECT), harness degrade status (none expected; AC8-equivalent holds with 5th tool). Report recorded per spec 0026's measurement-report schema pattern.

6. **[doc] Honest lift record — N=2 is signal, not proof:** Record the measured outcome directly. If django lifts (RIGHT_FILE_WRONG_SPAN → CORRECT), the tool proved its worth on the exact case it targets. If django does NOT lift, or astropy stays WRONG_FILE (expected, per AC5), or either case degrades, record that too — do not overfit the tool to these two cases. N=2 is signal, not proof; the value is in honest measurement and enabling future bake-off ranking.

## Out of Scope

- The model bake-off (this unblocks it, ranking through the now-complete suite)
- Cross-file reference/caller resolution (the deferred semantic/graph tier — symbols is file-local only)
- The representative eval set (built after this, run through the final 5-tool suite)
- A sixth tool
- Eager context
- Any model/gateway/generation-knob change (0028/0029 done)

## Open Questions

(Resolved by AC1–AC5 and the spec text above; no remaining open questions at the spec stage.)

---

**Key insight for review:**

AC5's lift-measurement is the entire spec — this is the "measured second round" the staging plan promised, not "add tool, assume it helps." You already have the 0029 baseline (astropy=wrong-file, django=right-file-wrong-span), so the before/after is cheap and honest: the tool justifies itself on the django case or it doesn't, and either result is recorded. Don't let it ship on the theory that symbols help.

OQ2 is the sharp one and it's the honesty guard. astropy is wrong-file at baseline — a symbol tool operates within a file, so it structurally cannot fix wrong-file navigation. That makes astropy a natural control: if django lifts (right-file→correct) but astropy doesn't (still wrong-file), that's the tool working exactly as designed — it fixes span precision, not file navigation.
