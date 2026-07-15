"""Spec 0047 — the resumable, ledger-backed enlargement pipeline (package core).

The reusable orchestration the operator driver wraps: convert → author → tag → assemble
→ recheck, every out-of-process arm INJECTED (HF snapshot loader, Claude author, Codex
verifier, concept-labeler, span-text reader) so this module is pure of network/model I/O
and unit-testable end-to-end. The thin real-model entrypoint lives at
``specs/0047-enlargement/enlargement_run/run_enlargement.py`` (the 0046 reactive_run
split).

LOSSLESS RESUME: a JSON ledger records phase completion and per-case author/tag state; a
re-run skips completed phases and already-recorded cases, so a mid-author crash never
replays the ~130-case × 2-model authoring. Every drift/​integrity failure is a
``StopAndWarn`` (non-zero exit, ledger preserved) — never a partial commit.
"""

from __future__ import annotations

import dataclasses
import json
import sys
from collections.abc import Callable
from pathlib import Path

from harpyja.eval.enlargement import (
    EnlargementConfig,
    PowerRecheckResult,
    SamplingFrame,
    compute_power_recheck,
    power_recheck_payload,
    select_candidates,
)
from harpyja.eval.enlargement_authoring import (
    assemble_enlarged_authoring_artifact,
    assemble_enlarged_terse,
    audit_sample,
    author_enlarged_set,
    is_blind_ineligible,
    tag_enlarged_row,
)
from harpyja.eval.swebench_eval import (
    _to_eval_case,
    append_converted_cases,
    assert_pool_append_preserves_existing_labels,
    extend_provenance,
    line_sha_map,
    parse_patch,
)

Invoke = Callable[[str], str]
_TERSE_NAME = "swebench_verified.terse.jsonl"
_RAW_NAME = "swebench_verified.raw.jsonl"
_AUTHORING_NAME = "swebench_verified.authoring.json"
_PROVENANCE_NAME = "swebench_verified.provenance.json"


class StopAndWarn(RuntimeError):
    """A drift/integrity guard fired — stop loudly with the ledger preserved for resume."""


@dataclasses.dataclass(frozen=True)
class EnlargementDeps:
    """Everything the pipeline needs, with the out-of-process arms injected."""

    frame: SamplingFrame
    cfg: EnlargementConfig
    out_dir: Path
    ledger_path: Path
    existing_raw_rows: list[dict]
    existing_terse_rows: list[dict]
    existing_authoring: dict
    load_snapshot: Callable[[], tuple[str, list[dict]]]  # → (revision, hf_instance_rows)
    author_invoke: Invoke
    verifier_invoke: Invoke
    concept_label: Callable[[str, str, tuple[str, ...], str], str]  # → "same"|"divergent"
    read_span_text: Callable[[dict], str]
    author_model: str
    verifier_model: str
    concept_model: str
    effect_band: float = 0.1
    existing_provenance: dict = dataclasses.field(default_factory=dict)


class Ledger:
    """A resumable phase/per-case state file (append-only in spirit, atomic writes)."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.data: dict = {"phases": {}}
        if self.path.is_file():
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        self.data.setdefault("phases", {})

    def _save(self) -> None:
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(self.data, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(self.path)

    def phase(self, name: str) -> dict:
        return self.data["phases"].setdefault(name, {})

    def is_phase_done(self, name: str) -> bool:
        return bool(self.phase(name).get("done"))

    def finish_phase(self, name: str, payload: dict | None = None) -> None:
        p = self.phase(name)
        if payload:
            p.update(payload)
        p["done"] = True
        self._save()

    def get_case(self, name: str, case_id: str) -> dict | None:
        return self.phase(name).setdefault("cases", {}).get(case_id)

    def put_case(self, name: str, case_id: str, value: dict) -> None:
        self.phase(name).setdefault("cases", {})[case_id] = value
        self._save()


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    tmp.replace(path)


def _write_json(path: Path, payload: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


# ---- phases -------------------------------------------------------------------


def _phase_convert(deps: EnlargementDeps, ledger: Ledger) -> list[dict]:
    """T11: load the pinned snapshot, CONTENT-verify the pinned slice, select +
    audited-convert the new cases, and drift-guard the existing labels. Returns the
    NEW raw rows.

    Source-snapshot integrity is a CONTENT check, not a fingerprint check: the HF
    ``_fingerprint`` is an arrow-load hash that changes across ``datasets`` versions /
    cache state even for identical content, so it is recorded as provenance but never
    gates. The real invariant — the 50 already-pinned cases are byte-identical to the
    committed fixture (labels reused verbatim) — is asserted by re-deriving each pinned
    case from the freshly-loaded snapshot and comparing to the committed row."""
    revision, rows = deps.load_snapshot()
    _assert_pinned_slice_unchanged(deps, rows)
    if revision != deps.frame.hf_revision:
        print(
            f"[convert] NOTE: HF fingerprint {revision!r} != frozen "
            f"{deps.frame.hf_revision!r}, but the pinned slice is CONTENT-identical "
            "(benign arrow-fingerprint change); recording both.",
            file=sys.stderr,
        )
    selected, exclusions = select_candidates(
        rows, deps.cfg, already_pinned_ids=deps.frame.already_pinned_ids
    )
    new_rows: list[dict] = []
    for inst in selected:
        targets = parse_patch(inst["patch"])
        new_rows.append(_to_eval_case(inst, targets))
    merged = append_converted_cases(deps.existing_raw_rows, new_rows)
    # drift-guard: the committed labels must be byte-identical after the append.
    assert_pool_append_preserves_existing_labels(
        merged, line_sha_map(deps.existing_raw_rows)
    )
    raw_path = deps.out_dir / _RAW_NAME
    _write_jsonl(raw_path, merged)
    # AC1: extend the provenance chain (prior sha superseded but preserved).
    if deps.existing_provenance:
        updated_prov = extend_provenance(
            deps.existing_provenance,
            raw_path,
            new_ids=[r["case_id"] for r in new_rows],
            snapshot={"hf_revision": revision},
        )
        # Record the arrow-fingerprint pair as informational provenance (the gate is
        # the content check above, not this fingerprint).
        updated_prov["source_fingerprint_observed"] = revision
        updated_prov["source_fingerprint_frozen"] = deps.frame.hf_revision
        _write_json(deps.out_dir / _PROVENANCE_NAME, updated_prov)
    ledger.finish_phase(
        "convert",
        {
            "new_ids": [r["case_id"] for r in new_rows],
            "exclusion_counts": _count_reasons(exclusions),
        },
    )
    return new_rows


def _count_reasons(exclusions: list[tuple[str, str]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for _cid, reason in exclusions:
        out[reason] = out.get(reason, 0) + 1
    return out


def _assert_pinned_slice_unchanged(deps: EnlargementDeps, snapshot_rows: list[dict]) -> None:
    """The real source-snapshot integrity guard: re-derive each of the already-pinned
    cases from the freshly-loaded HF snapshot and assert it is byte-identical to the
    committed raw fixture. A missing pinned case (the slice shrank) or a re-derived
    mismatch (the slice's content changed, or the convert logic drifted) is a
    StopAndWarn — the committed 50 must be reusable VERBATIM or the whole chain is
    untrustworthy."""
    index = {r.get("instance_id"): r for r in snapshot_rows}
    committed = {r["case_id"]: r for r in deps.existing_raw_rows}
    for cid in deps.frame.already_pinned_ids:
        inst = index.get(cid)
        if inst is None:
            raise StopAndWarn(
                f"source snapshot drift: pinned case {cid!r} is ABSENT from the loaded "
                "HF snapshot — the committed slice cannot be reused verbatim"
            )
        rederived = _to_eval_case(inst, parse_patch(inst["patch"]))
        if rederived != committed.get(cid):
            raise StopAndWarn(
                f"source snapshot drift: pinned case {cid!r} re-derives DIFFERENTLY "
                "than the committed raw fixture — the source content (or the convert "
                "logic) changed; refusing to enlarge on a shifted foundation"
            )


def _phase_author(deps: EnlargementDeps, ledger: Ledger, new_rows: list[dict]) -> dict:
    """T13: blind-author each new case (skipping ledger-recorded ones), routing
    blind-ineligible + leaky to counted drops. Per-case ledger = lossless resume."""
    raw_by_id = {r["case_id"]: r for r in new_rows}
    for raw in new_rows:
        cid = raw["case_id"]
        if ledger.get_case("author", cid) is not None:
            continue
        if is_blind_ineligible(raw):
            ledger.put_case("author", cid, {"outcome": "blind-ineligible"})
            continue
        # author one case; author_enlarged_set over a single eligible case reuses the
        # frozen 0036 protocol (blindness asserted inside) and records provenance.
        cases, artifact, _ineligible = author_enlarged_set(
            [raw],
            author_invoke=deps.author_invoke,
            verifier_invoke=deps.verifier_invoke,
            author_model=deps.author_model,
            verifier_model=deps.verifier_model,
        )
        rec = artifact.records[0]
        entry = {
            "outcome": rec.outcome,
            "verifier_verdict": rec.verifier_verdict,
            "query": cases[0].query if cases else None,
            "record": _authoring_record_payload(rec),
        }
        ledger.put_case("author", cid, entry)

    # aggregate from the ledger (order-stable by new_rows)
    records: list[dict] = []
    leaky = dropped = ineligible = 0
    kept: list[dict] = []
    for raw in new_rows:
        entry = ledger.get_case("author", raw["case_id"])
        if entry["outcome"] == "blind-ineligible":
            ineligible += 1
            continue
        records.append(entry["record"])
        if entry["verifier_verdict"] == "leaky":
            leaky += 1
        if entry["outcome"] == "dropped":
            dropped += 1
        else:
            kept.append({"case_id": raw["case_id"], "raw": raw_by_id[raw["case_id"]],
                         "query": entry["query"]})
    ledger.finish_phase(
        "author",
        {"leaky": leaky, "dropped": dropped, "blind_ineligible": ineligible,
         "kept_ids": [k["case_id"] for k in kept]},
    )
    return {"records": records, "leaky": leaky, "dropped": dropped,
            "blind_ineligible": ineligible, "kept": kept}


def _authoring_record_payload(rec) -> dict:
    return {
        "case_id": rec.case_id,
        "author_model": rec.author_model,
        "verifier_model": rec.verifier_model,
        "author_input": rec.author_input,
        "author_input_hash": rec.author_input_hash,
        "verifier_input_hash": rec.verifier_input_hash,
        "verifier_verdict": rec.verifier_verdict,
        "outcome": rec.outcome,
    }


@dataclasses.dataclass(frozen=True)
class _Case:
    case_id: str
    query: str
    repo: str
    classification: str


def _phase_tag(deps: EnlargementDeps, ledger: Ledger, kept: list[dict]) -> list[dict]:
    """T15: reachability (DETERMINISTIC ``classify_reachability`` — the spec's
    load-bearing confound axis) + a substantiable concept-vs-patch tag, per kept case.

    concept-vs-patch: a ``divergent`` tag is only meaningful WITH a concept span DISTINCT
    from the gold patch, and locating that reliably needs a repo-aware pass the
    gold-span-text-only labeler cannot do. Fabricating ``concept_span = gold`` would be a
    self-contradiction (concept == patch IS "same"). So we tag the substantiable default
    ``same`` (no fabricated span) and KEEP the model's same/divergent opinion as ADVISORY
    provenance for a future repo-aware pass — never as a committed divergent label."""
    for k in kept:
        cid = k["case_id"]
        if ledger.get_case("tag", cid) is not None:
            continue
        raw = k["raw"]
        span_text = deps.read_span_text(raw)
        gold_paths = tuple(s["path"] for s in raw.get("expected_spans", []))
        advisory = deps.concept_label(cid, k["query"], gold_paths, span_text)
        case = _Case(cid, k["query"], str(raw["repo"]), raw.get("classification", "point"))
        row = tag_enlarged_row(case, span_text=span_text, concept_label="same")
        ledger.put_case("tag", cid, {"row": row, "concept_advisory": advisory})
    rows = [ledger.get_case("tag", k["case_id"])["row"] for k in kept]
    ledger.finish_phase("tag", {"tagged": len(rows)})
    return rows


def _phase_assemble(deps: EnlargementDeps, ledger: Ledger, new_terse: list[dict],
                    authoring: dict) -> None:
    """Assemble + commit the enlarged terse fixture (existing 19 drift-guarded) + the
    extended authoring artifact + the 20-case audit sample."""
    merged_terse = assemble_enlarged_terse(deps.existing_terse_rows, new_terse)
    _write_jsonl(deps.out_dir / _TERSE_NAME, merged_terse)
    _write_json(deps.out_dir / _AUTHORING_NAME, authoring)
    _write_json(deps.out_dir / "audit_sample.json", {"sample": audit_sample(new_terse, n=20)})
    ledger.finish_phase("assemble", {"terse_n": len(merged_terse)})


def _phase_recheck(deps: EnlargementDeps, ledger: Ledger, new_terse: list[dict],
                   author_result: dict) -> PowerRecheckResult:
    """T16/T17: compute the machine-readable power re-check from the enlarged tag +
    attrition counts and emit ``power_recheck.json``."""
    all_terse = assemble_enlarged_terse(deps.existing_terse_rows, new_terse)
    lexical_n = sum(1 for r in all_terse if r.get("reachability") == "lexical")
    conceptual_n = sum(1 for r in all_terse if r.get("reachability") == "conceptual")
    result = compute_power_recheck(
        deps.cfg,
        lexical_n=lexical_n,
        conceptual_n=conceptual_n,
        coverage=conceptual_n,
        leaky_count=author_result["leaky"],
        blind_ineligible_count=author_result["blind_ineligible"],
        dropped_count=author_result["dropped"],
        effect_band=deps.effect_band,
    )
    _write_json(deps.out_dir / "power_recheck.json", power_recheck_payload(result))
    ledger.finish_phase("recheck", {"conceptual_n": conceptual_n, "lexical_n": lexical_n})
    return result


def run_pipeline(deps: EnlargementDeps) -> PowerRecheckResult:
    """Run (or resume) the whole chain. Idempotent per phase via the ledger."""
    deps.out_dir.mkdir(parents=True, exist_ok=True)
    ledger = Ledger(deps.ledger_path)

    if ledger.is_phase_done("convert"):
        new_ids = set(ledger.phase("convert")["new_ids"])
        merged = _read_jsonl(deps.out_dir / _RAW_NAME)
        new_rows = [r for r in merged if r["case_id"] in new_ids]
    else:
        new_rows = _phase_convert(deps, ledger)

    author_result = _phase_author(deps, ledger, new_rows)
    new_terse = _phase_tag(deps, ledger, author_result["kept"])

    authoring = assemble_enlarged_authoring_artifact(
        deps.existing_authoring,
        _artifact_from_records(author_result),
        blind_ineligible_count=author_result["blind_ineligible"],
    )
    _phase_assemble(deps, ledger, new_terse, authoring)
    return _phase_recheck(deps, ledger, new_terse, author_result)


def _read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()
    ]


def _artifact_from_records(author_result: dict):
    """Rebuild an AuthoringArtifact from the ledger-recorded records (for assembly)."""
    from harpyja.eval.authoring_provenance import AuthoringArtifact, validate_authoring_record

    records = tuple(validate_authoring_record(r) for r in author_result["records"])
    return AuthoringArtifact(
        schema_version="0026/1",
        records=records,
        leaky_count=author_result["leaky"],
        dropped_count=author_result["dropped"],
    )
