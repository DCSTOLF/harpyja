"""Spec 0043 — budget attribution + the 4b inversion attributor (AC1, AC3).

Pure projections over PERSISTED trajectories — no model compute. Three
evidence-honesty rules govern everything here:

- The evidence base is machine-local, gitignored ``eval_work/`` (the committed
  ``specs/.archive`` artifacts are summaries): existence is asserted PER
  artifact, and a missing trajectory is the typed ``trajectory-missing``
  degrade — never a silent skip, never fabricated numbers.
- NO latency was ever recorded (verified: ``per_turn`` carries only
  ``{reasoning_chars, completion_tokens, finish_reason}``; the run ledger has
  no elapsed field; each artifact holds exactly one timestamp). Case timing is
  therefore ESTIMATE-GRADE ONLY — successive artifact-timestamp deltas, every
  value labeled ``grade: estimate`` (the 0021 rule) — and nothing this module
  emits claims a measured latency.
- ``per_turn`` and ``model_turns`` can differ in length (a ``finish=length``
  final turn enters ``per_turn`` but never the history): per-turn currencies
  are reported over the FULL ``per_turn`` list, history facts over the history
  — the two are NEVER zipped positionally.

The committed derived table pins every source artifact's filename + content
sha256, so the finding stays auditable after ``eval_work`` evaporates.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from harpyja.eval.metrics import Span, span_hit_kind
from harpyja.eval.submission_gap import _parse_tool_content

ATTRIBUTION_SCHEMA_VERSION = "0043/attribution/1"

# The typed per-cell degrade: the artifact this cell's attribution needs is
# not on disk (eval_work is machine-local) — recorded, never silently skipped.
TRAJECTORY_MISSING = "trajectory-missing"

# A model-unreachable degrade is the lm_http_timeout_s class (the 0040 lesson:
# HTTP timeouts were typed model-unreachable), distinct from the loop's own
# scout_wall_clock_s expiry.
_HTTP_TIMEOUT_MARKER = "model-unreachable"

# 4b-inversion attribution: a factor discriminates when the focal model's value
# exceeds the mean of its peers by this ratio. Below it, nothing in the
# persisted trajectories separates the candidates and the honest verdict is
# unattributable (the remaining candidate — serving behavior under load — is
# invisible to a trajectory by construction).
INVERSION_FACTOR = 1.5

_INVERSION_CAUSES = {
    "mean_turns": "more-turns",
    "mean_tool_result_bytes": "larger-tool-outputs",
    "mean_prompt_chars": "prompt-growth-prefill",
}

_MISSING_MEASUREMENT = (
    "per-request serving latency under load (instrumented re-run: per-turn "
    "wall-clock joined additively to per_turn)"
)


@dataclasses.dataclass(frozen=True)
class InversionFinding:
    """The AC3 verdict: a named cause, or the honest out with the missing
    measurement named (falsifiable, not a default escape)."""

    model: str
    cause: str
    missing_measurement: str | None


def attribute_case(
    trajectory: Mapping[str, Any],
    expected: Sequence[Span],
    *,
    max_turns: int,
    degrade: str | None = None,
) -> dict[str, Any]:
    """The per-case budget attribution over one persisted trajectory."""
    turns = trajectory.get("model_turns", [])

    assistant_turns = 0
    tool_call_count = 0
    turns_to_locate: int | None = None
    for turn in turns:
        role = turn.get("role")
        if role == "assistant":
            assistant_turns += 1
            tool_call_count += len(turn.get("tool_calls") or [])
        elif role == "tool" and turns_to_locate is None:
            spans, _decodable = _parse_tool_content(turn.get("content"))
            if any(
                span_hit_kind(s, e) == "line" for s in spans for e in expected
            ):
                turns_to_locate = assistant_turns

    per_turn = trajectory.get("per_turn") or []
    submitted = trajectory.get("citations_submitted")

    if degrade is not None and _HTTP_TIMEOUT_MARKER in degrade:
        terminal_cause = "http-timeout"
    elif isinstance(submitted, int) and submitted > 0:
        terminal_cause = "submitted"
    elif assistant_turns >= max_turns:
        terminal_cause = "turn-cap"
    else:
        terminal_cause = "wall-clock"

    return {
        "turns_to_locate": turns_to_locate,
        "turns_after_locate": (
            assistant_turns - turns_to_locate if turns_to_locate is not None else None
        ),
        "assistant_turns": assistant_turns,
        "tool_call_count": tool_call_count,
        # Full per_turn list — deliberately NOT zipped against history.
        "reasoning_chars_per_turn": [t.get("reasoning_chars") for t in per_turn],
        "completion_tokens_per_turn": [t.get("completion_tokens") for t in per_turn],
        "finish_reasons": [t.get("finish_reason") for t in per_turn],
        "terminal_cause": terminal_cause,
    }


def attribute_cell(
    artifact_path: Path,
    expected: Sequence[Span],
    *,
    max_turns: int = 12,
    degrade: str | None = None,
) -> dict[str, Any]:
    """Existence-assert FIRST, then attribute — a missing artifact is the typed
    ``trajectory-missing`` degrade carrying no fabricated numbers."""
    path = Path(artifact_path)
    if not path.is_file():
        return {"degrade": TRAJECTORY_MISSING, "source_path": str(path)}
    trajectory = json.loads(path.read_text())
    record = attribute_case(trajectory, expected, max_turns=max_turns, degrade=degrade)
    record["degrade"] = None
    record["source_path"] = str(path)
    return record


def case_timing_estimates(
    entries: Sequence[tuple[str, str]],
) -> dict[str, dict[str, Any]]:
    """ESTIMATE-GRADE case timing: successive verifier-artifact timestamp
    deltas within one sequential run block. The first case has no predecessor
    (``seconds: None``); every value is labeled ``grade: estimate`` (0021)."""
    out: dict[str, dict[str, Any]] = {}
    prev: datetime | None = None
    for case_id, stamp in entries:
        now = datetime.fromisoformat(stamp)
        seconds = (now - prev).total_seconds() if prev is not None else None
        out[case_id] = {"seconds": seconds, "grade": "estimate"}
        prev = now
    return out


def attribute_inversion(
    evidence_by_model: Mapping[str, Mapping[str, Any]],
) -> InversionFinding:
    """AC3: attribute the heavy-repo degrade inversion from persisted evidence.

    The focal model is the one carrying the most degrades. Each candidate
    factor discriminates only when the focal value exceeds the peer mean by
    ``INVERSION_FACTOR``; the largest-ratio discriminating factor is the named
    cause. When NOTHING in the trajectories discriminates, the remaining
    candidate (serving behavior under load) is structurally invisible to a
    trajectory — the verdict is the honest out with the missing measurement
    named, never a guessed cause.
    """
    focal = max(evidence_by_model, key=lambda m: evidence_by_model[m]["degrade_count"])
    peers = [m for m in evidence_by_model if m != focal]

    best_cause: str | None = None
    best_ratio = 0.0
    for factor, cause in _INVERSION_CAUSES.items():
        focal_value = evidence_by_model[focal].get(factor)
        peer_values = [
            evidence_by_model[m][factor]
            for m in peers
            if evidence_by_model[m].get(factor) is not None
        ]
        if focal_value is None or not peer_values:
            continue
        peer_mean = sum(peer_values) / len(peer_values)
        if peer_mean <= 0:
            continue
        ratio = focal_value / peer_mean
        if ratio >= INVERSION_FACTOR and ratio > best_ratio:
            best_cause, best_ratio = cause, ratio

    if best_cause is not None:
        return InversionFinding(model=focal, cause=best_cause, missing_measurement=None)
    return InversionFinding(
        model=focal,
        cause="unattributable-needs-instrumented-rerun",
        missing_measurement=_MISSING_MEASUREMENT,
    )


def build_attribution_table(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Serialize the COMMITTED derived table, each source pinned by filename +
    content sha256 — durable after the gitignored ``eval_work`` evaporates."""
    sources = []
    cases = []
    for row in rows:
        path = Path(row["source_path"])
        sources.append({
            "filename": path.name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        })
        cases.append({
            "case": row["case"],
            "model": row["model"],
            **dict(row["record"]),
        })
    return {
        "schema_version": ATTRIBUTION_SCHEMA_VERSION,
        "timing_grade": "estimate",
        "sources": sources,
        "cases": cases,
    }
