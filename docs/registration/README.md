# Registering Harpyja with a coding agent (Wave 0)

Harpyja speaks MCP over stdio. In Wave 0 it registers a single tool,
`harpyja_locate`, which returns a **schema-valid empty stub** (no retrieval yet):

```json
{ "citations": [], "confidence": "low", "tiers_run": [], "notes": "wave-0 stub: no retrieval" }
```

These recipes are verified by the Wave 0 acceptance criteria AC11 (Claude Code)
and AC12 (Codex). Both are **manual integration checks** — they launch a real
agent, not pytest.

## Claude Code

Copy [`mcp.json`](./mcp.json) into your project as `.mcp.json` (or merge the
`mcpServers.harpyja` block into an existing one), or run:

```bash
claude mcp add harpyja -- uv run harpyja serve --stdio
```

## Codex

Merge [`codex-config.toml`](./codex-config.toml) into `~/.codex/config.toml`.

## Manual verification (AC11 / AC12)

Run these steps **independently** for each agent:

1. **Launch** the agent with the config above. The agent spawns
   `uv run harpyja serve --stdio` as a subprocess.
2. **Handshake** completes — the agent shows no MCP connection error for the
   `harpyja` server.
3. **Tool listed** — `harpyja_locate` appears in the agent's available tools.
4. **Call returns the stub** — invoke `harpyja_locate` (any `query` /
   `repo_path`). The response is the empty `LocateResult` shown above, returned
   cleanly over stdio (no framing corruption from logs — logs go to stderr).

A self-contained, automated version of this round-trip (over a subprocess stdio
session) lives in `harpyja/server/test_stdio_hygiene.py` and runs under the
`integration` marker:

```bash
uv run pytest -m integration
```
