"""spec 0040 T14 — the committed three-model preflight driver (operator tooling).

STOP-AND-WARN posture: aborts loudly when Ollama is unreachable; each pinned
model — the two NEW tags and the re-confirmed ``qwen3:14b`` anchor — is typed
through the committed ``PreflightOutcome`` enum (coherence + clean /v1
tool_calls + per-model think-control probe) and the result is written to
``preflight_result.json`` (schema 0040/preflight/1), VALIDATED by the same
loud validator the drift pin uses before it ever lands on disk.

Re-runnable: probes are cheap (~1 min/model); a re-run overwrites the artifact
wholesale (no partial merge — the artifact is only ever a complete typed
answer for all three models).
"""

from __future__ import annotations

import dataclasses
import json
import sys
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from harpyja.eval.pool_pilot import run_model_preflight  # noqa: E402
from harpyja.eval.pool_precheck import (  # noqa: E402
    POOL_CONFIG_HASH_0040,
    PREREGISTERED_POOL_CONFIG_0040,
)
from harpyja.eval.pool_preflight_result import (  # noqa: E402
    POOL_PREFLIGHT_SCHEMA_VERSION,
    validate_pool_preflight_result,
)

API_BASE = "http://127.0.0.1:11434"
OUT = Path(__file__).parent / "preflight_result.json"
CFG = PREREGISTERED_POOL_CONFIG_0040


def main() -> int:
    try:
        with urllib.request.urlopen(f"{API_BASE}/api/tags", timeout=10) as r:
            served = {m["name"] for m in json.loads(r.read())["models"]}
    except Exception as e:  # noqa: BLE001
        raise SystemExit(f"STOP-AND-WARN: Ollama unreachable: {e}") from e

    models: dict[str, dict] = {}
    for tag in CFG.model_tags:
        print(f"preflight: {tag} ...", flush=True)
        result = run_model_preflight(tag, served_tags=served, api_base=API_BASE)
        obs = dataclasses.asdict(result.observations)
        models[tag] = {
            "outcome": result.outcome.value,
            **obs,
            "think_control_mechanism": result.think_control_mechanism,
            "exclusion_reason": result.exclusion_reason,
        }
        print(f"  -> {result.outcome.value} (think: {obs['think_control']})")

    artifact = {
        "schema_version": POOL_PREFLIGHT_SCHEMA_VERSION,
        "endpoint": f"{API_BASE}/v1",
        "config_hash": POOL_CONFIG_HASH_0040,
        "models": models,
    }
    validate_pool_preflight_result(artifact)
    OUT.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
