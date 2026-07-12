"""Spec 0042 — AC6 unit: the gated adoption re-measurement machinery.

``run_adoption_cells`` consumes the FROZEN ``PREREGISTERED_ADOPTION_CONFIG_0042``
coverage (pinned 0040 pilot cases x required models, optional recorded-if-run —
never re-selected), routes the whole run through ``run_gated_pool_pilot``
(live=True required; the ``0041/pilot/2`` exclusivity proof rides the ledger,
keyed by ``ADOPTION_CONFIG_HASH_0042``), and per clean cell emits a
trajectory-VERIFIED artifact (verifier seam, never self-reported) carrying the
model identity, the tools invoked including the per-case ``symbols`` invocation
count, the terminal bucket, citations, and the exclusivity-proof reference.

All fakes here — no network (the test_gate_run idioms).
"""

from __future__ import annotations

import importlib.util
import inspect
import json
from pathlib import Path

import pytest

from harpyja.eval.adoption_precheck import (
    ADOPTION_CONFIG_HASH_0042,
    PREREGISTERED_ADOPTION_CONFIG_0042,
)
from harpyja.eval.adoption_run import (
    build_adoption_cell_artifact,
    build_adoption_run_summary,
    run_adoption_cells,
)
from harpyja.eval.pool_pilot import PoolRunError
from harpyja.eval.pool_precheck import (
    POOL_CONFIG_HASH_0040,
    PREREGISTERED_POOL_CONFIG_0040,
)

_CFG = PREREGISTERED_ADOPTION_CONFIG_0042
_REPO_ROOT = Path(__file__).resolve().parents[2]
# Evidence-path convention: the committed driver pins specs/.archive first
# (the post-close location), live specs/ fallback while the spec is active.
_DRIVER_ARCHIVED = (
    _REPO_ROOT / "specs" / ".archive" / "0042-adoption" / "adoption_run" / "run_adoption.py"
)
_DRIVER_LIVE = _REPO_ROOT / "specs" / "0042-adoption" / "adoption_run" / "run_adoption.py"
_DRIVER = _DRIVER_ARCHIVED if _DRIVER_ARCHIVED.is_file() else _DRIVER_LIVE


def _fake_verifier_artifact(
    case_id: str,
    model: str,
    *,
    bucket: str = "right-file-wrong-span",
    symbols_calls: int = 2,
    verifier_status: str = "PASSED",
    failure_reason: str | None = None,
) -> dict:
    """A verifier-shaped artifact (the ``run_verified_case`` output shape):
    tool usage lives in ``model_turns`` tool_calls — the machinery must DERIVE
    the tool facts from the trajectory, never accept a self-reported list."""
    calls = [{"id": "t1", "function": {"name": "grep", "arguments": "{}"}}]
    calls += [
        {"id": f"s{i}", "function": {"name": "symbols", "arguments": "{}"}}
        for i in range(symbols_calls)
    ]
    return {
        "schema_version": "0038/1",
        "requested_model": model,
        "endpoint": "http://127.0.0.1:11434/v1",
        "served_model": model,
        "configured_endpoint_models": [model],
        "tiers_run": [0, 1],
        "model_turns": [
            {"role": "assistant", "tool_calls": calls},
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "t9",
                        "function": {"name": "submit_citations", "arguments": "{}"},
                    }
                ],
            },
        ],
        "terminal_bucket": bucket,
        "verifier_status": verifier_status,
        "failure_reason": failure_reason,
        "citations_submitted": 1,
        "citations_surviving": 1,
        "case": case_id,
    }


def _passing_runner(case: dict, model: str) -> tuple[dict, str | None]:
    return _fake_verifier_artifact(case["case_id"], model), None


def _run(tmp_path: Path, **kw):
    kw.setdefault("verified_case_runner", _passing_runner)
    kw.setdefault("ps_reader", lambda api_base: [])
    kw.setdefault("live", True)
    return run_adoption_cells(
        ledger_path=tmp_path / "adoption_results.json",
        artifact_dir=tmp_path / "artifacts",
        **kw,
    )


def test_adoption_run_cell_emits_trajectory_verified_artifact(tmp_path):
    result = _run(tmp_path)
    assert result["status"] == "completed"
    assert result["cells_remaining"] == []

    case_id = _CFG.pilot_case_ids[0]
    model = _CFG.required_models[0]
    slug = model.replace(":", "_").replace(".", "_")
    art_path = tmp_path / "artifacts" / f"{case_id}__{slug}.adoption.json"
    assert art_path.is_file()
    art = json.loads(art_path.read_text(encoding="utf-8"))
    # Model identity: requested AND served, from the VERIFIED trajectory.
    assert art["requested_model"] == model
    assert art["served_model"] == model
    assert art["verifier_status"] == "PASSED"
    # Tools invoked — including the per-case symbols invocation COUNT (two
    # symbols calls in the trajectory; tool_names_invoked is ordered-unique).
    assert art["tool_names_invoked"] == ["grep", "symbols", "submit_citations"]
    assert art["symbols_invocations"] == 2
    # Terminal bucket + citations.
    assert art["terminal_bucket"] == "right-file-wrong-span"
    assert art["citations_submitted"] == 1
    assert art["citations_surviving"] == 1
    # The run's exclusivity-proof reference.
    ref = art["exclusivity_proof_ref"]
    assert ref["ledger"] == str(tmp_path / "adoption_results.json")
    assert ref["ledger_schema_version"] == "0041/pilot/2"
    assert ref["config_hash"] == ADOPTION_CONFIG_HASH_0042
    # The ledger cell mirrors the measurement facts (the decider's inputs).
    obj = json.loads((tmp_path / "adoption_results.json").read_text(encoding="utf-8"))
    cell = obj["entries"][f"{case_id}::{model}"]
    assert cell["bucket"] == "right-file-wrong-span"
    assert cell["symbols_invocations"] == 2
    assert cell["artifact"] == str(art_path)


def test_adoption_artifact_builder_refuses_unverified_trajectories(tmp_path):
    """The artifact is trajectory-VERIFIED by construction: a failed
    verification is a typed degrade in the ledger, never an artifact."""
    failed = _fake_verifier_artifact(
        "c1", "qwen3:14b", verifier_status="FAILED", failure_reason="model-mismatch"
    )
    with pytest.raises(PoolRunError, match="verifier-PASSED"):
        build_adoption_cell_artifact(
            case_id="c1",
            model="qwen3:14b",
            verifier_artifact=failed,
            verifier_artifact_path=None,
            ledger_path=tmp_path / "ledger.json",
        )

    bad_case = _CFG.pilot_case_ids[1]

    def runner(case: dict, model: str) -> tuple[dict, str | None]:
        if case["case_id"] == bad_case:
            return (
                _fake_verifier_artifact(
                    case["case_id"],
                    model,
                    verifier_status="FAILED",
                    failure_reason="model-mismatch",
                ),
                None,
            )
        return _passing_runner(case, model)

    _run(tmp_path, verified_case_runner=runner)
    obj = json.loads((tmp_path / "adoption_results.json").read_text(encoding="utf-8"))
    cell = obj["entries"][f"{bad_case}::{_CFG.required_models[0]}"]
    assert cell["bucket"] is None
    assert cell["degrade"] == "verifier:model-mismatch"
    slug = _CFG.required_models[0].replace(":", "_").replace(".", "_")
    assert not (tmp_path / "artifacts" / f"{bad_case}__{slug}.adoption.json").exists()


def test_adoption_run_refuses_without_live(tmp_path):
    """The 0040/0041 posture: the machinery is a live operator entrypoint —
    never fired implicitly; the committed driver is the only live=True caller."""
    with pytest.raises(PoolRunError, match="live=True"):
        run_adoption_cells(
            ledger_path=tmp_path / "adoption_results.json",
            artifact_dir=tmp_path / "artifacts",
            verified_case_runner=_passing_runner,
            ps_reader=lambda api_base: [],
        )
    assert not (tmp_path / "adoption_results.json").exists()


def test_adoption_run_consumes_pinned_0040_cases(tmp_path):
    """The cells enumerated == the frozen config's pilot_case_ids x required
    models (+ optional only when explicitly included); no re-selection
    parameter exists on the entrypoint."""
    _run(tmp_path)
    obj = json.loads((tmp_path / "adoption_results.json").read_text(encoding="utf-8"))
    expected = {f"{cid}::{m}" for cid in _CFG.pilot_case_ids for m in _CFG.required_models}
    assert set(obj["entries"]) == expected

    with_optional = tmp_path / "with_optional"
    with_optional.mkdir()
    result = _run(with_optional, include_optional=("qwen3:8b",))
    assert result["models"] == list(_CFG.required_models) + ["qwen3:8b"]
    obj = json.loads(
        (with_optional / "adoption_results.json").read_text(encoding="utf-8")
    )
    expected = {
        f"{cid}::{m}"
        for cid in _CFG.pilot_case_ids
        for m in (*_CFG.required_models, "qwen3:8b")
    }
    assert set(obj["entries"]) == expected

    # Coverage is CONSUMED from the freeze — an unpinned tag refuses loudly...
    with pytest.raises(PoolRunError, match="never re-selected"):
        _run(tmp_path, include_optional=("qwen3-coder:30b",))
    # ...and no signature seam allows re-selecting cases or models.
    params = set(inspect.signature(run_adoption_cells).parameters)
    reselection = {
        "cases",
        "case_ids",
        "pilot_case_ids",
        "models",
        "pilot_models",
        "model_tags",
        "required_models",
    }
    assert params & reselection == set()


def test_adoption_run_no_force_bypass_parameter():
    """Signature introspection (the 0039/0041 no-bypass idiom) across every
    public entry point: machinery, gate wrapper, and the committed driver."""
    from harpyja.eval.gate_run import run_gated_pool_pilot

    forbidden = {
        "force",
        "bypass",
        "allow_contended",
        "skip_gate",
        "ignore_contention",
        "skip_preflight",
        "no_gate",
    }
    for fn in (run_adoption_cells, run_gated_pool_pilot):
        assert set(inspect.signature(fn).parameters) & forbidden == set()

    # The committed driver exposes no force/bypass/skip-gate CLI flag either.
    spec = importlib.util.spec_from_file_location("run_adoption_0042", _DRIVER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert set(inspect.signature(mod.main).parameters) & forbidden == set()
    option_strings = [
        s for action in mod.build_parser()._actions for s in action.option_strings
    ]
    for opt in option_strings:
        flat = opt.lstrip("-").replace("-", "_")
        assert flat not in forbidden
        assert "force" not in flat and "bypass" not in flat and "gate" not in flat


def test_adoption_ledger_carries_exclusivity_proof_and_config_hash(tmp_path):
    _run(tmp_path)
    obj = json.loads((tmp_path / "adoption_results.json").read_text(encoding="utf-8"))
    # 0041/pilot/2-shaped, keyed by the FROZEN 0042 adoption hash (a ledger
    # under a different hash is not resumable — the freeze discipline).
    assert obj["schema_version"] == "0041/pilot/2"
    assert obj["config_hash"] == ADOPTION_CONFIG_HASH_0042
    assert obj["config_hash"] != POOL_CONFIG_HASH_0040
    record = obj["exclusivity"]
    assert record["exclusivity_check_kind"] == "start-plus-per-block"
    # start + one per model block (required-only run → 1 block).
    assert len(record["checks"]) == 1 + len(_CFG.required_models)
    assert all(c["clean"] and c["timestamp"] for c in record["checks"])
    # The foreign predicate ran against the frozen 0040 tag set (identity).
    assert record["model_set"] == list(PREREGISTERED_POOL_CONFIG_0040.model_tags)


def test_clean_cells_never_rerun(tmp_path):
    """Resumability (the 0041 ``_cell_needs_run`` posture): clean cells never
    re-run; a typed degrade gets exactly ONE bounded re-run, then rests."""
    bad_case = _CFG.pilot_case_ids[2]
    calls: list[str] = []

    def runner(case: dict, model: str) -> tuple[dict, str | None]:
        calls.append(case["case_id"])
        if case["case_id"] == bad_case:
            return (
                _fake_verifier_artifact(
                    case["case_id"],
                    model,
                    verifier_status="FAILED",
                    failure_reason="terminal-bucket-missing",
                ),
                None,
            )
        return _passing_runner(case, model)

    _run(tmp_path, verified_case_runner=runner)
    assert len(calls) == len(_CFG.pilot_case_ids)

    # Second invocation over the same ledger: ONLY the degraded cell re-runs.
    calls.clear()
    _run(tmp_path, verified_case_runner=runner)
    assert calls == [bad_case]
    obj = json.loads((tmp_path / "adoption_results.json").read_text(encoding="utf-8"))
    cell = obj["entries"][f"{bad_case}::{_CFG.required_models[0]}"]
    assert cell["attempts"] == 2

    # Third invocation: degrade at the attempt cap → recorded-by-cause, no run.
    calls.clear()
    result = _run(tmp_path, verified_case_runner=runner)
    assert calls == []
    assert result["status"] == "completed"
    assert result["cells_remaining"] == []


def test_adoption_run_budget_stop_reports_in_progress(tmp_path):
    """The wall-clock posture (0040 run_pilot precedent): a budget stop is a
    typed in-progress result with the remaining cells — resumable, never a
    silent partial 'completed'."""
    result = _run(tmp_path, budget_s=0.0)
    assert result["status"] == "in-progress"
    assert len(result["cells_remaining"]) == len(_CFG.pilot_case_ids)
    # The ledger exists (gate proof recorded) with zero cells fired.
    obj = json.loads((tmp_path / "adoption_results.json").read_text(encoding="utf-8"))
    assert obj["schema_version"] == "0041/pilot/2"
    assert obj["entries"] == {}
    # Re-invoking without the budget completes the remaining cells.
    result = _run(tmp_path)
    assert result["status"] == "completed"
    assert result["cells_remaining"] == []


def test_adoption_run_summary_reuses_frozen_decider(tmp_path):
    """The machine-readable summary is derived by the FROZEN T9 machinery
    (build_adoption_cells + decide_adoption_outcome) over the committed 0040
    baseline — a 14b-only all-clean run has RFWS denominator 2 → provisionally
    under-powered by construction (the frozen config's own docstring)."""
    _run(tmp_path)
    summary = build_adoption_run_summary(tmp_path / "adoption_results.json")
    assert summary["config_hash"] == ADOPTION_CONFIG_HASH_0042
    assert summary["models_run"] == list(_CFG.required_models)
    assert summary["cells_clean"] == len(_CFG.pilot_case_ids)
    assert summary["cells_degraded"] == 0
    assert summary["cells_suspect"] == 0
    decision = summary["decision"]
    # Every fake cell invoked symbols → adopted over the full 14b universe.
    assert decision["adoption_count"] == len(_CFG.pilot_case_ids)
    assert decision["rfws_denominator"] == 2
    assert decision["under_powered"] is True
    assert decision["outcome"] == "adopted-under-powered"
    assert list(decision["missing_required"]) == []
    # And the summary is JSON-serializable as committed (the driver writes it).
    json.dumps(summary)
