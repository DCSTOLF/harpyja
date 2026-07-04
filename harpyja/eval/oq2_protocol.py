"""Spec 0020 — the sequential OQ2 operator protocol driver (G0→G1→G2→G3).

Four stop-and-report gates, each recorded before the next is entered. The driver is
pure orchestration over injected collaborators (preflight / provision / G1 / G2 / G3),
so it is fully unit-testable with fakes and does no I/O of its own except the final
gate-ledger write (delegated to `oq2_ledger.write_gate_ledger`). It measures the frozen
SUT; it never mutates it.

Terminal dispositions:
- **hold / BLOCKED** — an *environment* problem that is not a SUT finding: G0 preflight
  fail (a required model not pulled), fixtures absent, or a G1 sub-check-(a)
  non-completion for an environment reason (OOM / resource exhaustion). Names the fix.
- **close** — a recorded outcome that *observed* the SUT: `STOP:SMOKE` (G1 completed
  then degrade-dominated or gate-false-rejected a correct citation) or a G3 label
  (`RECOMMENDATION` / `GATE_CONFOUNDED` / `DEGRADED_DOMINATED` / `NOT_SEPARABLE`).

The close/hold split is drawn BY CAUSE (D7), not by which gate stopped.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

from harpyja.eval.config import EvalConfig
from harpyja.eval.oq2_classify import classify_g3_outcome
from harpyja.eval.oq2_ledger import build_gate_ledger, write_gate_ledger
from harpyja.eval.recommend import Recommendation
from harpyja.eval.swebench_eval import (
    PreflightError,
    _required_model_tags,
    preflight_models_present,
)

# --------------------------------------------------------------------------- #
# collaborator result types (injected fakes in unit tests; live wiring in T19)
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class ProvisionInfo:
    """What `provision()` yields once the fixtures resolve (or `None` if absent)."""

    fixture_subset_id: str
    effective_n: int


@dataclass(frozen=True)
class G1Result:
    """The astropy-12907 single-case smoke outcome (three sub-checks).

    `environment_failure` is only meaningful when `completed is False`: it distinguishes
    an OOM / resource non-completion (→ BLOCKED hold) from a genuine SUT crash.
    """

    completed: bool
    environment_failure: bool = False
    degrade_dominant: bool = False
    correct_citation_false_rejected: bool = False
    measured: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class G2Result:
    """Point-subset gate-quality metrics + the instruct-vs-finder A/B."""

    instruct_false_escalation: float | None
    finder_false_escalation: float | None
    catch_rate: float | None


@dataclass(frozen=True)
class G3Result:
    """The sweep (or single descriptive pass) outputs handed to the projection."""

    recommendation: Recommendation
    aggregate: Mapping[str, object]  # must carry `degraded_dominated`
    descriptive: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class GateVerdict:
    gate: str
    status: str
    detail: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ProtocolResult:
    disposition: str  # "close" | "hold"
    outcome: str
    gates: list[GateVerdict]
    g3: object | None  # G3Classification | None
    ledger: dict


def _verdict_dict(v: GateVerdict) -> dict:
    return {"gate": v.gate, "status": v.status, **v.detail}


def run_oq2_protocol(
    *,
    settings,
    eval_config: EvalConfig,
    tags_payload: Mapping[str, object],
    provenance_base: Mapping[str, object],
    provision: Callable[[], ProvisionInfo | None],
    run_g1: Callable[[object, EvalConfig], G1Result],
    run_g2: Callable[[object, EvalConfig], G2Result],
    run_g3: Callable[..., G3Result],
    preflight: Callable[..., list[str]] = preflight_models_present,
    verdict_sink: Callable[[GateVerdict], None] | None = None,
    out_dir=None,
    repo_path=None,
    write: bool = False,
) -> ProtocolResult:
    """Run the four gates in order, stop-and-report, and emit a `0020/1` gate-ledger."""
    gates: list[GateVerdict] = []

    def commit(v: GateVerdict) -> None:
        gates.append(v)
        if verdict_sink is not None:
            verdict_sink(v)

    def finish(
        disposition: str, outcome: str, g3=None, *, fixture_subset_id=None
    ) -> ProtocolResult:
        provenance = {
            **dict(provenance_base),
            "eval_config": dataclasses.asdict(eval_config),
            "fixture_subset_id": fixture_subset_id,
        }
        ledger = build_gate_ledger(
            disposition=disposition,
            outcome=outcome,
            gates=[_verdict_dict(v) for v in gates],
            g3=g3,
            provenance=provenance,
        )
        if write:
            if out_dir is None or repo_path is None:
                raise ValueError("write=True requires out_dir and repo_path")
            write_gate_ledger(ledger, out_dir=out_dir, repo_path=repo_path)
        return ProtocolResult(disposition, outcome, gates, g3, ledger)

    # ---- G0: preflight (assert models pulled BEFORE provisioning) -----------
    try:
        pulled = preflight(settings, tags_payload)
    except PreflightError as err:
        served = {m.get("name") for m in (tags_payload or {}).get("models", [])}
        missing = [t for t in _required_model_tags(settings) if t not in served]
        commit(GateVerdict("G0", "blocked", {
            "missing": missing,
            "remediation": "ollama pull " + " ".join(missing),
            "cause": str(err),
        }))
        return finish("hold", "BLOCKED")
    commit(GateVerdict("G0", "pass", {"pulled": list(pulled)}))

    # ---- provision (the clone; fixtures absent is an environment hold) ------
    info = provision()
    if info is None:
        return finish("hold", "BLOCKED")
    fixture_subset_id = info.fixture_subset_id

    # ---- G1: single-case smoke (astropy-12907), non-completion by cause -----
    g1 = run_g1(settings, eval_config)
    measured = dict(g1.measured)
    if not g1.completed:
        if g1.environment_failure:  # OOM / resource — an environment hold, not a finding
            commit(GateVerdict("G1", "blocked", {"cause": "environment", "measured": measured}))
            return finish("hold", "BLOCKED", fixture_subset_id=fixture_subset_id)
        commit(GateVerdict("G1", "stop", {"subcheck": "completed", "measured": measured}))
        return finish("close", "STOP:SMOKE", fixture_subset_id=fixture_subset_id)
    if g1.degrade_dominant:
        commit(GateVerdict("G1", "stop", {"subcheck": "degrade_dominant", "measured": measured}))
        return finish("close", "STOP:SMOKE", fixture_subset_id=fixture_subset_id)
    if g1.correct_citation_false_rejected:
        commit(GateVerdict("G1", "stop", {"subcheck": "false_rejected", "measured": measured}))
        return finish("close", "STOP:SMOKE", fixture_subset_id=fixture_subset_id)
    commit(GateVerdict("G1", "pass", {"measured": measured}))

    # ---- G2: gate quality; over-ceiling records but never aborts ------------
    g2 = run_g2(settings, eval_config)
    ceiling = eval_config.gate_false_escalation_ceiling
    instruct = g2.instruct_false_escalation
    over_ceiling = instruct is not None and instruct > ceiling
    finder_beats_instruct = (
        instruct is not None
        and g2.finder_false_escalation is not None
        and g2.finder_false_escalation < instruct
    )
    commit(GateVerdict("G2", "over-ceiling" if over_ceiling else "pass", {
        "gate_false_escalation_instruct": instruct,
        "gate_false_escalation_scout": g2.finder_false_escalation,
        "catch_rate": g2.catch_rate,
        "over_ceiling": over_ceiling,
        "finder_beats_instruct": finder_beats_instruct,
    }))

    # ---- G3: sweep (or descriptive-only under confound) → classify ----------
    g3r = run_g3(settings, eval_config, descriptive_only=over_ceiling)
    aggregate = {**dict(g3r.aggregate), "effective_n": info.effective_n}
    classification = classify_g3_outcome(g3r.recommendation, aggregate, eval_config)
    commit(GateVerdict("G3", "complete", {
        "label": classification.label,
        "descriptive_only": over_ceiling,
        "descriptive": dict(g3r.descriptive),
    }))
    return finish(
        "close", classification.label, g3=classification, fixture_subset_id=fixture_subset_id
    )
