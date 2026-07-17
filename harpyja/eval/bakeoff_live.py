"""Spec 0048 — bake-off: the live SUT seams for the operator run (T22).

Maps a ``live_verifier`` artifact → the durable bake-off artifact, and builds the
``CellRunner`` / ``PreflightProber`` the driver consumes. The explorer path is run
UNCHANGED (``explorer_think=None`` ⇒ the 0034/0038 ``{max_tokens: 2048}`` byte-pin
holds); the frozen decoding (``temperature=0``/``top_p=1``/``seed``) is RECORDED
intent + server-side greedy, VERIFIED by the reproducibility replay probe — never
injected into the explorer's outbound params (that would be a SUT change the
measurement invariant forbids). Factories do no I/O at construction, so this
module imports without a live stack.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from harpyja.eval.bakeoff_config import BakeoffConfig
from harpyja.eval.bakeoff_driver import CellRunner, PreflightProber
from harpyja.eval.bakeoff_run import (
    BakeoffPreflightObservations,
    BakeoffRunError,
    build_bakeoff_artifact,
    reproducibility_replay_probe,
)
from harpyja.eval.locate_accuracy import LocateBucket

__all__ = [
    "bakeoff_artifact_from_verifier",
    "make_live_cell_runner",
    "make_live_preflight_prober",
]

# The heavy-repo timeout degrade class (0043) — a coverage cap, not a capability
# signal; watched at scale per the reliability invariant.
_HEAVY_REPO_DEGRADE_MARKERS = ("wall-clock", "timeout")


def _tool_call_counts(verifier_artifact: Mapping[str, Any]) -> dict[str, int]:
    """Per-tool call counts from ``model_turns`` (authoritative — the tools live in
    the turn ``tool_calls``). Falls back to the top-level ``tool_names_invoked`` list
    (one each) only when no turns are present, so the count is never fabricated."""
    counts: dict[str, int] = {}
    saw_turn_tool_call = False
    for turn in verifier_artifact.get("model_turns") or []:
        if not isinstance(turn, dict):
            continue
        for call in turn.get("tool_calls") or []:
            name = (call.get("function") or {}).get("name")
            if name:
                counts[name] = counts.get(name, 0) + 1
                saw_turn_tool_call = True
    if not saw_turn_tool_call:
        for name in verifier_artifact.get("tool_names_invoked") or []:
            counts[name] = counts.get(name, 0) + 1
    return counts


def _reasoning_tokens(verifier_artifact: Mapping[str, Any]) -> int:
    """Sum per-turn reasoning tokens where the trajectory recorded them (0034);
    honest 0 when absent — never fabricated."""
    direct = verifier_artifact.get("reasoning_tokens")
    if isinstance(direct, int):
        return direct
    total = 0
    for turn in verifier_artifact.get("per_turn") or []:
        rt = turn.get("reasoning_tokens") if isinstance(turn, dict) else None
        if isinstance(rt, int):
            total += rt
    return total


def bakeoff_artifact_from_verifier(
    cfg: BakeoffConfig,
    *,
    case_id: str,
    model: str,
    verifier_artifact: Mapping[str, Any],
    sut_hash: str,
    exclusivity_record: Mapping[str, Any],
) -> dict[str, Any]:
    """PURE map from a persisted ``live_verifier`` artifact → the bake-off artifact
    (via ``build_bakeoff_artifact``). Reads only fields the verifier records; a
    degrade yields ``bucket=None`` (never a fabricated EMPTY)."""
    raw_bucket = verifier_artifact.get("terminal_bucket")
    bucket = LocateBucket(raw_bucket) if raw_bucket else None

    # The top-level ``tool_names_invoked`` field is often None even when tools WERE
    # called (the verifier writes the tools in ``model_turns`` but does not always
    # populate the convenience field — observed live). Derive per-tool call counts
    # from ``model_turns`` directly, cross-checked against the committed
    # ``extract_tool_names`` oracle, so symbols-adoption (0042 / AC6) is never
    # silently zeroed by a null convenience field.
    tools = _tool_call_counts(verifier_artifact)
    symbols_adopted = tools.get("symbols", 0) > 0

    submitted = bool(verifier_artifact.get("citations_submitted") or 0)
    surviving = bool(verifier_artifact.get("citations_surviving") or 0)
    found_but_unsubmitted = verifier_artifact.get("submission_outcome") == "found-unsubmitted"

    degrade = verifier_artifact.get("degrade")
    heavy_repo_degrade = degrade is not None and any(
        marker in degrade for marker in _HEAVY_REPO_DEGRADE_MARKERS
    )

    return build_bakeoff_artifact(
        cfg, case_id=case_id, model=model, bucket=bucket, tools=tools,
        symbols_adopted=symbols_adopted,
        reasoning_tokens=_reasoning_tokens(verifier_artifact),
        submitted=submitted, surviving=surviving,
        found_but_unsubmitted=found_but_unsubmitted,
        serving_transport=verifier_artifact.get("serving_transport"),
        sut_hash=sut_hash, exclusivity_record=exclusivity_record,
        heavy_repo_degrade=heavy_repo_degrade, degrade=degrade,
    )


def _settings_for(cfg: BakeoffConfig, *, api_base: str, model: str):
    """The frozen per-cell Settings — arms-parity ``explorer_think=None`` (the
    byte-pin holds), the shipped turn/wall-clock/timeout knobs. Decoding is NOT
    set here (it would break the explorer param byte-pin); greedy is a server-side
    precondition the replay probe verifies."""
    import dataclasses

    from harpyja.config.settings import Settings

    return dataclasses.replace(
        Settings(),
        lm_api_base=f"{api_base}/v1",
        lm_model=model,
        explorer_think=cfg.explorer_think,
    )


def make_live_cell_runner(
    cfg: BakeoffConfig,
    *,
    api_base: str,
    out_dir: str | Path,
    cases_by_id: Mapping[str, Mapping[str, Any]],
    worktrees_root: str | Path,
    sut_hash: str,
    exclusivity_record: Mapping[str, Any],
) -> CellRunner:
    """Build the real per-cell runner: ``run_verified_case`` under the frozen
    knobs, mapped to the bake-off artifact. ``cases_by_id`` carries per-case
    ``gold`` + ``query``; worktrees are provisioned by the operator."""
    out_dir = Path(out_dir)
    worktrees_root = Path(worktrees_root)

    def runner(case_id: str, model: str) -> Mapping[str, Any]:
        import json

        from harpyja.eval.live_verifier import run_verified_case
        from harpyja.gateway.gateway import ModelGateway

        case = cases_by_id[case_id]
        if case.get("gold") is None:
            # A blind-withheld gold that the operator did not supply is a loud
            # missing-input — never a silent skip or a fabricated span.
            raise BakeoffRunError(
                f"case {case_id!r} has no gold span (blind-withheld) — supply the "
                "audited gold before the live run; the cell cannot be scored without it"
            )
        settings = _settings_for(cfg, api_base=api_base, model=model)
        gateway = ModelGateway(api_base=settings.lm_api_base, model=settings.lm_model)
        model_dir = out_dir / model.replace(":", "_").replace(".", "_")
        _result, artifact_path = run_verified_case(
            case_name=case_id, settings=settings, gateway=gateway,
            gold_span=case["gold"], out_dir=model_dir,
            repo_path=str(worktrees_root / case_id), query=case["query"],
        )
        verifier_artifact = json.loads(Path(artifact_path).read_text(encoding="utf-8"))
        return bakeoff_artifact_from_verifier(
            cfg, case_id=case_id, model=model, verifier_artifact=verifier_artifact,
            sut_hash=sut_hash, exclusivity_record=exclusivity_record,
        )

    return runner


def make_live_preflight_prober(
    cfg: BakeoffConfig,
    *,
    served_tags: Sequence[str],
    replay_cases: Sequence[str],
    coherence_probe: Callable[[str], tuple[bool, bool]],
    replay_cell: Callable[[str, str, int], LocateBucket],
) -> PreflightProber:
    """Build the per-model preflight prober: served membership (from the positive
    ``/api/tags`` set), a coherence + ``/v1`` tool-calling probe, and the
    reproducibility replay over ``replay_cases`` (≥3 conceptual). A non-served
    model short-circuits (no probe calls)."""
    served = set(served_tags)

    def prober(tag: str) -> BakeoffPreflightObservations:
        if tag not in served:
            return BakeoffPreflightObservations(False, False, False, "unserved")
        coherent, tool_calls_clean = coherence_probe(tag)
        if not (coherent and tool_calls_clean):
            return BakeoffPreflightObservations(True, coherent, tool_calls_clean, "unrun")
        replay = reproducibility_replay_probe(
            lambda cid, ix: replay_cell(tag, cid, ix), replay_cases
        )
        return BakeoffPreflightObservations(True, True, True, replay)

    return prober
