"""Spec 0020 (T19) — live wiring for the OQ2 operator protocol.

Builds the real G0→G3 collaborators over the resolved SWE-bench fixture + the served
stack and drives `run_oq2_protocol`. Offline (loopback-only) at run time: the only
outbound calls go through the Model Gateway / `assert_local`. This module is the seam
the operator uses to actually PRODUCE the recorded typed outcome — the unit tests
prove the driver correct; this makes it runnable end-to-end.

Cost note (D9): with `--deep-model qwen3-coder:30b` the full clean G3 sweep is
`k_runs × |grid| × |point cases|` `mode=auto` runs — many hours. G0/G1 are cheap and
gate that cost; G2-over-ceiling routes to a single descriptive pass instead.
"""

from __future__ import annotations

import dataclasses
import json
import subprocess
from itertools import product
from pathlib import Path

from harpyja.eval.config import EvalConfig
from harpyja.eval.oq2_protocol import (
    G1Result,
    G2Result,
    G3Result,
    ProvisionInfo,
    run_oq2_protocol,
)
from harpyja.eval.recommend import (
    SweepPoint,
    gate_confounded_recommendation,
    recommend_oq2,
)
from harpyja.eval.swebench_eval import (
    DEFAULT_THRESHOLDS,
    DEFAULT_TOP_NS,
    _live_stack_factory,
    _load_resolved,
    _mean_or_none,
    run_swebench,
)

_G1_CASE_ID = "astropy__astropy-12907"
_DESCRIPTIVE_KEYS = (
    "span_hit_rate_primary",
    "escalation_rate",
    "tier01_resolve_rate",
    "fc_citation_spanned_count",
    "fc_citation_filelevel_count",
    "fc_citation_dropped_count",
)


def _sut_git_sha() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        )
        return out.stdout.strip()
    except Exception:
        return "unknown"


def _fetch_tags(settings) -> dict:
    """Fetch `/api/tags` behind `assert_local` (the same loopback-gated egress class)."""
    import urllib.request
    from urllib.parse import urlsplit

    from harpyja.gateway.gateway import assert_local

    assert_local(settings.lm_api_base)
    parts = urlsplit(settings.lm_api_base)
    host = parts.hostname or "localhost"
    url = f"{parts.scheme or 'http'}://{host}:{parts.port or 11434}/api/tags"
    with urllib.request.urlopen(url, timeout=5.0) as resp:  # noqa: S310 (loopback)
        return json.loads(resp.read())


def run_oq2_operator(
    fixtures_dir: str | Path,
    base_settings,
    eval_config: EvalConfig,
    *,
    out_dir: str | Path,
    thresholds=None,
    top_ns=None,
    per_case_timeout: float | None = None,
    write: bool = True,
):
    """Wire the live collaborators and run the four-gate protocol end-to-end."""
    cases, _provenance, _excluded, _malformed = _load_resolved(fixtures_dir)
    point_cases = [c for c in cases if c.classification == "point"]
    stack_factory = _live_stack_factory()
    thresholds = tuple(thresholds) if thresholds else DEFAULT_THRESHOLDS
    top_ns = tuple(top_ns) if top_ns else DEFAULT_TOP_NS
    state: dict = {}  # carries G2's measured instruct FE forward to a confounded G3

    def _run(cases_, settings, cfg):
        return run_swebench(
            cases_, settings, cfg, stack_factory=stack_factory, mode="auto",
            per_case_timeout=per_case_timeout,
        )

    def provision():
        return ProvisionInfo(
            fixture_subset_id=f"swebench-verified-n{len(point_cases)}",
            effective_n=len(point_cases),
        )

    def run_g1(settings, cfg):
        astro = [c for c in cases if c.case_id == _G1_CASE_ID]
        if not astro:
            return G1Result(completed=False, measured={"reason": f"{_G1_CASE_ID} absent"})
        try:
            rep = _run(astro, settings, cfg)
        except Exception as err:  # OOM / backend crash — an environment hold, not a finding
            return G1Result(completed=False, environment_failure=True,
                            measured={"error": type(err).__name__, "detail": str(err)[:200]})
        agg = rep["aggregate"]
        fe = agg.get("gate_false_escalation")
        return G1Result(
            completed=True,
            degrade_dominant=bool(agg.get("degraded_dominated")),
            correct_citation_false_rejected=(fe is not None and fe > 0),
            measured={
                "tier1_correct": rep["cases"][0].get("tier1_correct"),
                "gate_false_escalation": fe,
                "scout_degrade_rate": agg.get("scout_degrade_rate"),
                "deep_degrade_rate": agg.get("deep_degrade_rate"),
                "notes": rep["cases"][0].get("notes"),
            },
        )

    def run_g2(settings, cfg):
        # A/B: the instruct judge (default) vs the retained finder judge, same subset.
        instruct_rep = _run(
            point_cases, dataclasses.replace(settings, verify_method="instruct_model"), cfg
        )
        finder_rep = _run(
            point_cases, dataclasses.replace(settings, verify_method="scout_model"), cfg
        )
        instruct_fe = instruct_rep["aggregate"].get("gate_false_escalation")
        state["instruct_fe"] = instruct_fe
        return G2Result(
            instruct_false_escalation=instruct_fe,
            finder_false_escalation=finder_rep["aggregate"].get("gate_false_escalation"),
            catch_rate=instruct_rep["aggregate"].get("gate_catch_rate"),
        )

    def run_g3(settings, cfg, *, descriptive_only):
        if descriptive_only:
            rep = _run(point_cases, settings, cfg)
            agg = rep["aggregate"]
            rec = gate_confounded_recommendation(state.get("instruct_fe") or 0.0, cfg)
            return G3Result(
                recommendation=rec,
                aggregate={"degraded_dominated": bool(agg.get("degraded_dominated"))},
                descriptive={k: agg.get(k) for k in _DESCRIPTIVE_KEYS},
            )
        rank_inputs: list[SweepPoint] = []
        degraded_any = False
        descriptive: dict = {}
        for thr, top_n in product(thresholds, top_ns):
            pset = dataclasses.replace(settings, verify_threshold=thr, verify_top_n=top_n)
            per_run = [_run(point_cases, pset, cfg)["aggregate"] for _ in range(cfg.k_runs)]
            degraded_any = degraded_any or any(bool(a.get("degraded_dominated")) for a in per_run)
            catch = [a.get("gate_catch_rate") for a in per_run]
            false_runs = [a.get("gate_false_escalation") for a in per_run]
            rank_inputs.append(SweepPoint(
                verify_threshold=thr, verify_top_n=top_n,
                catch_rate_mean=_mean_or_none(catch),
                false_escalation_mean=(_mean_or_none(false_runs) or 0.0),
                false_escalation_runs=tuple(v for v in false_runs if v is not None),
            ))
            if not descriptive:
                descriptive = {k: per_run[0].get(k) for k in _DESCRIPTIVE_KEYS}
        rec = recommend_oq2(rank_inputs, state.get("instruct_fe"), cfg)
        return G3Result(
            recommendation=rec,
            aggregate={"degraded_dominated": degraded_any},
            descriptive=descriptive,
        )

    provenance_base = {
        "sut_git_sha": _sut_git_sha(),
        "model_tags": sorted({base_settings.scout_model, base_settings.lm_model}),
        "grid": {"thresholds": list(thresholds), "top_ns": list(top_ns)},
    }
    repo_path = point_cases[0].repo if point_cases else str(fixtures_dir)
    return run_oq2_protocol(
        settings=base_settings,
        eval_config=eval_config,
        tags_payload=_fetch_tags(base_settings),
        provenance_base=provenance_base,
        provision=provision,
        run_g1=run_g1,
        run_g2=run_g2,
        run_g3=run_g3,
        out_dir=out_dir,
        repo_path=repo_path,
        write=write,
    )
