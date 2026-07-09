"""Discriminating experiment: explicit think:true + raised budget on astropy.

Premise established by probes (2026-07-09):
- Ollama /v1 honors `think` and returns `message.reasoning` SEPARATE from content;
  tool_calls parse cleanly alongside (finish=tool_calls).
- Thinking is ALREADY ON by default for qwen3:14b — every prior run reasoned
  invisibly INSIDE the 2048 max_tokens cap. So the experimental variable is
  BUDGET + explicit think, vs the cap-2048 status quo (4 runs, zero right-file).

Arm: think=true, max_tokens=8192, astropy__astropy-12907, N=2 runs.
Records per run: terminal bucket, submitted/surviving, tools, per-turn reasoning
(persisted to a side file), finish_reasons, wall time.
"""
import dataclasses
import json
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, "/Users/daniel.stolf/development/harpyja")

from harpyja.config.settings import Settings
from harpyja.eval.live_verifier import verifier_preflight, verify_trajectory
from harpyja.eval.locate_accuracy import classify_case, normalize_citations
from harpyja.gateway.gateway import ModelGateway
from harpyja.index.manifest import read_manifest
from harpyja.scout.errors import ScoutUnavailable
from harpyja.scout.explorer_backend import ExplorerBackend, _tool_schemas
from harpyja.server.types import CodeSpan
from harpyja.symbols.engine_identity import engine_identity
from harpyja.symbols.ripgrep import RipgrepEngine
from harpyja.symbols.symbols_io import load_symbols_or_none

API = "http://127.0.0.1:11434/v1"
MODEL = "qwen3:14b"
REPO = "/Users/daniel.stolf/development/harpyja/eval_work/worktrees/astropy__astropy-12907"
QUERY = "where is the separability matrix computed for nested compound models"
GOLD = CodeSpan(path="astropy/modeling/separable.py", start_line=242, end_line=248)
OUT = Path("/Users/daniel.stolf/.claude/jobs/d8e27f45/tmp/think_experiment")
OUT.mkdir(exist_ok=True)

MAX_TOKENS = 8192
N_RUNS = 2

tags = json.loads(
    urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=5).read()
)
verifier_preflight(API, MODEL, tags)
print(f"[preflight] OK — think:true + max_tokens={MAX_TOKENS}, N={N_RUNS}", flush=True)

settings = dataclasses.replace(
    Settings(),
    lm_api_base=API,
    lm_model=MODEL,
    scout_max_turns=10,
    scout_wall_clock_s=900.0,      # thinking turns are slower — generous ceiling
    lm_http_timeout_s=300.0,
)
gateway = ModelGateway(api_base=API, model=MODEL)

art_dir = Path(REPO) / ".harpyja"
manifest = read_manifest(art_dir) or []
symbol_records = load_symbols_or_none(art_dir, engine_identity()) or []
ripgrep = RipgrepEngine(settings)
schemas = _tool_schemas()

for run_idx in range(1, N_RUNS + 1):
    reasoning_log = []  # (turn, reasoning_len, finish_reason)
    turn_no = {"n": 0}

    def model_call(messages):
        # The gateway's return dict drops `reasoning` by design; capture it via
        # the INJECTABLE transport seam (raw response inspected, then passed on).
        import functools

        from harpyja.gateway.gateway import _default_transport

        captured = {}

        def capturing_transport(url, payload):
            resp = _default_transport(url, payload, timeout_s=settings.lm_http_timeout_s)
            msg = (resp.get("choices") or [{}])[0].get("message", {})
            captured["reasoning"] = msg.get("reasoning") or ""
            captured["usage"] = resp.get("usage")
            return resp

        turn_no["n"] += 1
        resp = gateway.complete_with_tools(
            messages, schemas,
            transport=capturing_transport,
            max_tokens=MAX_TOKENS, think=True,
        )
        reasoning_log.append({
            "turn": turn_no["n"],
            "reasoning_chars": len(captured.get("reasoning", "")),
            "reasoning": captured.get("reasoning", ""),
            "usage": captured.get("usage"),
            "finish_reason": resp.get("finish_reason"),
        })
        return resp

    backend = ExplorerBackend(
        gateway=gateway,
        repo_path=REPO,
        settings=settings,
        manifest=manifest,
        search_engine=ripgrep,
        symbol_records=symbol_records,
        model_call=model_call,
        max_tokens=MAX_TOKENS,
    )

    print(f"[run {run_idx}] starting ...", flush=True)
    t0 = time.monotonic()
    degrade = None
    try:
        citations = backend.run(QUERY, [])
    except ScoutUnavailable as e:
        citations = []
        degrade = e.cause
    wall = time.monotonic() - t0

    traj = backend.last_trajectory or {}
    normalized = normalize_citations(citations, None)
    bucket, _ = classify_case(normalized.effective, (GOLD,), window=50)

    tools = traj.get("tool_names_invoked", [])
    record = {
        "run": run_idx,
        "arm": {"think": True, "max_tokens": MAX_TOKENS},
        "bucket": bucket.value if bucket else None,
        "degrade": degrade,
        "citations": [
            {"path": s.path, "start": s.start_line, "end": s.end_line} for s in citations
        ],
        "citations_submitted": traj.get("citations_submitted"),
        "citations_surviving": traj.get("citations_surviving"),
        "tools_invoked": tools,
        "turns": traj.get("turns_used"),
        "wall_s": round(wall, 1),
        "reasoning_per_turn": [
            {k: v for k, v in r.items() if k != "reasoning"} for r in reasoning_log
        ],
    }
    (OUT / f"run{run_idx}_trajectory.json").write_text(
        json.dumps({"record": record, "model_turns": traj.get("model_turns", []),
                    "reasoning_log": reasoning_log}, indent=2, default=str)
    )
    print(json.dumps(record), flush=True)

print("[done]", flush=True)
