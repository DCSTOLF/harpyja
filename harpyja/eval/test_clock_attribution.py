"""Spec 0043 T5 — budget attribution + the 4b inversion attributor (AC1, AC3).

Pure projections over PERSISTED trajectories (no model compute). The evidence
base is machine-local and gitignored (`eval_work/`), so: existence is asserted
per artifact (`trajectory-missing` is a typed degrade, never a silent skip),
timing is ESTIMATE-GRADE only (no latency field was ever recorded — verified),
and the committed derived table pins source filenames + content hashes.
"""

import hashlib
import json

from harpyja.eval.clock_attribution import (
    TRAJECTORY_MISSING,
    InversionFinding,
    attribute_case,
    attribute_cell,
    attribute_inversion,
    build_attribution_table,
    case_timing_estimates,
)
from harpyja.server.types import CodeSpan

GOLD = (CodeSpan(path="pkg/mod.py", start_line=10, end_line=20),)

_HIT = (
    "[CodeSpan(path='pkg/mod.py', start_line=12, end_line=15, "
    "symbol='f', language='python', kind='function')]"
)
_MISS = (
    "[CodeSpan(path='pkg/other.py', start_line=1, end_line=2, "
    "symbol=None, language=None, kind=None)]"
)


def _turns(tool_contents):
    turns = [{"role": "user", "content": "locate"}]
    for content in tool_contents:
        turns.append({
            "role": "assistant",
            "content": "",
            "tool_calls": [{"function": {"name": "grep", "arguments": "{}"}}],
        })
        turns.append({"role": "tool", "content": content})
    return turns


def _traj(tool_contents, *, per_turn=None, submitted=None, surviving=None):
    return {
        "model_turns": _turns(tool_contents),
        "per_turn": per_turn or [],
        "citations_submitted": submitted,
        "citations_surviving": surviving,
        "timestamp": "2026-07-11T10:00:00",
    }


def test_attribution_asserts_per_artifact_existence_first(tmp_path):
    """A missing trajectory is the TYPED degrade, never a silent skip."""
    present = tmp_path / "a_verifier_artifact.json"
    present.write_text(json.dumps(_traj([_MISS])))
    missing = tmp_path / "b_verifier_artifact.json"  # never written

    ok = attribute_cell(present, GOLD)
    assert ok.get("degrade") is None

    gone = attribute_cell(missing, GOLD)
    assert gone["degrade"] == TRAJECTORY_MISSING == "trajectory-missing"
    # A degraded cell carries NO attribution numbers (nothing fabricated).
    assert "turns_to_locate" not in gone


def test_per_case_attribution_fields():
    """The per-case record carries exactly the recorded currencies."""
    pt = [
        {"reasoning_chars": 100, "completion_tokens": 40, "finish_reason": "tool_calls"},
        {"reasoning_chars": 900, "completion_tokens": 80, "finish_reason": "tool_calls"},
        {"reasoning_chars": 50, "completion_tokens": 10, "finish_reason": "stop"},
    ]
    rec = attribute_case(_traj([_MISS, _HIT, _MISS], per_turn=pt), GOLD, max_turns=12)

    assert rec["turns_to_locate"] == 2       # hit arrived on the 2nd tool result
    assert rec["turns_after_locate"] == 1    # one assistant turn after the hit
    assert rec["tool_call_count"] == 3
    assert rec["reasoning_chars_per_turn"] == [100, 900, 50]
    assert rec["completion_tokens_per_turn"] == [40, 80, 10]
    assert rec["finish_reasons"] == ["tool_calls", "tool_calls", "stop"]
    # Never located: both locate fields are honest Nones.
    rec2 = attribute_case(_traj([_MISS]), GOLD, max_turns=12)
    assert rec2["turns_to_locate"] is None
    assert rec2["turns_after_locate"] is None


def test_terminal_cause_is_typed():
    """wall-clock / http-timeout / turn-cap / submitted, mechanically derived."""
    # Submitted wins when counts say so.
    rec = attribute_case(_traj([_HIT], submitted=1, surviving=1), GOLD, max_turns=12)
    assert rec["terminal_cause"] == "submitted"
    # A model-unreachable degrade (the 300s HTTP timeout class) is http-timeout.
    rec = attribute_case(
        _traj([_MISS]), GOLD, max_turns=12,
        degrade="no-trajectory: Explorer did not capture trajectory "
                "(scout cause: model-unreachable)",
    )
    assert rec["terminal_cause"] == "http-timeout"
    # At the cap with no submission: turn-cap.
    rec = attribute_case(_traj([_MISS] * 12), GOLD, max_turns=12)
    assert rec["terminal_cause"] == "turn-cap"
    # Ended below the cap, unsubmitted: the wall-clock ceiling expired the loop.
    rec = attribute_case(_traj([_MISS] * 3), GOLD, max_turns=12)
    assert rec["terminal_cause"] == "wall-clock"


def test_attribution_never_zips_per_turn_and_model_turns():
    """The 0034 length skew: a finish=length final turn exists in per_turn but
    not in history — the attributor reports the FULL per_turn list and never
    aligns the two lists positionally."""
    pt = [
        {"reasoning_chars": 10, "completion_tokens": 5, "finish_reason": "tool_calls"},
        {"reasoning_chars": 20, "completion_tokens": 9, "finish_reason": "tool_calls"},
        {"reasoning_chars": 9999, "completion_tokens": 2048, "finish_reason": "length"},
    ]
    # 2 assistant turns in history, 3 per_turn entries — must not crash.
    rec = attribute_case(_traj([_MISS, _MISS], per_turn=pt), GOLD, max_turns=12)
    assert len(rec["reasoning_chars_per_turn"]) == 3   # full per_turn, not zipped
    assert rec["finish_reasons"][-1] == "length"
    assert rec["tool_call_count"] == 2                 # history counts stay history's


def test_case_timing_is_estimate_grade_labeled():
    """Case timing = successive artifact timestamp deltas, LABELED an estimate
    (0021) — no latency field exists to read."""
    est = case_timing_estimates([
        ("case-a", "2026-07-11T10:00:00"),
        ("case-b", "2026-07-11T10:03:20"),
        ("case-c", "2026-07-11T10:04:20"),
    ])
    assert est["case-a"] == {"seconds": None, "grade": "estimate"}  # no predecessor
    assert est["case-b"] == {"seconds": 200.0, "grade": "estimate"}
    assert est["case-c"] == {"seconds": 60.0, "grade": "estimate"}
    assert all(v["grade"] == "estimate" for v in est.values())


def test_no_measured_latency_field_anywhere():
    """The attributor never claims a measured latency — the only timing it
    emits rides under the estimate label."""
    rec = attribute_case(_traj([_HIT]), GOLD, max_turns=12)
    assert "latency" not in json.dumps(rec)
    assert "measured" not in json.dumps(rec)


def test_4b_inversion_attributor_names_cause_or_unattributable():
    """AC3: a named cause when the persisted evidence discriminates; otherwise
    the honest UNATTRIBUTABLE out WITH the specific missing measurement named."""
    # 4b runs far more turns than its peers → the evidence names more-turns.
    finding = attribute_inversion({
        "qwen3.5:4b": {"degrade_count": 3, "mean_turns": 11.0,
                       "mean_tool_result_bytes": 2000.0},
        "qwen3:8b": {"degrade_count": 1, "mean_turns": 5.0,
                     "mean_tool_result_bytes": 2100.0},
        "qwen3:14b": {"degrade_count": 1, "mean_turns": 5.5,
                      "mean_tool_result_bytes": 1900.0},
    })
    assert isinstance(finding, InversionFinding)
    assert finding.model == "qwen3.5:4b"
    assert finding.cause == "more-turns"
    assert finding.missing_measurement is None

    # Nothing in the trajectories discriminates → serving behavior is the
    # remaining candidate, which trajectories CANNOT show: unattributable,
    # with the missing measurement named (falsifiable, not a default escape).
    finding = attribute_inversion({
        "qwen3.5:4b": {"degrade_count": 3, "mean_turns": 5.0,
                       "mean_tool_result_bytes": 2000.0},
        "qwen3:8b": {"degrade_count": 1, "mean_turns": 5.0,
                     "mean_tool_result_bytes": 2100.0},
        "qwen3:14b": {"degrade_count": 1, "mean_turns": 5.5,
                      "mean_tool_result_bytes": 1900.0},
    })
    assert finding.cause == "unattributable-needs-instrumented-rerun"
    assert finding.missing_measurement  # named, non-empty


def test_derived_table_pins_source_artifact_filenames_and_hashes(tmp_path):
    """The COMMITTED table survives eval_work evaporating: every source
    artifact is pinned by filename + content sha256."""
    src = tmp_path / "case-a_verifier_artifact.json"
    payload = json.dumps(_traj([_HIT]))
    src.write_text(payload)

    table = build_attribution_table(
        [{"case": "case-a", "model": "qwen3:14b", "source_path": src,
          "record": attribute_case(_traj([_HIT]), GOLD, max_turns=12)}]
    )
    assert table["schema_version"] == "0043/attribution/1"
    (pin,) = table["sources"]
    assert pin["filename"] == "case-a_verifier_artifact.json"
    assert pin["sha256"] == hashlib.sha256(payload.encode()).hexdigest()
    assert table["timing_grade"] == "estimate"
    (case_row,) = table["cases"]
    assert case_row["case"] == "case-a"
    assert case_row["model"] == "qwen3:14b"
