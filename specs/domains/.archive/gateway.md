# Domain requirement archive

Verbatim superseded requirement text demoted from a domain file by spec consolidation. Append-only.

## gateway | spec 0028 | MODIFY
- `ModelGateway.complete_with_tools(messages, tools, *, transport, resolver, **params)` returns `{content, tool_calls}` from `choices[0].message` for tool-calling models (the Scout explorer loop) — the same single outbound abstraction, `assert_local` asserted BEFORE any transport touch, transport injectable exactly like `complete`. (spec 0024)

## gateway | spec 0031 | MODIFY
- `ModelGateway.complete_with_tools(messages, tools, *, transport, resolver, **params)` returns `{content, tool_calls, finish_reason}` for tool-calling models (the Scout explorer loop) — `finish_reason` reads `choices[0].finish_reason` (the CHOICE not the message, `str`-cast, defaulting to the sentinel `"unknown"` when absent), backward-additive over the two prior keys; the same single outbound abstraction, `assert_local` asserted BEFORE any transport touch, transport injectable exactly like `complete`, and `ModelGateway` stays purely param-driven (no `max_tokens` default of its own, so the Deep-tier path is never capped). (specs 0024, 0028)

