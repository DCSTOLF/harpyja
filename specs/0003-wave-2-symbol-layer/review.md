---
spec: "0003"
title: "Wave 2 — Symbol layer (tree-sitter, Python + Go)"
revision: 3
round: 4
reviewers: [codex, claude-p]
quorum: 1
verdict: approve-with-comments
status: reviewed
date: 2026-06-26
---

# Cross-model review — 0003 (revision 3, fourth round)

**Verdict: APPROVED (with comments). Quorum met. Spec advances to `reviewed`.**

No guardrail violations. No convention violations. Both agents independently stress-tested D15 corruption-recovery and found it correct by construction. All remaining comments are non-blocking fixture-tightening clarifications; they do not alter the design and require no re-review round.

---

## Trajectory

Four rounds strictly narrowed the review surface:

- **Round 0** — broad under-specification across degradation, identity, and integrity.
- **Round 1** — two new structural holes surfaced (per-file degraded persistence; engine identity scope).
- **Round 2** — single remaining area (D15 corruption recovery) plus two precision gaps.
- **Round 3 (this round)** — fixture clarifications only; D15 now correct by construction; both agents independently validated the adversarial cases (clean-truncation, records-first/meta-last crash residue, in-line bit flip, meta corruption).

---

## codex

**Verdict:** approve-with-comments

Concerns:
- D15/D17 do not define how `engine_identity` represents a pinned grammar package that is absent or fails to load. The spec requires grammar-unavailable to degrade gracefully, and says `engine_identity` includes each grammar's version — but an absent package has no version unless a stable sentinel is specified. Without a sentinel, degraded runs cannot write or validate `symbols.meta.json` reproducibly.

Suggestions:
- Use a deterministic per-grammar sentinel in `engine_identity` for the absent/load-failed case — e.g. `tree-sitter-python: missing` or `load-error:<abi-code>` — so degraded runs still produce a byte-reproducible, validatable sidecar.

Discussion: Round-3 fixes are sound and implementation-ready. D15 is materially stronger: `record_count` + `sha256` over exact bytes closes both the clean newline-truncation case and the records-first/meta-last crash residue; write order is correct; the sidecar is deterministic; O(records) validation is accepted. D4 own-region rule is testable and correctly resolves the class-with-broken-method case without suppressing clean siblings. D18 correctly mirrors D6 (total-in-index). The only remaining gap is the missing/load-failed grammar identity representation — a localized, easy spec-text fix that does not undermine the design.

---

## claude-p

**Verdict:** approve-with-comments

Concerns:
- D4 defines the own-region as "the definition node's span EXCLUDING the subtrees of any nested definitions," but "nested definitions" is not pinned. For a class, it means its extracted methods (AC4-iv). For a method containing a broken function-local `def` (not extracted, out of scope), it is unstated whether that local def's subtree is excluded (method emitted, error tolerated) or not (method skipped). Both outcomes are defensible; they produce opposite records; no AC constrains the choice. One sentence clarifying that "nested definitions" means any nested definition syntactic form, extracted or not, makes AC4 reproducible.
- D10c describes method addressing as "ordered adjacent `<id><sep><id>` pair within a segment" but does not say how a 3+ chain (`Foo.bar.baz`) is handled — all adjacent pairs, only the first, or reject. The case is degenerate given that `parent` is immediate-only (D3), but a fixture author cannot write the AC10 assertion without the explicit rule.

Suggestions:
- Make the absent-grammar → installed-grammar recovery path explicit. Installing a previously-absent grammar changes `engine_identity`, which fires D15 full rebuild, which clears any stale `grammar-missing` flags persisted under D18. This interaction is the mechanism that prevents D18 from re-surfacing a stale grammar-missing flag for an on-disk-unchanged file whose grammar is now available. The chain is derivable but load-bearing; state it in D15/D18 and add a corresponding AC (mirror AC8 for the absent→present direction).
- D9 and D15 say "atomic rename"; project conventions (Wave-1 R4/R8) mandate `os.replace` (same-dir, cross-platform; Windows `rename` fails if the destination exists). Use `os.replace` literally.
- Keep AC5 "zero parse calls" distinct from "zero file reads." The no-reparse path still performs a full O(records) scan of `symbols.jsonl` to recompute the digest. AC5 must not be read as implying zero I/O on the incremental path.

Discussion: Revision 3 is sound and implementation-ready. D15 is now correct by construction, not by assumption. Adversarial cases checked: in-line bit flip caught by digest; meta corruption triggers rebuild; interrupted rename leaves whole-old or whole-new. The two-file commit is deliberately not jointly atomic — the digest is engineered to detect the only inconsistent intermediate state. This is a clean design, not a workaround. D4 fix is honest. D18 mirrors D6. Exact-only plus segment-split is the right call. All guardrails respected throughout. Comments are fixture-tightening clarifications, not blockers.

---

## Synthesis

The two agents agree on the overall shape: the spec is implementation-ready and the D15 corruption-recovery area is now correct by construction. The concerns are non-overlapping and additive — together they cover every open edge case.

**Points of agreement across both agents:**
- D15/D17: `engine_identity` needs a sentinel for absent or load-failed grammars (both agents; codex named it directly, claude-p noted the recovery interaction that depends on it).
- `os.replace` vs "atomic rename" wording (claude-p; consistent with Wave-1 precedent both agents know).

**Points from one agent only (all non-blocking):**
- D4 "nested definitions" referent for non-extracted local defs (claude-p).
- D10c 3+ chain handling rule (claude-p).
- Absent→present grammar recovery path made explicit with an AC (claude-p).
- AC5 "zero parse calls" vs "zero file reads" distinction (claude-p).

---

## Non-blocking clarifications to fold in (checklist)

These are editorial tightening items only. No re-review round required.

1. **engine_identity absent-grammar sentinel** (D15, D17) — both agents. Define a deterministic entry per grammar when the package is absent or fails to load, e.g. `tree-sitter-python: missing` or `load-error:<abi-code>`, so degraded runs write a reproducible, validatable sidecar.

2. **D4 "nested definitions" referent** (D4, AC4) — claude-p. Clarify that "nested definitions" means any nested definition syntactic form, extracted or not. Consequence: a method containing a broken function-local `def` is emitted (method record written) with the local def's subtree excluded from the own-region check, error tolerated.

3. **D10c 3+ chain rule** (D10c, AC10) — claude-p. State that a dotted chain of 3+ identifiers (`Foo.bar.baz`) is resolved by evaluating every adjacent pair — `(Foo, bar)` and `(bar, baz)` — so fixture authors can write a deterministic AC10 assertion.

4. **Absent→present grammar recovery path** (D15, D18) — claude-p. Make explicit that installing a previously-absent grammar changes `engine_identity`, which triggers D15 full rebuild, which clears stale `grammar-missing` flags in D18. Add a corresponding AC (mirror of AC8 for the absent→present direction).

5. **`os.replace` literal wording** (D9, D15) — claude-p. Replace every instance of "atomic rename" with `os.replace` (same-dir, cross-platform; matches Wave-1 R4/R8 convention).

6. **AC5 scope** (AC5, D15) — claude-p. Distinguish "zero parse calls" (true on the no-reparse path) from "zero file reads" (false — the digest scan reads `symbols.jsonl` in full). AC5 must state what is and is not zero.

---

## Action

Status: `reviewed`. Fold the six clarifications above as editorial tightening directly into the spec (no re-review round — all are non-blocking, reviewer-requested fixture-tightening that do not alter the design). Once folded, proceed with `/speccraft:spec:plan`.
