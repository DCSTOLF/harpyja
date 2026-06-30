# FastContext: Programmatic Install & Use (with CLI fallback)

Two install models, same package:

- **`uv tool install .`** (what you already did) → isolated env, exposes the `fastcontext`
  **binary** on PATH. Not importable from your app. Drive via subprocess.
- **`uv add` from git/path** (below) → installs `fastcontext` into **your MCP server's
  own venv**, so `from fastcontext... import ...` works and you call it in-process.

Use Path A (programmatic). If it won't install or import, fall back to Path B (CLI).

---

## Path A — Programmatic (uv add from git)

### Step 1 — Require Python 3.12+ in your project

FastContext requires Python 3.12 or newer. Your MCP project must allow it. In your
`pyproject.toml`:

```toml
[project]
requires-python = ">=3.12"
```

Confirm the venv uv will use is actually 3.12+:

```bash
uv run python --version      # must print 3.12.x or newer
# if not, pin it:
uv python install 3.12
uv venv --python 3.12
```

### Step 2 — Add FastContext as a dependency

From your MCP server project root (the dir with *your* `pyproject.toml`):

```bash
uv add "git+https://github.com/DCSTOLF/fastcontext"
```

There are **no published releases**, so `main` can move. Pin a commit for
reproducibility once it installs cleanly:

```bash
uv add "git+https://github.com/DCSTOLF/fastcontext@<commit-sha>"
```

**Already have the repo cloned locally** (you do — you installed the CLI from it)?
Install from the path instead; this sidesteps any git/submodule fetch issues:

```bash
uv add /absolute/path/to/fastcontext
# or editable, if you'll be patching it:
uv add --editable /absolute/path/to/fastcontext
```

### Step 3 — Configure the model endpoint (same env vars as the CLI)

These are read by FastContext's internal LLM wrapper, so the **programmatic agent needs
them in its process environment** just like the CLI does. Set them before the agent runs
(shell export for testing; in production load them into the server's environment, e.g.
via your process manager or an `.env` loaded before importing fastcontext):

```bash
export FC_BASE_URL="http://127.0.0.1:11434/v1/"
export FC_MODEL="hf.co/mitkox/FastContext-1.0-4B-RL-Q4_K_M-GGUF:latest"
# Ollama does not require an API key.
# FC_REASONING_EFFORT accepts: none, low, medium, high, max.
export FC_REASONING_EFFORT="none"
export FC_MAX_TOKENS=1024
export FC_TEMPERATURE=0
```

### Step 4 — Programmatic use

```python
import asyncio

from fastcontext.agent.agent_factory import make_fastcontext_agent


async def main() -> None:
    agent = make_fastcontext_agent(
        trajectory_file=".fastcontext/trajectory.jsonl",
        work_dir="/path/to/repo",
    )
    answer = await agent.run(
        prompt="Find where database migrations are defined",
        max_turns=6,
        citation=True,
    )
    print(answer)


asyncio.run(main())
```

Integration notes for the MCP server:
- `work_dir` replaces the subprocess `cwd` — point it at the repo being scanned.
- Keep `trajectory_file` **outside** the scanned repo so you don't pollute it (e.g. a
  temp path per call), same as the CLI guidance.
- `agent.run(...)` is already a coroutine — `await` it directly inside your tool handler;
  no `asyncio.run` (that's only for the standalone script above).

### Step 5 — Verify the import resolves

```bash
uv run python -c "from fastcontext.agent.agent_factory import make_fastcontext_agent; print('ok')"
```

If that prints `ok`, Path A is live and you can drop the subprocess wrapper.

> Verify the exact `make_fastcontext_agent` / `agent.run` signatures and env-var names
> against source before committing: `src/fastcontext/agent/agent_factory.py` and
> `src/fastcontext/agent/llm.py`. The example above is from the README.

---

## If Path A fails — likely causes

- **Wrong Python.** `uv add` resolves but import errors / build fails → venv is < 3.12.
  Redo Step 1.
- **Submodules.** The repo has `third_party` submodules; a plain git install does not init
  them. If the build references them, use the **local path** install (Step 2) from your
  already-initialized clone, or `git submodule update --init --recursive` in the clone first.
- **Dependency conflict.** FastContext pulls in its full dependency tree (OpenAI-compatible
  client, etc.) into your venv. If it clashes with your MCP deps and you can't resolve it,
  the subprocess CLI keeps FastContext's deps in a separate process — use Path B.

---

## Path B — Fallback: installed CLI

If the previous steps don't work, keep using the `fastcontext` binary you already
installed and drive it as a subprocess.

```bash
export FC_BASE_URL="http://127.0.0.1:11434/v1/"
export FC_MODEL="hf.co/mitkox/FastContext-1.0-4B-RL-Q4_K_M-GGUF:latest"
# Ollama does not require an API key.
# Ollama accepts: none, low, medium, high, max.
export FC_REASONING_EFFORT="none"
export FC_MAX_TOKENS=1024
export FC_TEMPERATURE=0

fastcontext \
  --query "Find the files that implement authentication and explain where to make a change" \
  --max-turns 6 \
  --traj .fastcontext/trajectory.jsonl

# alternatively — return only the machine-readable citation block

fastcontext \
  --query "Locate the request validation logic" \
  --citation
```

Wrap this with the async subprocess helper from the earlier integration doc (parse the
`<final_answer>` block, set `cwd` to the repo, send `--traj` to a temp path, add a timeout).
