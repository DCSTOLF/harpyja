# History

Append-only. Newest first.

## 2026-06-26 — Wave 0 foundations shipped

**Spec:** specs/0001-wave-0-foundations/
**Decision:** Ship the agent↔server skeleton with a stub-first MCP contract and
four foundational choices: (1) the air-gap is enforced in exactly one helper,
`gateway.assert_local`, reused for both the outbound endpoint and — via
`DEFAULT_HTTP_HOST=127.0.0.1` plus the CLI `--allow-remote-bind` opt-out — the
inbound HTTP listener; loopback = `127.0.0.0/8` / `::1` / literal `localhost`.
(2) `harpyja_locate` is registered and returns a schema-valid empty
`LocateResult` (`confidence="low"`) per SPEC §2.1 — no retrieval. (3) Config
resolves with precedence defaults < `harpyja.toml` < `HARPYJA_*` env <
per-request override, on a frozen `Settings` dataclass. (4) Tests live next to
the package under test (`test_*.py`); no top-level `tests/` root.
**Why:** Pin the riskiest integration surface (MCP registration, which differs
between Claude Code and Codex) early and make later waves purely additive; keep
the air-gap guarantee auditable in one place rather than scattered across layers.
**Consequence:** Wave 1+ adds retrieval behind the existing `harpyja_locate`
contract without touching transport, config, or the air-gap. The inbound bind
default and `assert_local` are the security-load-bearing surfaces to preserve.

## 2026-06-26 — speccraft adopted

**Spec:** specs/0001-speccraft-v1/
**Decision:** Adopt speccraft for spec-first TDD workflow.
**Why:** Establish disciplined spec-first development from day one.
**Consequence:** All future code changes go through `/spec:new`.
