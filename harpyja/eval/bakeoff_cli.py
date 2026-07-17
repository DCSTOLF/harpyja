"""Spec 0048 — bake-off: the operator CLI (``run_bakeoff.sh`` invokes this).

Loads the 0047 enlarged pool (44 conceptual / 9 lexical), pins the SUT hash and a
0041 exclusivity proof, wires the live preflight + cell seams, drives the staged
resumable grid, and writes the typed report. This is a LIVE operator entrypoint —
it STOPs loudly on an unready precondition, never a silent partial run. The pure
pool loader + report serialization are unit-covered; the grid itself is the ~9h
detached run.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
from pathlib import Path
from typing import Any

from harpyja.eval.bakeoff_analysis import BakeoffReport
from harpyja.eval.bakeoff_config import PREREGISTERED_BAKEOFF_CONFIG_0048, BakeoffConfig

_FIXTURES = Path(__file__).resolve().parent / "fixtures"
_DEFAULT_TERSE = _FIXTURES / "swebench_verified.terse.jsonl"
_DEFAULT_RESOLVED = _FIXTURES / "swebench_verified.resolved.jsonl"


def _load_resolved_gold(resolved_path: Path) -> dict[str, dict[str, Any]]:
    """The audited gold source: ``expected_spans`` keyed by case_id, normalized to
    the ``run_verified_case`` shape (``file``/``start_line``/``end_line``). Absent
    file → no gold. Only the pinned/resolved cases carry gold; the enlarged cases
    are provisioned by the operator."""
    if not resolved_path.is_file():
        return {}
    gold: dict[str, dict[str, Any]] = {}
    for line in resolved_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        spans = row.get("expected_spans") or []
        if spans:
            s = spans[0]
            gold[row["case_id"]] = {
                "file": s.get("path") or s.get("file"),
                "start_line": s.get("start_line"),
                "end_line": s.get("end_line"),
            }
    return gold


def load_bakeoff_pool(
    terse_path: str | Path = _DEFAULT_TERSE,
    resolved_path: str | Path = _DEFAULT_RESOLVED,
) -> tuple[list[str], dict[str, str], dict[str, dict[str, Any]]]:
    """Load the enlarged pool → (case_ids, reachability, cases_by_id).

    ``cases_by_id[case_id]`` carries the ``query``, ``repo``, and the ``gold`` span
    resolved from the audited ``expected_spans`` source (``resolved.jsonl``), falling
    back to the terse ``concept_span``. Gold is BLIND-WITHHELD / unprovisioned for the
    enlarged cases, so ``gold`` is ``None`` there — the operator supplies it before the
    live run; a ``None`` gold is a loud missing-input at cell time, never a silent
    skip. Order is the fixture's committed order (no cherry-picking)."""
    path = Path(terse_path)
    resolved_gold = _load_resolved_gold(Path(resolved_path))
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    case_ids: list[str] = []
    reachability: dict[str, str] = {}
    cases_by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        cid = row["case_id"]
        case_ids.append(cid)
        reachability[cid] = row["reachability"]
        cases_by_id[cid] = {
            "gold": resolved_gold.get(cid) or row.get("concept_span"),
            "gold_withheld": bool(row.get("gold_withheld")),
            "query": row["query"],
            "repo": row["repo"],
        }
    return case_ids, reachability, cases_by_id


def report_payload(cfg: BakeoffConfig, report: BakeoffReport) -> dict[str, Any]:
    """Serialize the typed report for the durable ``outcome`` artifact — the
    headline outcome, per-pair verdicts (conceptual, primary), lexical descriptive
    stats, per-repo distribution, the 0042/0043 per-model threads, and provenance."""
    return {
        "config_id": "0048/bake-off/1",
        "outcome": report.outcome.value,
        "ranking": list(report.ranking) if report.ranking else None,
        "exclusions": [{"tag": e.tag, "reason": e.reason} for e in report.exclusions],
        "conceptual_pairs": [
            {
                "pair": list(r.pair), "outcome": r.outcome.value, "b": r.b, "c": r.c,
                "eligible_n": r.eligible_n, "adjusted_p": r.adjusted_p,
                "winner": r.winner, "repo_concentrated": r.repo_concentrated,
                "degraded_dominated": r.degraded_dominated,
            }
            for r in report.conceptual_pair_results
        ],
        "lexical_descriptive_stats": dict(report.lexical_stats),
        "per_repo_distribution": {k: dict(v) for k, v in report.per_repo_distribution.items()},
        "symbols_adoption": dict(report.symbols_adoption),
        "found_but_unsubmitted": dict(report.found_but_unsubmitted),
        "provenance": {
            "pool_sha256": cfg.pool_sha256,
            "multiplicity_stance": cfg.multiplicity_stance,
            "conceptual_n": cfg.conceptual_n,
            "lexical_n": cfg.lexical_n,
        },
    }


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="bakeoff", description="spec 0048 bake-off run")
    p.add_argument("--ledger", required=True)
    p.add_argument("--api-base", default="http://localhost:11434")
    p.add_argument("--out-dir", default="/tmp/bakeoff_0048_artifacts")
    p.add_argument("--worktrees", default="eval_work/worktrees")
    p.add_argument("--report-out", default="specs/0048-bake-off/outcome.json")
    p.add_argument("--replay-cases", type=int, default=3)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """The live operator entrypoint. Preflights (assert-local-first → positive
    /api/tags → coherence + /v1 tool-calling → reproducibility replay), pins the
    exclusivity proof + SUT hash, then drives the staged resumable grid."""
    import urllib.request

    from harpyja.eval.bakeoff_driver import run_bakeoff
    from harpyja.eval.bakeoff_live import make_live_cell_runner, make_live_preflight_prober
    from harpyja.eval.bakeoff_run import probe_served_membership
    from harpyja.eval.exclusivity_gate import check_exclusive_endpoint
    from harpyja.eval.reactive_config import compute_sut_hash
    from harpyja.gateway.gateway import assert_local

    args = _parse_args(argv)
    cfg = PREREGISTERED_BAKEOFF_CONFIG_0048

    def _tags_reader(api_base: str) -> list[str]:
        with urllib.request.urlopen(f"{api_base}/api/tags", timeout=10) as r:  # noqa: S310
            return [m["name"] for m in json.loads(r.read())["models"]]

    # Positive /api/tags membership, assert_local FIRST.
    membership = probe_served_membership(
        cfg, api_base=args.api_base, assert_local_fn=assert_local, tags_reader=_tags_reader
    )
    served_tags = [t for t, ok in membership.items() if ok]

    # The 0041 exclusivity proof + the pinned SUT hash, recorded per artifact.
    exclusivity_record = check_exclusive_endpoint(args.api_base, cfg.model_tags)
    sut_hash = compute_sut_hash()

    case_ids, reachability, cases_by_id = load_bakeoff_pool()
    replay_cases = [c for c in case_ids if reachability[c] == "conceptual"][: args.replay_cases]

    def _coherence_probe(tag: str) -> tuple[bool, bool]:
        from harpyja.eval.live_verifier import probe_reasoning_default
        from harpyja.gateway.gateway import ModelGateway

        gw = ModelGateway(api_base=f"{args.api_base}/v1", model=tag)
        try:
            probe_reasoning_default(gw)  # one sane gateway round-trip
            return True, True
        except Exception:
            return False, False

    def _replay_cell(tag: str, case_id: str, _run_ix: int):
        from harpyja.eval.live_verifier import run_verified_case
        from harpyja.gateway.gateway import ModelGateway

        case = cases_by_id[case_id]
        from harpyja.config.settings import Settings

        settings = dataclasses.replace(
            Settings(), lm_api_base=f"{args.api_base}/v1", lm_model=tag,
            explorer_think=cfg.explorer_think,
        )
        gw = ModelGateway(api_base=settings.lm_api_base, model=settings.lm_model)
        result, _ = run_verified_case(
            case_name=case_id, settings=settings, gateway=gw, gold_span=case["gold"],
            out_dir=Path(args.out_dir) / "replay" / tag.replace(":", "_"),
            repo_path=str(Path(args.worktrees) / case_id), query=case["query"],
        )
        from harpyja.eval.locate_accuracy import LocateBucket

        tb = result.terminal_bucket
        return LocateBucket(tb) if tb else LocateBucket.EMPTY

    prober = make_live_preflight_prober(
        cfg, served_tags=served_tags, replay_cases=replay_cases,
        coherence_probe=_coherence_probe, replay_cell=_replay_cell,
    )
    cell_runner = make_live_cell_runner(
        cfg, api_base=args.api_base, out_dir=args.out_dir, cases_by_id=cases_by_id,
        worktrees_root=args.worktrees, sut_hash=sut_hash,
        exclusivity_record=exclusivity_record,
    )

    report = run_bakeoff(
        cfg, case_ids=case_ids, reachability=reachability, ledger_path=args.ledger,
        preflight_prober=prober, cell_runner=cell_runner,
    )

    payload = report_payload(cfg, report)
    out = Path(args.report_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(f"bake-off OUTCOME: {report.outcome.value}")
    if report.ranking:
        print(f"  ranking: {' > '.join(report.ranking)}")
    for e in report.exclusions:
        print(f"  MODEL_EXCLUDED({e.tag}, {e.reason})")
    print(f"  report written: {out}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
