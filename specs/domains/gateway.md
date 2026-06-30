# Gateway domain

Consolidated, current requirements for the Model Gateway and the air-gap
boundary. Each line carries its originating spec(s) as provenance.

- `ModelGateway.assert_local()` passes for `127.0.0.0/8` and `::1` endpoints (or hosts resolving only to those) and rejects any non-loopback endpoint unless `allow_remote` is set, making no network call. (spec 0001)
- The Model Gateway is the single outbound caller — a thin client over a local OpenAI-compatible endpoint (llama.cpp `llama-server` or Ollama) holding the base URL + primary model from `Settings`. (spec 0005)
- `gateway.assert_local` takes an injected resolver (stdlib default, fake in tests), resolves the configured endpoint host to its address set, and asserts every resolved address is loopback via the stdlib `ipaddress` predicate; `localhost` is accepted only because it resolves to loopback. No request is ever sent to a non-loopback address. (spec 0005)
- A configured non-loopback endpoint raises a typed, actionable `NonLoopbackEndpointError`/`AirGapError` naming the offending host — a loud floor case, never a silent skip and never a degrade note. (spec 0005)
