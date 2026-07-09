# Thinking experiment — astropy, think:true + max_tokens=8192 (2026-07-09)

Ad-hoc operator experiment run AFTER the 0033 T1–T15 implementation, on the fixed stack
(repo-relative scoped grep + submit-seam counts live). NOT part of 0033's ACs — recorded
here as reference evidence for the follow-up spec (reasoning observability + think knob)
and for the eval set to validate against. Stack: Ollama `qwen3:14b` @ loopback,
`scout_max_turns=10`, `scout_wall_clock_s=900`, `lm_http_timeout_s=300`. Driver:
`driver.py` (in this directory); full per-turn reasoning logs in the trajectory JSONs.

## API-shape probes (the premise)

1. **Ollama `/api/chat` with `think:true` + tools**: `message.thinking` (2402 chars)
   SEPARATE from empty `content`, well-formed `tool_calls`, `done_reason: stop`. Thinking
   and tool-calling coexist cleanly.
2. **Ollama `/v1/chat/completions` with `think:true` + tools**: honors it —
   `message.reasoning` (2561 chars) separate from content, `finish_reason: tool_calls`.
   Rides the existing `ModelGateway.complete_with_tools` (`**params` → request body).
3. **The load-bearing surprise — `/v1` WITHOUT `think`**: the response STILL carries
   `reasoning` (3949 chars on a trivial prompt). **Thinking is ON BY DEFAULT for
   qwen3:14b on this Ollama.** Every 0031–0033 live run reasoned invisibly: the gateway
   drops the field, and the reasoning consumed the 2048 `explorer_max_tokens` cap unseen
   (840 completion tokens for one trivial tool-call turn). The 0028 thinking-disable
   rationale (unbounded `<think>` in content, contamination risk, llama.cpp-era 16B) is
   obsolete under this API shape — not because thinking can now be enabled, but because
   it was never off in the Ollama/qwen3:14b era and we neither observed nor budgeted it.

## Results (N=2)

| Run | Bucket | Citation (survived) | Tools | Turns | Wall |
|---|---|---|---|---|---|
| 1 | wrong-file | `astropy/modeling/core.py:812` | ls, grep, read_span, submit | 8 | 200.6s |
| 2 | **right-file-wrong-span** | `astropy/modeling/separable.py:66-102` | ls, grep, **symbols**, submit | 7 | 215.0s |

**Run 2 is a double first across all observed astropy runs (~6 baseline: 0031 empty,
0032 found-then-dropped, 0033-T14 wrong-file-survived, honest-empty, etc.):**
- **First right-file outcome.** Navigation: `ls .` → `ls astropy/` → `ls astropy/modeling/`
  (the 0027 push→pull layout walk), spotted `separable.py` in the listing, grepped INSIDE
  it (empty — file-scope grep returns `[]` by wrapper rule), then
  **`symbols("astropy/modeling/separable.py")`** and cited a span from the symbol index.
- **First observed `symbols` invocation ever** — the 0030 hypothesis (file-local symbol
  index buys span precision once the model reaches the right file) observed working
  end-to-end for the first time.
- The cited span `66-102` is `separability_matrix()` — the PUBLIC function that computes
  the matrix. For the natural-language query ("where is the separability matrix
  computed...") this is arguably the humanly-correct localization; the gold span
  (242-248, inside `_cstack`) is the SWE-bench BUG-FIX hunk — a subtly different
  question. The strict oracle scores right-file-wrong-span honestly (gap > window-50);
  the representativeness nuance is the 0026 axis, recorded not re-litigated.

**Thinking mechanics: fully clean.** 15 thinking turns total, ZERO truncation
(`finish_reason: tool_calls` every turn), per-turn reasoning 863–4542 chars all
structurally isolated in `reasoning` (content stayed empty on tool-call turns), per-turn
completion 212–1041 tokens.

## Honest caveats (why this is signal, not a finding)

1. **N=2 vs ~6 baseline.** Baseline: zero right-file ever. This arm: 1/2 + first symbols
   adoption. Suggestive; the eval set's paired A/B is the instrument that decides.
2. **The mechanism is NOT established.** `think:true` ≈ the default (probe 3), and no
   turn exceeded 1041 completion tokens, so the raised cap was never binding either —
   NEITHER knob mechanically explains run 2. It may be stochastic variance the baseline
   would show at higher N. Do not flip any Settings default on this evidence.

## Named follow-ups (for the next spec, not acted on here)

- Surface `reasoning` ADDITIVELY through `ModelGateway.complete_with_tools` (today it is
  generated, dropped, and invisible — how the default-thinking fact stayed hidden since
  0028) and record at least per-turn reasoning LENGTHS in the trajectory record.
- Make `think` an `explorer_*`-scoped knob per the generation-control convention
  (0028 AC2/AC8 pattern), superseding/reconciling `explorer_enable_thinking`
  (whose `chat_template_kwargs` mechanism targets the llama.cpp template era).
- Revisit `explorer_max_tokens=2048` with the now-visible reasoning tax in mind.
- The eval set measures thinking-arm vs default-arm as a paired within-case A/B
  (McNemar over the signal-bearing flips — the 0023/0026 machinery).
