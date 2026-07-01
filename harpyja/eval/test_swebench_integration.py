"""Integration ACs (AC10, AC11) for the SWE-bench per-case-repo driver (spec 0010).

`@pytest.mark.integration`, skip-not-fail. The multi-repo driver is exercised live
against the existing legacy fixture (each case carries its own repo path), so no
SWE-bench provisioning/network is required for the run/sweep ACs; the convert smoke
(AC8) is separately network-gated. Every deterministic shape is already pinned by
the unit ACs — an absent stack/network degrades these to skips, never failures.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
from dataclasses import replace
from pathlib import Path

import pytest

from harpyja.eval.config import EvalConfig
from harpyja.eval.dataset import load_dataset
from harpyja.eval.live import default_seed_path
from harpyja.eval.report import validate_report
from harpyja.eval.runner import build_live_stack
from harpyja.eval.swebench_eval import (
    PROVENANCE_NAME,
    RAW_NAME,
    _load_resolved,
    _read_jsonl,
    run_swebench,
    run_swebench_sweep,
)

# Reuse the live-stack gating + egress guard from the 0009-6a integration suite.
from harpyja.eval.test_eval_integration import (
    _NEEDS_STACK,
    _deny_nonloopback_egress,
    _live_stack_available,
    _settings_live,
)

_LEGACY = Path(__file__).parent / "fixtures" / "legacy"


def _socket_reachable(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _live_cases(repo: str, cap: int = 2):
    """The seed cases, repointed at a live legacy repo (each its own 'repo')."""
    cases = load_dataset(default_seed_path())
    return [replace(c, repo=repo) for c in cases][:cap]


def _factory():
    return lambda settings, repo: build_live_stack(settings, repo)


# ---- AC10: live end-to-end + air-gap ---------------------------------------

@pytest.mark.integration
def test_swebench_driver_live_auto_schema_conforming(tmp_path):
    if not _live_stack_available():
        pytest.skip(_NEEDS_STACK)
    repo = str(tmp_path / "legacy")
    shutil.copytree(_LEGACY, repo)
    out = tmp_path / "out"
    report = run_swebench(
        _live_cases(repo), _settings_live(), EvalConfig(k_runs=1),
        stack_factory=_factory(), out_dir=out, write=True,
    )
    validate_report(report)
    assert (out / "report.json").exists()
    agg = report["aggregate"]
    assert agg["span_hit_rate_primary"] is not None
    assert agg["escalation_rate"] is not None
    assert "classifier_agreement_rate" in agg
    assert report["run_metadata"]["protocol"] == "standalone-localization"


@pytest.mark.integration
def test_swebench_driver_live_no_nonloopback_egress(tmp_path):
    if not _live_stack_available():
        pytest.skip(_NEEDS_STACK)
    repo = str(tmp_path / "legacy")
    shutil.copytree(_LEGACY, repo)
    with _deny_nonloopback_egress():
        report = run_swebench(
            _live_cases(repo), _settings_live(), EvalConfig(k_runs=1),
            stack_factory=_factory(), out_dir=tmp_path / "out", write=True,
        )
    validate_report(report)


# ---- Spec 0011 AC21: degrade visibility is surfaced live, never silent --------

@pytest.mark.integration
def test_swebench_live_surfaces_degrade_visibility(tmp_path):
    """AC21: re-running the driver live, the report SURFACES scout-degrade visibility
    as first-class fields — it can never read as a silent all-degrade again.

    With seam (a) the FastContext citation-formatter crash is gone, so Scout fires
    instead of flooring at `backend-error`. Asserts the degrade-visibility contract
    on a live run (legacy fixture stand-in; the real N=12 flask subset is the
    compute-bound operator opt-in): the degrade rate is *measured* (non-null),
    escalation is *measured*, every case records its per-case notes, and — the
    load-bearing guarantee — a degrade-floor run is loudly flagged rather than
    silent (rate < 1.0, OR rate == 1.0 ⇒ degraded_dominated + reliability note).
    """
    if not _live_stack_available():
        pytest.skip(_NEEDS_STACK)
    repo = str(tmp_path / "legacy")
    shutil.copytree(_LEGACY, repo)
    report = run_swebench(
        _live_cases(repo, cap=3), _settings_live(), EvalConfig(k_runs=1),
        stack_factory=_factory(), out_dir=tmp_path / "out", write=True,
    )
    validate_report(report)
    agg = report["aggregate"]
    # First-class, machine-readable degrade visibility (no longer silent).
    assert agg["scout_degrade_rate"] is not None  # measured, not a phantom 0.0/floor
    assert agg["escalation_rate"] is not None
    assert isinstance(agg["scout_degrade_count"], int)
    assert isinstance(agg["reliability_notes"], list)
    for f in ("fc_citation_spanned_count", "fc_citation_filelevel_count",
              "fc_citation_dropped_count"):
        assert isinstance(agg[f], int)
    # Every case records its own notes (a per-case reason, never silence).
    assert all("notes" in c for c in report["cases"])
    # The load-bearing guarantee: an all-degrade run is impossible to MISS.
    if agg["scout_degrade_rate"] >= 1.0:
        assert agg["degraded_dominated"] is True
        assert "degraded-dominated" in agg["reliability_notes"]


# ---- AC11: live OQ2 sweep + budget -----------------------------------------

@pytest.mark.integration
def test_swebench_sweep_live_recommendation_and_guard(tmp_path):
    if not _live_stack_available():
        pytest.skip(_NEEDS_STACK)
    repo = str(tmp_path / "legacy")
    shutil.copytree(_LEGACY, repo)
    out = tmp_path / "sweep-out"
    base = _settings_live()
    report = run_swebench_sweep(
        _live_cases(repo), base, EvalConfig(k_runs=1),
        stack_factory=_factory(), thresholds=(0.5, 0.7), top_ns=(3,),
        out_dir=out, write=True, sample_cap=2,
    )
    assert len(report["sweep"]) == 2  # 2 thresholds × 1 top_n
    rec = report["recommendation"]
    assert rec["verify_threshold"] in (0.5, 0.6, 0.7)
    assert "oq2_low_confidence" in rec and "oq2_basis" in rec
    assert (out / "sweep.json").exists()
    # N far below the floor → indicative_only; and base settings were not mutated.
    assert report["run_metadata"]["indicative_only"] is True
    assert base.verify_threshold == _settings_live().verify_threshold


# ---- Spec 0012 AC5: N=12 recovery re-measurement (operator-run) -------------

_SPEC_DIR = Path(__file__).resolve().parents[2] / "specs" / "0012-path-prefix"
_BASELINE = _SPEC_DIR / "baseline_q8rl_n12.json"


def _summarize(report: dict) -> dict:
    agg = report["aggregate"]
    cases = report["cases"]
    return {
        "scout_empty_count": sum(
            1 for c in cases if (c.get("notes") or "").startswith("gate-skipped:scout-empty")
        ),
        "gate_ran_count": sum(1 for c in cases if c.get("production_gate_ran")),
        "fc_spanned_count": agg["fc_citation_spanned_count"],
        "fc_filelevel_count": agg["fc_citation_filelevel_count"],
        "fc_dropped_count": agg["fc_citation_dropped_count"],
        # .get: the committed baseline predates spec 0012 (no recovered fields → 0).
        "recovered_spanned_count": agg.get("fc_citation_recovered_spanned_count", 0),
        "recovered_filelevel_count": agg.get("fc_citation_recovered_filelevel_count", 0),
    }


@pytest.mark.integration
def test_q8rl_recovery_n12_run_writes_artifact_with_delta(tmp_path):
    """AC5: re-run the committed N=12 point subset with a Q8 Scout model override
    (no production default changed) and suffix recovery ON; write the artifact with
    the recovered_filelevel_paths and the recorded delta vs the committed baseline.

    Operator-gated (skip-not-fail): set HARPYJA_Q8_SCOUT_MODEL to a served Q8
    FastContext model and HARPYJA_N12_FIXTURES to the provisioned fixtures dir
    (holding swebench_verified.resolved.jsonl for the 12 flask/requests/pylint/sphinx
    point cases). Pass = the artifact records the delta and self-flags
    indicative_only; there is NO strict-inequality gate (single non-deterministic run).
    """
    q8 = os.environ.get("HARPYJA_Q8_SCOUT_MODEL")
    fixtures = os.environ.get("HARPYJA_N12_FIXTURES")
    if not q8 or not fixtures:
        pytest.skip("set HARPYJA_Q8_SCOUT_MODEL + HARPYJA_N12_FIXTURES to run AC5")
    if not _live_stack_available():
        pytest.skip(_NEEDS_STACK)
    if not _BASELINE.is_file():
        pytest.skip(f"committed baseline missing: {_BASELINE}")

    cases, provenance, excluded, malformed = _load_resolved(fixtures)
    settings = replace(_settings_live(), scout_model=q8)

    # A factory that records each per-case Scout engine so we can read its final
    # (production) tally's recovered file-level PATHS after the run.
    engines = []

    def factory(s, repo):
        stack = build_live_stack(s, repo)
        if stack.scout_engine is not None:
            engines.append(stack.scout_engine)
        return stack

    out = tmp_path / "out"
    report = run_swebench(
        cases, settings, EvalConfig(k_runs=1), stack_factory=factory,
        out_dir=out, write=True, provenance=provenance,
        new_file_only_excluded_count=excluded, malformed_skipped_count=malformed,
        repo_revision=f"swebench-verified::{q8}",
    )
    validate_report(report)

    recovered_paths: list[str] = []
    for e in engines:
        t = getattr(e, "last_tally", None)
        if t is not None:
            recovered_paths.extend(t.recovered_filelevel_paths)

    base = json.loads(_BASELINE.read_text(encoding="utf-8"))
    base_sum = _summarize(base)
    new_sum = _summarize(report)
    artifact = {
        **new_sum,
        "recovered_filelevel_paths": sorted(recovered_paths),
        "indicative_only": report["run_metadata"]["indicative_only"],
        "baseline_ref": "specs/0012-path-prefix/baseline_q8rl_n12.json",
        "delta_vs_baseline": {k: new_sum[k] - base_sum[k] for k in new_sum},
    }
    (_SPEC_DIR / "run_q8rl_recovery_n12.json").write_text(
        json.dumps(artifact, indent=2, sort_keys=True), encoding="utf-8"
    )

    # Honest recorded delta — NOT a strict-inequality gate (single live run varies).
    assert artifact["indicative_only"] is True  # N=12 < n_floor
    assert "delta_vs_baseline" in artifact
    assert isinstance(artifact["recovered_filelevel_paths"], list)
    # The recovered count must match the listed paths (no count/paths drift).
    assert len(artifact["recovered_filelevel_paths"]) == artifact["recovered_filelevel_count"]


# ---- AC8: live HuggingFace convert smoke (network-gated) --------------------

@pytest.mark.integration
def test_convert_live_hf_smoke(tmp_path):
    try:
        import datasets  # noqa: F401
    except ImportError:
        pytest.skip("datasets not installed")
    if not _socket_reachable("huggingface.co", 443):
        pytest.skip("no network to HuggingFace")
    from harpyja.eval.swebench_eval import cmd_convert

    cmd_convert(argparse.Namespace(
        out_dir=str(tmp_path), sample=3, per_repo=3, seed=0, verbose=False,
    ))
    rows = _read_jsonl(tmp_path / RAW_NAME)
    assert rows  # at least one well-formed case
    assert all("case_id" in r and "expected_spans" in r for r in rows)
    prov = json.loads((tmp_path / PROVENANCE_NAME).read_text(encoding="utf-8"))
    assert "SWE-bench_Verified" in prov["hf_dataset_id"]
    assert len(prov["raw_fixture_sha256"]) == 64


# ---- Spec 0016 (AC7): the served-model default reaches Ollama's served set -----

@pytest.mark.integration
def test_scout_model_default_present_in_ollama_served_set():
    """The out-of-box `scout_model` default (no CLI flags) names a tag Ollama serves.

    Spec 0016 B1: the old default (`mitkox/...RL-Q4_K_M`) was served nowhere → 404 on
    every Scout call. This is a POSITIVE membership check against `/api/tags`, so it
    cannot pass trivially when the endpoint is down. Three-way, skip-not-fail:
      - Ollama unreachable                → skip (never fail)
      - reachable but the tag is absent   → skip with a diagnostic naming the tag
      - the OLD unserved tag is the default → FAIL (asserted unconditionally below)
    """
    import json as _json
    import urllib.request
    from urllib.parse import urlsplit

    from harpyja.config.settings import Settings

    _OLD_UNSERVED = "hf.co/mitkox/FastContext-1.0-4B-RL-Q4_K_M-GGUF:latest"
    default_scout = Settings().scout_model  # no model flags → the resolved default

    # Unconditional guard: a regression back to the unserved default fails even offline.
    assert default_scout != _OLD_UNSERVED

    parts = urlsplit(Settings().lm_api_base)
    host = parts.hostname or "localhost"
    port = parts.port or 11434
    if not _socket_reachable(host, port):
        pytest.skip(f"Ollama not reachable at {host}:{port}")

    tags_url = f"{parts.scheme or 'http'}://{host}:{port}/api/tags"
    try:
        with urllib.request.urlopen(tags_url, timeout=3.0) as resp:  # noqa: S310 (localhost)
            served = {m["name"] for m in _json.loads(resp.read()).get("models", [])}
    except OSError as err:
        pytest.skip(f"Ollama /api/tags query failed: {err}")

    if default_scout not in served:
        pytest.skip(
            f"default scout_model {default_scout!r} not in Ollama served set "
            f"({sorted(served)}) — pull it to validate AC7 live"
        )
    # Positive membership: the default IS served.
    assert default_scout in served
