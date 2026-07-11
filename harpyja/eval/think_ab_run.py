"""Spec 0039 — AC6: the resumable, STOP-AND-WARN operator run machinery.

The paired run is ~19 cases x 2 arms x K=2 x ~200s — a multi-hour operator run
that outlasts one invocation, so every completed case+arm+repeat cell lands in
a version-stamped resumable ledger keyed to the FROZEN config hash (a ledger
written under a different config is not resumable — loud, never merged).

Preflight (STOP-AND-WARN, before any arm fires): the pre-registered model tag
must be SERVED (the default ``lm_model`` tag is NOT servable on the live stack —
the 0036 lesson), and the two-call seed probe reports whether the ``/v1`` path
honors ``seed``. A negative probe DOWNGRADES the config's paired-per-repeat
claim to ``"unverified"`` — the 0037 lesson: never record provenance an endpoint
may silently drop.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from harpyja.eval.locate_accuracy import LocateBucket
from harpyja.eval.locate_probe import require_live_stack
from harpyja.eval.think_ab import AbConfig

__all__ = [
    "AB_LEDGER_SCHEMA_VERSION",
    "AbLedger",
    "AbRunError",
    "ab_preflight",
    "require_live_stack",
    "seed_honoring_probe",
]

AB_LEDGER_SCHEMA_VERSION = "0039/1"

_KNOWN_LEDGER_SCHEMA_VERSIONS = frozenset({AB_LEDGER_SCHEMA_VERSION})


class AbRunError(ValueError):
    """A run precondition or ledger that does not conform — loud, never defaulted."""


class AbLedger:
    """Resumable per-cell (case x arm x repeat) run ledger, atomically persisted."""

    def __init__(self, path: str | Path, *, config_hash: str):
        self._path = Path(path)
        self._config_hash = config_hash
        if self._path.is_file():
            obj = json.loads(self._path.read_text(encoding="utf-8"))
            version = obj.get("schema_version")
            if version not in _KNOWN_LEDGER_SCHEMA_VERSIONS:
                raise AbRunError(f"unknown ab-ledger schema_version: {version!r}")
            if obj.get("config_hash") != config_hash:
                raise AbRunError(
                    "ledger was written under a different frozen config "
                    f"({obj.get('config_hash')!r} != {config_hash!r}) — not resumable"
                )
            self._entries: dict[str, dict[str, Any]] = dict(obj.get("entries", {}))
        else:
            self._entries = {}
            self._flush()

    @staticmethod
    def _key(case_id: str, arm: str, repeat: int) -> str:
        return f"{case_id}::{arm}::{repeat}"

    def has(self, case_id: str, arm: str, repeat: int) -> bool:
        return self._key(case_id, arm, repeat) in self._entries

    def get(self, case_id: str, arm: str, repeat: int) -> dict[str, Any] | None:
        return self._entries.get(self._key(case_id, arm, repeat))

    def record(
        self, case_id: str, arm: str, repeat: int, entry: dict[str, Any]
    ) -> None:
        self._entries[self._key(case_id, arm, repeat)] = entry
        self._flush()

    @property
    def entries(self) -> dict[str, dict[str, Any]]:
        return dict(self._entries)

    def _flush(self) -> None:
        payload = {
            "schema_version": AB_LEDGER_SCHEMA_VERSION,
            "config_hash": self._config_hash,
            "entries": self._entries,
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        tmp.write_text(
            json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
        )
        tmp.replace(self._path)


def seed_honoring_probe(call: Callable[[int], str], *, seed: int) -> str:
    """Two same-request+same-seed calls: identical completions → "honored",
    anything else → "unverified" (never a false paired-per-repeat claim)."""
    first = call(seed)
    second = call(seed)
    return "honored" if first == second else "unverified"


def ab_preflight(
    cfg: AbConfig, *, served_tags: list[str], seed_probe: str
) -> dict[str, Any]:
    """STOP-AND-WARN gate before any arm fires. Raises when the PRE-REGISTERED
    model tag is not served (a runtime substitution under the frozen hash would
    be exactly the post-hoc steering the freeze prevents)."""
    if cfg.lm_model not in served_tags:
        raise AbRunError(
            f"pre-registered model tag {cfg.lm_model!r} is not served "
            f"(served: {served_tags}) — STOP; do not substitute a model under "
            f"the frozen config hash"
        )
    return {
        "model_served": True,
        "lm_model": cfg.lm_model,
        "serving_transport": cfg.serving_transport,
        "seed_honoring": seed_probe,
    }


def fold_repeats(
    buckets: list[LocateBucket | None], degrades: list[str | None]
) -> tuple[LocateBucket | None, str | None]:
    """The frozen any-success K-fold: McNemar needs ONE binary outcome per
    case+arm, so K repeats collapse to the BEST bucket across clean repeats
    (precedence CORRECT > RIGHT_FILE_WRONG_SPAN > WRONG_FILE > EMPTY). A cell
    whose repeats ALL degraded folds to its typed degrade cause — never a
    silently-empty observation."""
    precedence = [
        LocateBucket.CORRECT,
        LocateBucket.RIGHT_FILE_WRONG_SPAN,
        LocateBucket.WRONG_FILE,
        LocateBucket.EMPTY,
    ]
    clean = [b for b in buckets if b is not None]
    if clean:
        return min(clean, key=precedence.index), None
    causes = [d for d in degrades if d]
    return None, (causes[0] if causes else "unknown")


def run_ab_paired(
    cfg: AbConfig,
    *,
    out_dir: str | Path,
    ledger_path: str | Path,
    live: bool = False,
) -> dict[str, Any]:
    """The precheck-GATED paired run (AC6). The AC5 gate is evaluated FIRST on
    committed evidence: an UNDER_POWERED_STOP returns the typed refusal — no
    arm fires, no ledger is created, the stop is the deliverable. There is no
    force/bypass parameter: the gate is not a lever.

    On the PROCEED branch (``live=True``) drives the paired arms
    (A: ``explorer_think=None`` shipped default / B: ``False``) x K repeats over
    the 0036 set via ``run_verified_case``, resumable through ``AbLedger``,
    folds K by the frozen any-success rule, and returns the split report plus
    the per-arm symbols-adoption and reasoning-cost metrics."""
    import dataclasses as _dc

    from harpyja.eval.think_ab import AB_CONFIG_HASH_0039
    from harpyja.eval.think_ab_precheck import run_precheck

    precheck = run_precheck(cfg)
    if precheck.outcome == "under-powered-stop":
        return {
            "status": "gated-under-powered-stop",
            "precheck": _dc.asdict(precheck),
            "config_hash": AB_CONFIG_HASH_0039,
        }
    if not live:
        raise AbRunError(
            "pre-check PROCEEDED but live wiring was not requested — pass "
            "live=True from the committed driver"
        )
    return _run_ab_paired_live(
        cfg, out_dir=Path(out_dir), ledger_path=Path(ledger_path)
    )


def _run_ab_paired_live(
    cfg: AbConfig, *, out_dir: Path, ledger_path: Path
) -> dict[str, Any]:
    """The live PROCEED branch: arm-major, repeat-major, ledger-resumable."""
    import dataclasses as _dc
    import json as _json
    import urllib.request

    from harpyja.config.settings import Settings
    from harpyja.eval.live_verifier import run_verified_case
    from harpyja.eval.think_ab import (
        AB_CONFIG_HASH_0039,
        PairRecord,
        decide_ab_report,
    )
    from harpyja.eval.think_ab_precheck import _repo_root, load_fixture_reachability
    from harpyja.gateway.gateway import ModelGateway

    root = _repo_root()
    fixtures = root / "harpyja" / "eval" / "fixtures"
    worktrees = root / "eval_work" / "worktrees"

    # Preflight: served tag + seed probe (STOP-AND-WARN).
    with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=10) as r:
        served = [m["name"] for m in _json.loads(r.read())["models"]]

    def _seed_call(seed: int) -> str:
        payload = _json.dumps(
            {
                "model": cfg.lm_model,
                "messages": [{"role": "user", "content": "Reply with one word."}],
                "max_tokens": 8,
                "seed": seed,
                "reasoning_effort": "none",
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            "http://127.0.0.1:11434/v1/chat/completions",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = _json.loads(resp.read())
        return body["choices"][0]["message"].get("content", "")

    seed_probe = seed_honoring_probe(_seed_call, seed=cfg.seed_schedule[0])
    preflight = ab_preflight(cfg, served_tags=served, seed_probe=seed_probe)

    reachability = load_fixture_reachability()
    cases: list[dict[str, Any]] = []
    raw_index = {}
    for line in (fixtures / "swebench_verified.raw.jsonl").read_text(
        encoding="utf-8"
    ).splitlines():
        if line.strip():
            row = _json.loads(line)
            raw_index[row["case_id"]] = row
    for line in (fixtures / "swebench_verified.terse.jsonl").read_text(
        encoding="utf-8"
    ).splitlines():
        if not line.strip():
            continue
        row = _json.loads(line)
        raw = raw_index[row["case_id"]]
        gold = raw["expected_spans"][0]
        cases.append(
            {
                "case_id": row["case_id"],
                "query": row["query"],
                "gold": {
                    "file": gold["path"],
                    "start_line": gold["start_line"],
                    "end_line": gold["end_line"],
                },
            }
        )

    arms = {"on": cfg.arm_a_think, "off": cfg.arm_b_think}
    ledger = AbLedger(ledger_path, config_hash=AB_CONFIG_HASH_0039)

    for arm_name, think in arms.items():
        for repeat in range(cfg.k_repeats):
            for case in cases:
                if ledger.has(case["case_id"], arm_name, repeat):
                    continue
                settings = _dc.replace(
                    Settings(),
                    lm_api_base="http://127.0.0.1:11434/v1",
                    lm_model=cfg.lm_model,
                    explorer_think=think,
                    scout_max_turns=10,
                    scout_wall_clock_s=240.0,
                    lm_http_timeout_s=300.0,
                )
                gateway = ModelGateway(
                    api_base=settings.lm_api_base, model=settings.lm_model
                )
                arm_dir = out_dir / arm_name / f"k{repeat}"
                try:
                    result, artifact_path = run_verified_case(
                        case_name=case["case_id"],
                        settings=settings,
                        gateway=gateway,
                        gold_span=case["gold"],
                        out_dir=arm_dir,
                        repo_path=str(worktrees / case["case_id"]),
                        query=case["query"],
                    )
                except ValueError as e:
                    ledger.record(
                        case["case_id"],
                        arm_name,
                        repeat,
                        {"bucket": None, "degrade": f"no-trajectory: {e}", "artifact": None},
                    )
                    continue
                artifact = _json.loads(
                    Path(artifact_path).read_text(encoding="utf-8")
                )
                if result.status != "PASSED":
                    entry = {
                        "bucket": None,
                        "degrade": f"verifier:{result.failure_reason}",
                        "artifact": str(artifact_path),
                    }
                else:
                    per_turn = artifact.get("per_turn") or []
                    entry = {
                        "bucket": artifact["terminal_bucket"],
                        "degrade": None,
                        "artifact": str(artifact_path),
                        "reasoning_chars": sum(
                            t.get("reasoning_chars", 0) for t in per_turn
                        ),
                        "completion_tokens": sum(
                            t.get("completion_tokens", 0) for t in per_turn
                        ),
                        "tools": artifact.get("tool_names", []),
                        "think_mode": artifact.get("think_mode"),
                        "serving_transport": artifact.get("serving_transport"),
                    }
                ledger.record(case["case_id"], arm_name, repeat, entry)

    # Fold K repeats per case+arm and assemble PairRecords.
    records: list[PairRecord] = []
    symbols_adoption = {"on": 0, "off": 0}
    reasoning_totals = {"on": 0, "off": 0}
    for case in cases:
        folded: dict[str, dict[str, Any]] = {}
        for arm_name in arms:
            cells = [
                ledger.get(case["case_id"], arm_name, k)
                for k in range(cfg.k_repeats)
            ]
            buckets = [
                LocateBucket(c["bucket"]) if c and c.get("bucket") else None
                for c in cells
            ]
            degrades = [c.get("degrade") if c else "missing" for c in cells]
            bucket, degrade = fold_repeats(buckets, degrades)
            clean = [c for c in cells if c and c.get("degrade") is None]
            folded[arm_name] = {
                "bucket": bucket,
                "degrade": degrade,
                "reasoning": max(
                    (c.get("reasoning_chars", 0) for c in clean), default=0
                ),
                "tokens": max(
                    (c.get("completion_tokens", 0) for c in clean), default=0
                ),
                "symbols": any(
                    "symbols" in (c.get("tools") or []) for c in clean
                ),
            }
        for arm_name in arms:
            if folded[arm_name]["symbols"]:
                symbols_adoption[arm_name] += 1
            reasoning_totals[arm_name] += folded[arm_name]["reasoning"]
        records.append(
            PairRecord(
                case_id=case["case_id"],
                reachability=reachability[case["case_id"]],
                bucket_on=folded["on"]["bucket"],
                bucket_off=folded["off"]["bucket"],
                reasoning_chars_on=folded["on"]["reasoning"],
                reasoning_chars_off=folded["off"]["reasoning"],
                completion_tokens_on=folded["on"]["tokens"],
                completion_tokens_off=folded["off"]["tokens"],
                degrade_on=folded["on"]["degrade"],
                degrade_off=folded["off"]["degrade"],
            )
        )

    report = decide_ab_report(records, cfg)
    n = len(cases) or 1
    return {
        "status": "completed",
        "config_hash": AB_CONFIG_HASH_0039,
        "preflight": preflight,
        "report": {
            "config_hash": report.config_hash,
            "headline": report.headline,
            "strata": {
                name: {
                    "n": line.n,
                    "status": line.status,
                    "floor": line.floor,
                    "verdict": line.result.verdict.value if line.result else None,
                    "signal_discordant": (
                        line.result.signal_discordant if line.result else None
                    ),
                    "discordant_b": line.result.discordant_b if line.result else None,
                    "discordant_c": line.result.discordant_c if line.result else None,
                    "excluded": list(line.result.excluded) if line.result else [],
                    "confound_reasons": (
                        list(line.result.confound_reasons) if line.result else []
                    ),
                }
                for name, line in report.strata.items()
            },
        },
        "symbols_adoption": symbols_adoption,
        "reasoning_cost_delta": (
            reasoning_totals["on"] - reasoning_totals["off"]
        )
        / n,
    }
