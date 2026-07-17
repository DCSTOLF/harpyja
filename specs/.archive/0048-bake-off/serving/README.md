# Greedy serving — the bake-off's determinism precondition

The spec's replay probe requires the served models to be **reproducible** (a single
draw stands in for a stochastic one — the 0046 lesson). Validated empirically: the
default (non-greedy) `qwen3:14b` gave `empty` then `right-file-wrong-span` on two runs
of the same case (REPLAY-FAIL); the greedy variant (`temperature 0`) reproduced
**identically** — same bucket, same submitted-count, same tool-count (REPRODUCIBLE).
So the variance was pure sampling, and greedy serving is the fix.

The explorer's outbound params are byte-pinned to `{max_tokens: 2048}` (0034/0038), so
temperature CANNOT be injected per-request — greedy must be a **server-side default**.

## Two adoption paths (operator's choice — NOT applied automatically)

**A. Greedy variant tags (non-destructive, recommended for validation).** Build separate
`*-greedy` tags and point a validation run at them:

```bash
ollama create qwen3-14b-greedy  -f Modelfile.qwen3-14b
ollama create qwen3-8b-greedy   -f Modelfile.qwen3-8b
ollama create qwen3.5-4b-greedy -f Modelfile.qwen3.5-4b
```

Using variant names means the frozen `BakeoffConfig.model_tags` must be re-frozen to the
greedy tags (a small config re-freeze + rationale — the reconciled-freeze rule).

**B. Recreate the base tags greedy (no config change, but MUTATES the shared tags).**
`ollama create qwen3:14b -f Modelfile.qwen3-14b` overwrites the tag in place, so the frozen
config's `qwen3:14b` serves greedy with no name change. This changes the tag's behavior for
**everything** on the box that uses it — destructive to the shared environment; do it only
if you own those tags and want them greedy globally.

Either way, greedy is a **serving precondition** (like "the tag must be served"), verified
by the replay probe at preflight — not a SUT change. Re-run the formal 3-case×2 replay after
switching before trusting the bake-off's single-draw discordance.
