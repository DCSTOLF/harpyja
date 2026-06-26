# Harpyja — Specification

Authoritative contracts for Harpyja: MCP tools, internal interfaces, data shapes, configuration, and
behavioral guarantees. Prose-level rationale lives in [`ARCHITECTURE.md`](./ARCHITECTURE.md).

- **Status:** draft / v0
- **Language:** Python 3.12+
- **Transport:** MCP over stdio and streamable HTTP
- **Runtime deps:** ripgrep, Deno (RLM sandbox), local OpenAI-compatible model endpoint

---

## 1. Terminology

| Term | Meaning |
|------|---------|
| **Citation** | A `file:line-range` reference with an optional rationale. The unit of output. |
| **Manifest** | Ranked JSONL index of repository files. |
| **Symbol index** | AST-derived map of symbols → spans, per file. |
| **CodeSpan** | Normalized `(path, start_line, end_line)` record used everywhere internally. |
| **Tier** | A locator engine: 0 (deterministic), 1 (Scout), 2 (Deep). |
| **Mode** | Caller-facing routing hint: `auto`, `fast`, `deep`. |
| **Profile** | A named bundle of budgets/thresholds (e.g. `default`, `fast-local`, `thorough`). |

---

## 2. MCP tool contracts

All tools are **read-only**. None mutate the repository. All paths returned are repo-relative.

### 2.1 `harpyja_locate`

Find the files and lines relevant to a natural-language query.

**Input**

| Field | Type | Req | Default | Notes |
|-------|------|-----|---------|-------|
| `query` | string | yes | — | Natural-language description of what to find. |
| `repo_path` | string | yes | — | Absolute path to a git repo or directory. |
| `mode` | enum(`auto`,`fast`,`deep`) | no | `auto` | Routing hint. |
| `max_results` | int | no | `8` | Upper bound on returned citations (1–50). |
| `language_hint` | string | no | null | Optional language filter (e.g. `go`). |

**Output**

```json
{
  "citations": [
    {
      "path": "src/billing/gateway.py",
      "start_line": 212,
      "end_line": 241,
      "rationale": "retry loop with exponential backoff around the payment POST",
      "source_tier": 1,
      "score": 0.86
    }
  ],
  "confidence": "high",          // high | medium | low
  "tiers_run": [0, 1],
  "elapsed_ms": 1840,
  "notes": null                   // e.g. "model endpoint unreachable; Tier 0 only"
}
```

**Guarantees**

- Citations are sorted by descending `score`, deduplicated, overlapping spans merged.
- `confidence: "low"` is returned (never an error) when the only available tier is degraded.
- Never returns more than `max_results` citations.

### 2.2 `harpyja_read`

Return a bounded code snippet. Useful when the agent cannot read the filesystem directly (remote/air-gapped).

**Input:** `path` (string, repo-relative or absolute within repo), `start` (int ≥1), `end` (int ≥ start).
**Output:** `{ "path", "start", "end", "language", "content", "truncated": bool }`.
**Bounds:** clamped to `tool_max_lines` (default 400) and `tool_max_chars` (default 20000); `truncated`
flags clamping. Reads outside `repo_path` are rejected.

### 2.3 `harpyja_index`

Build or refresh the manifest and symbol index.

**Input:** `repo_path` (string, req), `refresh` (bool, default false — full rebuild when true).
**Output:** `{ "files_indexed", "symbols_indexed", "languages": {<lang>: <count>}, "elapsed_ms", "degraded": [<paths>] }`
where `degraded` lists files that fell back to ripgrep.

---

## 3. Internal interfaces

All tiers implement a common protocol so the Orchestrator treats them uniformly.

```python
class Locator(Protocol):
    name: str
    tier: int
    async def locate(self, req: LocateRequest, seed: list[CodeSpan]) -> LocateResult: ...

@dataclass
class CodeSpan:
    path: str            # repo-relative
    start_line: int
    end_line: int
    symbol: str | None = None
    language: str | None = None

@dataclass
class Citation(CodeSpan):
    rationale: str | None = None
    source_tier: int = 0
    score: float = 0.0

@dataclass
class LocateRequest:
    query: str
    repo_path: str
    mode: Literal["auto", "fast", "deep"]
    max_results: int
    language_hint: str | None

@dataclass
class LocateResult:
    citations: list[Citation]
    confidence: Literal["high", "medium", "low"]
    tiers_run: list[int]
    notes: str | None = None
```

### 3.1 Orchestrator

```python
class Orchestrator:
    async def run(self, req: LocateRequest) -> LocateResult: ...
    def classify(self, query: str) -> Literal["point", "broad"]: ...
    def plan(self, req, classification, index_ready: bool) -> list[int]: ...  # tier sequence
```

**Classification rules (v0, heuristic; replaceable by a model later):**
- `point` if the query names a concrete symbol/file/error string, or matches patterns like
  *where is / which file / definition of / find the function*.
- `broad` if it matches *how does … flow / trace / all places / across the (system|codebase) / audit /
  every*.
- Default to `point` when ambiguous (cheaper).

**Planning matrix**

| mode | classification | index_ready | tier plan |
|------|----------------|-------------|-----------|
| auto | point | yes | [0, 1] → gate → maybe 2 |
| auto | point | no  | [1] → gate → maybe 2 |
| auto | broad | any | [0, 2] (skip gate; broad goes deep) |
| fast | any | any | [0, 1] (no escalation; low-confidence flag if gate would fail) |
| deep | any | any | [0, 2] |

### 3.2 Symbol Layer

```python
class SymbolEngine(Protocol):
    def supports(self, language: str) -> bool: ...
    def symbols(self, path: str) -> list[CodeSpan]: ...           # definitions in a file
    def lookup(self, name: str, scope: str | None) -> list[CodeSpan]: ...

class RipgrepEngine:    # fallback; supports() always True
    def search(self, pattern: str, scope: str | None,
               max_files: int, max_matches: int) -> list[CodeSpan]: ...
```

**Degradation contract:** `symbols()` and `lookup()` MUST NOT raise on parse failure. They log the failure,
record the path in the run's `degraded` set, and fall back to `RipgrepEngine`. Callers never branch on engine.

**Languages with AST support (v0):** Go, Rust, Python, JavaScript, TypeScript, C#, Java, C, C++.
Symbol kinds extracted: function, method, class, struct, interface, enum, type alias, top-level const/var.

### 3.3 Scout (Tier 1) adapter

```python
class ScoutAdapter(Locator):
    tier = 1
    async def locate(self, req, seed) -> LocateResult: ...
```

Wraps **Microsoft FastContext** directly (pinned dependency, not reimplemented): constructs a FastContext
agent (`make_fastcontext_agent(work_dir=repo_path, …)`), passes the query (and optional seed spans as hints),
lets it run its read-only `Read`/`Glob`/`Grep` exploration with parallel tool calls against the Model Gateway,
and parses the returned `<final_answer>` block into `Citation`s. Bounded by `scout_max_turns`. The adapter is
the **only** module that knows FastContext's wire format.

### 3.4 Deep (Tier 2) RLM driver

```python
class DeepLocator(Locator):
    tier = 2
    async def locate(self, req, seed) -> LocateResult: ...
```

Constructs a **fresh `dspy.RLM` per call** (thread-safety requirement). The repo manifest and bounded host
tools are exposed inside the sandbox REPL:

| Host tool | Signature | Bounds |
|-----------|-----------|--------|
| `list_manifest` | `(filter: str = "") -> list[dict]` | caps rows to `manifest_page` |
| `search` | `(pattern, scope=None) -> list[CodeSpan]` | `search_max_files`, `search_max_matches` |
| `symbols` | `(path) -> list[CodeSpan]` | AST when available, else ripgrep |
| `read_span` | `(path, start, end) -> str` | `tool_max_lines`, `tool_max_chars` |

Bounded by `rlm_max_llm_calls`, `rlm_max_iterations`, `rlm_max_output_chars`. The driver instructs the RLM to
emit a final citation block in the same `CodeSpan` JSON shape.

### 3.5 Verification Gate

```python
class VerificationGate:
    def check(self, citations: list[Citation], query: str) -> GateResult: ...

@dataclass
class GateResult:
    score: float            # 0..1 aggregate relevance
    passed: bool            # score >= verify_threshold
    per_citation: dict[str, float]
```

Reads each cited span and scores relevance via the configured method:
- `judge` — a single sub-model call returning a 0–1 relevance score (default).
- `embedding` — cosine similarity between query and span embeddings (if a local embedder is configured).
- `both` — min of the two (conservative).

### 3.6 Model Gateway

```python
class ModelGateway:
    def __init__(self, base_url, primary_model, sub_model=None, api_key=None): ...
    async def complete(self, messages, *, model="primary", **kw) -> str: ...
    def assert_local(self) -> None:   # raises if base_url is non-loopback and allow_remote is False
```

OpenAI-compatible chat completions. `assert_local()` enforces the air-gap guarantee at startup.

---

## 4. Data formats

### 4.1 Manifest (`.harpyja/manifest.jsonl`)

One JSON object per line:

```json
{"path": "src/billing/gateway.py", "language": "python", "size": 8421,
 "hash": "sha256:…", "mtime": 1750000000, "prior": 0.72}
```

`prior` is a relevance heuristic (path depth, test/vendor/generated penalties, source-dir bonus) used to
order candidates before any model runs.

### 4.2 Symbol index (`.harpyja/symbols.jsonl`)

```json
{"path": "src/billing/gateway.py", "symbol": "PaymentGateway.charge",
 "kind": "method", "start_line": 198, "end_line": 244, "language": "python"}
```

Both artifacts live under `.harpyja/` in the repo (gitignored by default) and are incrementally updated by
file hash.

---

## 5. Configuration

Load order (later overrides earlier): built-in profile defaults → `harpyja.toml` → `HARPYJA_*` env vars →
per-request fields.

```toml
[model]
api_base   = "http://localhost:11434/v1"   # HARPYJA_LM_API_BASE
primary    = "qwen-4b-instruct"            # HARPYJA_LM_MODEL
sub        = ""                             # optional smaller judge/sub model; defaults to primary
api_key    = ""                             # if endpoint requires one
allow_remote = false                        # must be true to point at non-loopback

[routing]
default_mode    = "auto"
verify_method   = "judge"                   # judge | embedding | both
verify_threshold = 0.6
escalate_on_empty = true

[scout]                      # Tier 1
max_turns = 6

[deep]                       # Tier 2
rlm_max_iterations  = 10
rlm_max_llm_calls   = 60
rlm_max_output_chars = 20000

[search]                     # ripgrep bounds
search_max_files   = 4000
search_max_matches = 400
rg_chunk_size      = 512

[tools]
tool_max_lines = 400
tool_max_chars = 20000
manifest_page  = 200

[index]
ignore_globs = ["**/node_modules/**", "**/.git/**", "**/dist/**", "**/*.min.js"]
follow_symlinks = false

[languages]                  # toggle AST engines; off → ripgrep for that language
go = true
rust = true
python = true
javascript = true
typescript = true
csharp = true
java = true
c = true
cpp = true
```

**Profiles.** `--profile fast-local` tightens turns/iterations for small-context models; `--profile thorough`
raises Deep budgets. Profiles set defaults only; explicit config and env still win.

---

## 6. CLI

```
harpyja serve   [--stdio | --http --port N]
harpyja index   --repo PATH [--refresh]
harpyja locate  --repo PATH --query STR [--mode auto|fast|deep] [--max-results N]
harpyja read    --repo PATH --path FILE --start N --end M
harpyja doctor  # checks rg, deno, model endpoint, language parsers; prints air-gap status
```

`locate`/`read` share the exact code path as the MCP tools (the MCP layer is a thin wrapper), so CLI output
mirrors tool output.

---

## 7. Error handling & degradation

| Condition | Behavior |
|-----------|----------|
| Model endpoint unreachable | Run Tier 0 only; `confidence: low`; `notes` set. Never hard-fail `locate`. |
| Parser missing / parse error | Fall back to ripgrep for that file; record in `degraded`. |
| RLM sandbox (Deno) unavailable | Skip Tier 2; return best Tier 1/0 result with flag. |
| Empty Tier-1 result | Escalate (if `escalate_on_empty`), else return empty with `confidence: low`. |
| Path outside repo | Reject with a tool error (security boundary). |
| Concurrent requests | Each gets isolated state; Deep builds a fresh RLM instance per call. |

---

## 8. Security & privacy guarantees

1. **Read-only.** No tool writes to the repository.
2. **No egress.** Only the Model Gateway makes calls, and only to a loopback endpoint unless
   `allow_remote=true` is explicitly set.
3. **Path confinement.** All reads/searches are confined within `repo_path`; traversal outside is rejected.
4. **No telemetry.** Nothing is logged off-box. Trajectory logs (if enabled) stay under `.harpyja/`.
5. **Secret hygiene.** Snippet outputs are not persisted by default; enabling trajectory capture warns that
   outputs may contain secrets.

---

## 9. Acceptance tests (behavioral)

- **Point lookup** resolves a known function to the correct `file:line` using Tier 0 alone (no model).
- **Graceful degradation:** renaming a parser to force failure still returns ripgrep citations; file appears
  in `degraded`.
- **Escalation:** a broad "trace how X flows" query runs Tier 2 and returns multi-file citations.
- **Gate catch:** an injected wrong Tier-1 citation scores below threshold and triggers escalation.
- **Air-gap:** with the model endpoint down, `locate` returns Tier-0 citations and `confidence: low`, no error.
- **Agent integration:** Claude Code and Codex can register the server over stdio and call `harpyja_locate`.
- **Concurrency:** N parallel `locate` calls return correct, non-interleaved results.
