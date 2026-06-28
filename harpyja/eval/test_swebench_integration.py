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
