"""Spec 0040 — AC4 unit: the resumable pilot ledger + STOP-AND-WARN preflight."""

from __future__ import annotations

import json

import pytest

from harpyja.eval.locate_probe import require_live_stack
from harpyja.eval.pool_pilot import (
    POOL_PILOT_LEDGER_SCHEMA_VERSION,
    PoolPilotLedger,
    PoolRunError,
    pool_pilot_preflight,
    run_pool_pilot,
)
from harpyja.eval.pool_precheck import (
    POOL_CONFIG_HASH_0040,
    PREREGISTERED_POOL_CONFIG_0040,
)

_CFG = PREREGISTERED_POOL_CONFIG_0040


def test_pool_pilot_ledger_resumes_completed_cells(tmp_path):
    path = tmp_path / "pilot_results.json"
    ledger = PoolPilotLedger(path, config_hash=POOL_CONFIG_HASH_0040)
    ledger.record("c1", "qwen3:14b", {"bucket": "correct", "degrade": None})
    # A fresh instance over the same path resumes the completed cell.
    resumed = PoolPilotLedger(path, config_hash=POOL_CONFIG_HASH_0040)
    assert resumed.has("c1", "qwen3:14b")
    assert not resumed.has("c1", "qwen3:8b")
    assert resumed.get("c1", "qwen3:14b")["bucket"] == "correct"
    # The persisted shape is the version-stamped, hash-pinned envelope.
    obj = json.loads(path.read_text(encoding="utf-8"))
    assert obj["schema_version"] == POOL_PILOT_LEDGER_SCHEMA_VERSION
    assert obj["config_hash"] == POOL_CONFIG_HASH_0040
    assert "c1::qwen3:14b" in obj["entries"]


def test_pool_pilot_ledger_schema_validates_loud(tmp_path):
    path = tmp_path / "pilot_results.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "9999/1",
                "config_hash": POOL_CONFIG_HASH_0040,
                "entries": {},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(PoolRunError, match="schema_version"):
        PoolPilotLedger(path, config_hash=POOL_CONFIG_HASH_0040)
    # A ledger written under a DIFFERENT frozen config is not resumable.
    path.write_text(
        json.dumps(
            {
                "schema_version": POOL_PILOT_LEDGER_SCHEMA_VERSION,
                "config_hash": "b" * 64,
                "entries": {},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(PoolRunError, match="different frozen config"):
        PoolPilotLedger(path, config_hash=POOL_CONFIG_HASH_0040)


def test_pool_pilot_preflight_stops_when_model_tag_unserved():
    with pytest.raises(PoolRunError, match="not served"):
        pool_pilot_preflight(
            _CFG,
            served_tags=["qwen3:14b"],
            pilot_models=["qwen3:14b", "qwen3:8b"],
        )
    # A model outside the pre-registered tag set STOPs even if served —
    # substitution under the frozen hash is the steering the freeze prevents.
    with pytest.raises(PoolRunError, match="not in the pre-registered"):
        pool_pilot_preflight(
            _CFG,
            served_tags=["qwen3-coder:30b"],
            pilot_models=["qwen3-coder:30b"],
        )
    ok = pool_pilot_preflight(
        _CFG,
        served_tags=list(_CFG.model_tags),
        pilot_models=list(_CFG.model_tags),
    )
    assert ok["models_served"] is True
    assert ok["explorer_think"] is None  # arm parity rides the frozen config


def test_cell_needs_run_bounded_retry_for_typed_degrades():
    from harpyja.eval.pool_pilot import _cell_needs_run

    # Absent cell → run.
    assert _cell_needs_run(None)
    # Clean bucket → NEVER re-run (re-running clean observations because an
    # outcome looks wrong would be post-hoc steering).
    assert not _cell_needs_run({"bucket": "empty", "degrade": None, "attempts": 1})
    # Typed degrade with attempts left → ONE bounded re-run (0036 posture).
    assert _cell_needs_run(
        {"bucket": None, "degrade": "no-trajectory: x", "attempts": 1}
    )
    # Degrade at the attempt cap → recorded-by-cause, excluded, never silent.
    assert not _cell_needs_run(
        {"bucket": None, "degrade": "no-trajectory: x", "attempts": 2}
    )
    # Legacy cell without attempts counts as one attempt.
    assert _cell_needs_run({"bucket": None, "degrade": "verifier:x"})


def test_cell_needs_run_suspect_reruns_only_after_clean_gate_check():
    """Spec 0041 (AC2): 'suspect' is a THIRD disposition — a cell invalidated
    outcome-blind at a contamination boundary. It is re-runnable ONLY after a
    subsequent clean gate check; clean cells still never re-run; typed
    degrades keep exactly one bounded re-run."""
    from harpyja.eval.pool_pilot import _cell_needs_run

    suspect = {"bucket": "correct", "degrade": None, "status": "suspect", "attempts": 1}
    # No clean gate check since the boundary → NOT re-runnable (do not fire
    # cells into a possibly-still-contended endpoint).
    assert not _cell_needs_run(suspect)
    assert not _cell_needs_run(suspect, clean_gate_since=False)
    # After a clean gate check the suspect cell is re-runnable.
    assert _cell_needs_run(suspect, clean_gate_since=True)
    # The other two branches are UNCHANGED by the flag: clean never re-runs...
    clean = {"bucket": "empty", "degrade": None, "attempts": 1}
    assert not _cell_needs_run(clean, clean_gate_since=True)
    # ...and typed degrades keep the one bounded re-run regardless of the flag.
    degraded = {"bucket": None, "degrade": "verifier:x", "attempts": 1}
    assert _cell_needs_run(degraded)
    assert _cell_needs_run(degraded, clean_gate_since=True)
    capped = {"bucket": None, "degrade": "verifier:x", "attempts": 2}
    assert not _cell_needs_run(capped, clean_gate_since=True)


def test_run_pool_pilot_refuses_without_live_flag(tmp_path):
    # The live loop is an operator entrypoint — never fired implicitly.
    with pytest.raises(PoolRunError, match="live=True"):
        run_pool_pilot(
            _CFG,
            out_dir=tmp_path / "artifacts",
            ledger_path=tmp_path / "ledger.json",
            pilot_models=list(_CFG.model_tags),
        )


def test_strict_run_skip_is_hard_fail():
    # Without the strict env an unavailable stack skips; under
    # HARPYJA_REQUIRE_LIVE_STACK the same condition is a hard FAIL.
    assert require_live_stack(False, env={}) == "skip"
    assert (
        require_live_stack(False, env={"HARPYJA_REQUIRE_LIVE_STACK": "1"}) == "fail"
    )


def test_evict_other_models_retained_as_defense_in_depth(monkeypatch):
    """Spec 0041 (AC4): the 0040 per-block eviction seam survives — the
    bounded-residency touch is the primary, eviction the defense-in-depth."""
    import contextlib
    import io

    from harpyja.eval.pool_pilot import _evict_other_models

    requests: list[tuple[str, dict | None]] = []

    def fake_urlopen(req, timeout=None):
        url = req if isinstance(req, str) else req.full_url
        body = None if isinstance(req, str) else req.data
        requests.append((url, json.loads(body) if body else None))
        if url.endswith("/api/ps"):
            payload = {"models": [{"name": "qwen3:14b"}, {"name": "qwen3:8b"}]}
            return contextlib.closing(io.BytesIO(json.dumps(payload).encode()))
        return contextlib.closing(io.BytesIO(b"{}"))

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    evicted = _evict_other_models("qwen3:14b", api_base="http://127.0.0.1:11434")
    assert evicted == ["qwen3:8b"]
    # The eviction is a native keep_alive:0 generate — never a /v1 field.
    evict_calls = [r for r in requests if r[0].endswith("/api/generate")]
    assert evict_calls == [
        (
            "http://127.0.0.1:11434/api/generate",
            {"model": "qwen3:8b", "keep_alive": 0},
        )
    ]


# ---- spec 0041: version-gated exclusivity proof on the run-level ledger (AC3) --


def _exclusivity_record() -> dict:
    from harpyja.eval.exclusivity_gate import build_exclusivity_record

    return build_exclusivity_record(
        checks=[
            {
                "label": "start",
                "timestamp": "2026-07-11T00:00:00+00:00",
                "clean": True,
                "residents": [],
                "foreign": [],
            }
        ],
        model_set=list(_CFG.model_tags),
    )


def test_pool_ledger_0041_version_requires_exclusivity_record(tmp_path):
    from harpyja.eval.pool_pilot import POOL_PILOT_LEDGER_SCHEMA_VERSION_0041

    assert POOL_PILOT_LEDGER_SCHEMA_VERSION_0041 == "0041/pilot/2"
    # A 0041/pilot/2 file WITHOUT the exclusivity proof is not a valid
    # measurement — the validator rejects on load.
    path = tmp_path / "ledger.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": POOL_PILOT_LEDGER_SCHEMA_VERSION_0041,
                "config_hash": POOL_CONFIG_HASH_0040,
                "entries": {},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(PoolRunError, match="exclusivity"):
        PoolPilotLedger(path, config_hash=POOL_CONFIG_HASH_0040)
    # Constructing new with a NON-CONFORMING record is equally loud.
    with pytest.raises(PoolRunError, match="exclusivity"):
        PoolPilotLedger(
            tmp_path / "fresh.json",
            config_hash=POOL_CONFIG_HASH_0040,
            exclusivity={"schema_version": "0041/exclusivity/1"},
        )


def test_pool_ledger_0041_version_accepts_full_exclusivity_record(tmp_path):
    from harpyja.eval.pool_pilot import POOL_PILOT_LEDGER_SCHEMA_VERSION_0041

    path = tmp_path / "ledger.json"
    record = _exclusivity_record()
    ledger = PoolPilotLedger(
        path, config_hash=POOL_CONFIG_HASH_0040, exclusivity=record
    )
    ledger.record("c1", "qwen3:14b", {"bucket": "correct", "degrade": None})
    obj = json.loads(path.read_text(encoding="utf-8"))
    assert obj["schema_version"] == POOL_PILOT_LEDGER_SCHEMA_VERSION_0041
    assert obj["exclusivity"] == record
    # Round-trips: a fresh instance resumes and carries the proof.
    resumed = PoolPilotLedger(path, config_hash=POOL_CONFIG_HASH_0040)
    assert resumed.exclusivity == record
    assert resumed.has("c1", "qwen3:14b")
    # Appending a per-block check re-persists the grown record.
    grown = dict(record)
    grown["checks"] = record["checks"] + [
        {
            "label": "pre-block:qwen3:8b",
            "timestamp": "2026-07-11T00:10:00+00:00",
            "clean": True,
            "residents": ["qwen3:8b"],
            "foreign": [],
        }
    ]
    resumed.set_exclusivity(grown)
    assert (
        json.loads(path.read_text(encoding="utf-8"))["exclusivity"] == grown
    )


def test_pool_ledger_legacy_0040_version_still_validates_without_exclusivity(
    tmp_path,
):
    # Both directions of the version gate: legacy 0040/pilot/1 artifacts load
    # unchanged (no exclusivity requirement), and a ledger built WITHOUT the
    # proof still writes/reads 0040/pilot/1 byte-shape — committed 0040
    # artifacts and tests stay green.
    path = tmp_path / "ledger.json"
    ledger = PoolPilotLedger(path, config_hash=POOL_CONFIG_HASH_0040)
    ledger.record("c1", "qwen3:14b", {"bucket": "correct", "degrade": None})
    obj = json.loads(path.read_text(encoding="utf-8"))
    assert obj["schema_version"] == POOL_PILOT_LEDGER_SCHEMA_VERSION
    assert "exclusivity" not in obj
    resumed = PoolPilotLedger(path, config_hash=POOL_CONFIG_HASH_0040)
    assert resumed.exclusivity is None
    assert resumed.has("c1", "qwen3:14b")
