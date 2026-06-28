"""Integration ACs (AC7, AC8) for the eval harness (spec 0009-6a).

`@pytest.mark.integration`, skip-not-fail: runs the seed set through the REAL
`mode=auto` stack (Scout + Verification Gate + Deep) on a loopback endpoint and the
OQ2 sweep over it. Every deterministic shape (metrics, schema, scoring, N-floor) is
pinned by the unit ACs; a flaky/absent model degrades this to a skip, never a false
failure.
"""

from __future__ import annotations

import ipaddress
import shutil
import socket
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

import pytest

from harpyja.config.settings import Settings
from harpyja.eval.config import EvalConfig
from harpyja.eval.live import run_live_eval, run_live_sweep
from harpyja.eval.report import validate_report

_LOOPBACK = "http://127.0.0.1:11434/v1"
_DEEP_MODEL = "qwen2.5-coder:3b"
_NEEDS_STACK = (
    "requires FastContext + dspy + Deno + rg + a live endpoint with the Deep driver model"
)
_FIXTURE = Path(__file__).parent / "fixtures" / "legacy"


def _endpoint_reachable(api_base: str, timeout: float = 0.25) -> bool:
    hostport = api_base.split("://", 1)[-1].split("/", 1)[0]
    host, _, port = hostport.partition(":")
    try:
        with socket.create_connection((host, int(port or 80)), timeout=timeout):
            return True
    except OSError:
        return False


def _live_stack_available() -> bool:
    try:
        import dspy  # noqa: F401
        import fastcontext  # noqa: F401
    except ImportError:
        return False
    if shutil.which("deno") is None or shutil.which("rg") is None:
        return False
    return _endpoint_reachable(_LOOPBACK)


def _settings_live() -> Settings:
    return replace(Settings(), lm_api_base=_LOOPBACK, lm_model=_DEEP_MODEL, deep_max_subqueries=1)


def _repo(tmp_path) -> str:
    dst = tmp_path / "legacy"
    shutil.copytree(_FIXTURE, dst)
    return str(dst)


def _is_loopback_host(host: str) -> bool:
    if host in ("localhost", ""):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


@contextmanager
def _deny_nonloopback_egress():
    """In-process guard: allow loopback connects, raise on any non-loopback host.

    Covers the harness's own Python egress surface (gateway / scout client).
    Subprocess/sandbox egress (Deno) is covered by the Wave-4 / Scout network-deny
    tests, not re-litigated here.
    """
    real_connect = socket.socket.connect

    def guarded(self, address):
        try:
            host = address[0] if isinstance(address, tuple) else ""
        except Exception:
            host = ""
        if isinstance(address, tuple) and not _is_loopback_host(str(host)):
            raise AssertionError(f"non-loopback egress attempted to {address!r}")
        return real_connect(self, address)

    socket.socket.connect = guarded  # type: ignore[method-assign]
    try:
        yield
    finally:
        socket.socket.connect = real_connect  # type: ignore[method-assign]


# ---- AC7 -------------------------------------------------------------------

@pytest.mark.integration
def test_eval_end_to_end_live_seed_set_schema_conforming(tmp_path):
    if not _live_stack_available():
        pytest.skip(_NEEDS_STACK)
    repo = _repo(tmp_path)
    out = tmp_path / "eval-out"
    report = run_live_eval(
        repo, settings=_settings_live(), eval_config=EvalConfig(k_runs=1),
        out_dir=out, repo_revision="fixture-legacy",
    )
    validate_report(report)
    assert (out / "report.json").exists()
    assert len(report["cases"]) == 5


@pytest.mark.integration
def test_eval_all_metrics_populated_or_explicit_null_with_count(tmp_path):
    if not _live_stack_available():
        pytest.skip(_NEEDS_STACK)
    repo = _repo(tmp_path)
    report = run_live_eval(
        repo, settings=_settings_live(), eval_config=EvalConfig(k_runs=1),
        out_dir=tmp_path / "out", repo_revision="fixture-legacy",
    )
    agg = report["aggregate"]
    # Every aggregate field is present (schema). A null gate metric must carry its
    # (zero) count — populated-or-explicit-null-with-count (D2 / AC7).
    for key in ("span_hit_rate_primary", "escalation_rate", "tier01_resolve_rate"):
        assert agg[key] is not None
    if agg["gate_catch_rate"] is None:
        assert agg["wrong_tier1_count"] == 0
    if agg["gate_false_escalation"] is None:
        assert agg["correct_tier1_count"] == 0


@pytest.mark.integration
def test_eval_air_gap_no_nonloopback_egress(tmp_path):
    if not _live_stack_available():
        pytest.skip(_NEEDS_STACK)
    repo = _repo(tmp_path)
    with _deny_nonloopback_egress():
        report = run_live_eval(
            repo, settings=_settings_live(), eval_config=EvalConfig(k_runs=1),
            out_dir=tmp_path / "out", repo_revision="fixture-legacy",
        )
    validate_report(report)


# ---- AC8 -------------------------------------------------------------------

@pytest.mark.integration
def test_oq2_sweep_live_produces_recommendation(tmp_path):
    if not _live_stack_available():
        pytest.skip(_NEEDS_STACK)
    repo = _repo(tmp_path)
    out = tmp_path / "sweep-out"
    report = run_live_sweep(
        repo, base_settings=_settings_live(), eval_config=EvalConfig(k_runs=1),
        thresholds=(0.5, 0.7), top_ns=(3,), out_dir=out, repo_revision="fixture-legacy",
    )
    assert len(report["sweep"]) == 2  # 2 thresholds × 1 top_n
    rec = report["recommendation"]
    assert rec["verify_threshold"] in (0.5, 0.6, 0.7)
    assert "incumbent_validated" in rec
    assert (out / "sweep.json").exists()


@pytest.mark.integration
def test_oq2_sweep_applies_n_floor_caveat_below_floor(tmp_path):
    if not _live_stack_available():
        pytest.skip(_NEEDS_STACK)
    repo = _repo(tmp_path)
    report = run_live_sweep(
        repo, base_settings=_settings_live(), eval_config=EvalConfig(k_runs=1),
        thresholds=(0.6,), top_ns=(3,), out_dir=tmp_path / "out", repo_revision="fixture-legacy",
    )
    # the 5-case seed is far below the pinned N_FLOOR=30 -> indicative_only.
    assert report["run_metadata"]["seed_n"] < EvalConfig().n_floor
    assert report["run_metadata"]["indicative_only"] is True
