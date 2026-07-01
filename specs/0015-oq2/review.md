# Review — Spec 0015 "OQ2"

Reviewers: `codex` (codex-cli 0.140.0, gpt-5.5), `claude-p` (local `claude` CLI)
Synthesis: cross-reviewer + orchestrator source-verification

## Round 2 (2026-06-30) — final

| Reviewer | Verdict |
|----------|---------|
| claude-p | **approve-with-comments** |
| codex | changes-requested → **resolved post-review** (see below) |

**Quorum (≥1 approve / approve-with-comments): MET.** Status → `reviewed`.

Both reviewers confirmed all four round-1 load-bearing concerns resolved with no
relitigation. `claude-p` explicitly accepted the source-verified correction on AC4
("genuine measurement over an existing seam, not capability dressed as measurement").

### codex's round-2 blocker — a real bug, fixed

codex (reviewing the post-round-1 text) caught a genuine defect in AC4: the
false-escalation **denominator** clause bundled the reject/escalate condition into
itself, making numerator ≡ denominator (rate tautologically 1.0). Verified against
`harpyja/eval/metrics.py` — codex was right, and the implemented functions already
have the correct shape:

- `gate_false_escalation` (metrics.py:177): denominator = point cases where Scout is
  `_any_primary_overlap`-correct (**independent of gate outcome**); numerator = the
  escalated subset; `None`-with-zero-counts on empty.
- `gate_catch_rate` (metrics.py:161): denominator = point cases where Scout is
  oracle-**wrong**; numerator = the escalated (caught) subset; same null-with-count.

AC4 was rewritten to mirror those exact definitions (distinct numerator/denominator,
both rates' contracts pinned, both null-with-count). This **closes codex's only
blocker** and its `null-with-count` convention note — the change pins the spec to the
instrument as built, so the measurement invariant strengthens.

### claude-p's one comment — folded

AC5's "exactly one `reason`" had no tie-break when multiple null conditions co-hold.
Folded a **predeclared deterministic precedence** into AC5:
`under_n_floor → degraded_dominated → gate_quality_confounded → not_separable`, with
a `[unit]` test pinning it. AC5 is now fully review-hookable.

### Plan-level items (carry to `/speccraft:spec:plan`, not spec blockers)

- **OQ1 (mandatory):** fix K + the `threshold × top_n` grid (or the coarse→refine
  protocol) with a **predeclared** refinement/stopping rule; state whether K is held
  constant across grid points (the `mean(A)−mean(B) > spread(B)` comparator assumes
  comparable per-point spread).
- State the per-grid-point "dominated" comparison baseline explicitly so `dominated`
  isn't silently redefined between the global gate and the per-point recommender
  filter.
- Set the concrete `GATE_CONFOUND_THRESHOLD`, `GATE_RATE_N_FLOOR`, and
  `degraded_dominated` threshold values.

## Round 1 (2026-06-30) — superseded

Both reviewers returned **changes-requested**, converging on the two load-bearing
ACs (4, 5). All eight folded items (oracle pin, explicit denominators, null enum,
air-gap wording, quantified confound threshold, gate-rate sample floor, per-grid
degrade gate, subset pinning). One reviewer disagreement — `claude-p`'s claim that
AC4 needed a new measurement seam — was **source-verified false**: the harness
already captures pre-gate Scout spans on escalated cases (`runner.py:182-184`),
scores them via `_any_primary_overlap` (`metrics.py:169,185`), and
`gate_false_escalation()` already exists. AC4 is genuine measurement.

## Action recommendation

**Reviewed — proceed to `/speccraft:spec:plan`.** Both load-bearing ACs (4, 5) are
now pinned tightly enough to implement and review-hook. The plan must resolve OQ1
(K/grid + predeclared refinement rule) and set the three numeric thresholds before
the integration run.
