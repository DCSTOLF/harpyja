"""Spec 0048 — bake-off: the integration wiring.

AC1 preflight (assert-local-first → positive ``/api/tags`` membership → coherence
+ ``/v1`` tool-calling → reproducibility replay), AC2 resumable ledger + durable
per model+case artifact (mirroring ``think_ab_run.AbLedger`` and reusing the 0041
``exclusivity_gate`` proof), and the AC4/AC5/AC6 report assembly over the pure
``bakeoff_analysis`` core. The harness NEVER mutates the SUT.
"""

from __future__ import annotations

import enum
import json
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from harpyja.eval.bakeoff_analysis import (
    BakeoffReport,
    ModelExclusion,
    PairResult,
    assemble_bakeoff,
    decide_pair_outcome,
    discordant_counts,
    holm_adjusted_pvalues,
    holm_rejections,
    lexical_descriptive_stats,
    mcnemar_exact_p,
    per_repo_bc_distribution,
    split_by_reachability,
)
from harpyja.eval.bakeoff_config import BakeoffConfig
from harpyja.eval.locate_accuracy import LocateBucket

__all__ = [
    "BAKEOFF_LEDGER_SCHEMA_VERSION",
    "BakeoffLedger",
    "BakeoffPreflightObservations",
    "BakeoffPreflightOutcome",
    "BakeoffRunError",
    "adjudicate_bakeoff_preflight",
    "bakeoff_preflight",
    "build_bakeoff_artifact",
    "build_bakeoff_report",
    "probe_served_membership",
    "probe_served_variant_membership",
    "reproducibility_replay_probe",
]

BAKEOFF_LEDGER_SCHEMA_VERSION = "0048/1"
_KNOWN_LEDGER_SCHEMA_VERSIONS = frozenset({BAKEOFF_LEDGER_SCHEMA_VERSION})


class BakeoffRunError(ValueError):
    """A run precondition or ledger that does not conform — loud, never defaulted."""


# ---- AC1 preflight -----------------------------------------------------------


class BakeoffPreflightOutcome(enum.Enum):
    """The committed per-model preflight answer space. Every non-pass member
    EXCLUDES (no THINK_CONTROL_NOOP — ``explorer_think`` is fixed None, no thinking
    arm). REPLAY_FAIL is the 0048 addition: a batched backend that is not
    bit-reproducible at temp=0 yields a single-draw stochastic estimator (the 0046
    problem), so it is barred before its numbers count."""

    PREFLIGHT_PASS = "preflight-pass"
    UNSERVABLE = "unservable"
    COHERENCE_FAIL = "coherence-fail"
    TOOL_CALL_MALFORMED = "tool-call-malformed"
    REPLAY_FAIL = "replay-fail"


_EXCLUDING = frozenset(BakeoffPreflightOutcome) - {BakeoffPreflightOutcome.PREFLIGHT_PASS}


class BakeoffPreflightObservations:
    """The raw per-model probe facts the adjudicator types."""

    __slots__ = ("served", "coherent", "tool_calls_clean", "replay")

    def __init__(self, served: bool, coherent: bool, tool_calls_clean: bool, replay: str):
        self.served = served
        self.coherent = coherent
        self.tool_calls_clean = tool_calls_clean
        self.replay = replay


def adjudicate_bakeoff_preflight(
    obs: BakeoffPreflightObservations,
) -> BakeoffPreflightOutcome:
    """Exactly one value, in the frozen precedence (cheapest/most-fundamental
    first): unservable → coherence → tool-calling → replay → pass."""
    if not obs.served:
        return BakeoffPreflightOutcome.UNSERVABLE
    if not obs.coherent:
        return BakeoffPreflightOutcome.COHERENCE_FAIL
    if not obs.tool_calls_clean:
        return BakeoffPreflightOutcome.TOOL_CALL_MALFORMED
    if obs.replay != "reproducible":
        return BakeoffPreflightOutcome.REPLAY_FAIL
    return BakeoffPreflightOutcome.PREFLIGHT_PASS


def is_excluding(outcome: BakeoffPreflightOutcome) -> bool:
    return outcome in _EXCLUDING


def probe_served_membership(
    cfg: BakeoffConfig,
    *,
    api_base: str,
    assert_local_fn: Callable[..., Any],
    tags_reader: Callable[[str], Sequence[str]],
    tags: Sequence[str] | None = None,
) -> dict[str, bool]:
    """The POSITIVE ``/api/tags`` membership check — ``assert_local`` FIRST (the
    probe's own read is the same loopback-gated egress class as the calls it
    checks), THEN a per-tag membership over the served set. Cannot pass trivially
    when the endpoint is down (an empty served set → every tag False).

    ``tags`` defaults to ``cfg.model_tags`` (0048 behavior unchanged); spec 0049
    passes ``cfg.served_variant_tags`` via ``probe_served_variant_membership``."""
    checked = cfg.model_tags if tags is None else tags
    assert_local_fn(api_base)
    served = set(tags_reader(api_base))
    return {tag: tag in served for tag in checked}


def probe_served_variant_membership(
    cfg: BakeoffConfig,
    *,
    api_base: str,
    assert_local_fn: Callable[..., Any],
    tags_reader: Callable[[str], Sequence[str]],
) -> dict[str, bool]:
    """Spec 0049 (AC3): the positive ``/api/tags`` membership check keyed on the
    greedy ``served_variant_tags`` (NOT the base ``model_tags``)."""
    return probe_served_membership(
        cfg,
        api_base=api_base,
        assert_local_fn=assert_local_fn,
        tags_reader=tags_reader,
        tags=cfg.served_variant_tags,
    )


def reproducibility_replay_probe(
    run_case: Callable[[str, int], LocateBucket], cases: Sequence[str]
) -> str:
    """Double-run each of ``cases`` (run index 0 then 1) through the full explorer
    loop; ``"reproducible"`` iff every per-case bucket is identical across the two
    runs, else ``"replay-fail"``."""
    for case_id in cases:
        if run_case(case_id, 0) != run_case(case_id, 1):
            return "replay-fail"
    return "reproducible"


def bakeoff_preflight(
    cfg: BakeoffConfig,
    *,
    observations: Mapping[str, BakeoffPreflightObservations],
) -> tuple[dict[str, BakeoffPreflightOutcome], list[ModelExclusion]]:
    """Adjudicate each frozen tag; an excluding outcome yields a recorded
    ``ModelExclusion`` (never a scored-zero)."""
    outcomes: dict[str, BakeoffPreflightOutcome] = {}
    exclusions: list[ModelExclusion] = []
    for tag in cfg.model_tags:
        outcome = adjudicate_bakeoff_preflight(observations[tag])
        outcomes[tag] = outcome
        if is_excluding(outcome):
            exclusions.append(ModelExclusion(tag, outcome.value))
    return outcomes, exclusions


# ---- AC2 resumable ledger + durable artifact ---------------------------------


class BakeoffLedger:
    """Resumable per-cell (case × model) ledger keyed to the FROZEN config hash —
    a ledger under a different config is not resumable (loud). Mirrors
    ``think_ab_run.AbLedger``: atomic same-dir temp + replace."""

    def __init__(self, path: str | Path, *, config_hash: str):
        self._path = Path(path)
        self._config_hash = config_hash
        if self._path.is_file():
            obj = json.loads(self._path.read_text(encoding="utf-8"))
            version = obj.get("schema_version")
            if version not in _KNOWN_LEDGER_SCHEMA_VERSIONS:
                raise BakeoffRunError(f"unknown bakeoff-ledger schema_version: {version!r}")
            if obj.get("config_hash") != config_hash:
                raise BakeoffRunError(
                    "ledger was written under a different frozen config "
                    f"({obj.get('config_hash')!r} != {config_hash!r}) — not resumable"
                )
            self._entries: dict[str, dict[str, Any]] = dict(obj.get("entries", {}))
        else:
            self._entries = {}
            self._flush()

    @staticmethod
    def _key(case_id: str, model: str) -> str:
        return f"{case_id}::{model}"

    def has(self, case_id: str, model: str) -> bool:
        return self._key(case_id, model) in self._entries

    def get(self, case_id: str, model: str) -> dict[str, Any] | None:
        return self._entries.get(self._key(case_id, model))

    def record(self, case_id: str, model: str, entry: dict[str, Any]) -> None:
        self._entries[self._key(case_id, model)] = entry
        self._flush()

    @property
    def entries(self) -> dict[str, dict[str, Any]]:
        return dict(self._entries)

    def _flush(self) -> None:
        payload = {
            "schema_version": BAKEOFF_LEDGER_SCHEMA_VERSION,
            "config_hash": self._config_hash,
            "entries": self._entries,
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(self._path)


def build_bakeoff_artifact(
    cfg: BakeoffConfig,
    *,
    case_id: str,
    model: str,
    bucket: LocateBucket | None,
    tools: Mapping[str, int],
    symbols_adopted: bool,
    reasoning_tokens: int,
    submitted: bool,
    surviving: bool,
    found_but_unsubmitted: bool,
    serving_transport: str,
    sut_hash: str,
    exclusivity_record: Mapping[str, Any],
    heavy_repo_degrade: bool = False,
    degrade: str | None = None,
) -> dict[str, Any]:
    """The durable per model+case artifact — carries the bucket, tool usage
    (incl. symbols-adoption), reasoning cost, submit/survive/found-but-unsubmitted,
    the model identity + serving transport, the FROZEN decoding config, the 0047
    pool sha256, the pinned SUT hash, and the 0041 exclusivity proof."""
    return {
        "case_id": case_id,
        "model": model,
        "model_identity": model,
        "bucket": bucket.value if bucket is not None else None,
        "tools": dict(tools),
        "symbols_adopted": symbols_adopted,
        "reasoning_tokens": reasoning_tokens,
        "submitted": submitted,
        "surviving": surviving,
        "found_but_unsubmitted": found_but_unsubmitted,
        "serving_transport": serving_transport,
        "decoding": {
            "temperature": cfg.temperature,
            "top_p": cfg.top_p,
            "seed": cfg.seed,
        },
        "pool_sha256": cfg.pool_sha256,
        "sut_hash": sut_hash,
        "exclusivity": dict(exclusivity_record),
        "heavy_repo_degrade": heavy_repo_degrade,
        "degrade": degrade,
    }


# ---- AC4/AC5/AC6 report ------------------------------------------------------


def build_bakeoff_report(
    cfg: BakeoffConfig,
    entries: Mapping[str, Mapping[str, Any]],
    reachability: Mapping[str, str],
    *,
    surviving_models: Sequence[str] | None = None,
    exclusions: Sequence[ModelExclusion] = (),
    symbols_adoption: Mapping[str, float] | None = None,
    found_but_unsubmitted: Mapping[str, int] | None = None,
) -> BakeoffReport:
    """Assemble the typed report from the pure core: per conceptual pair compute
    ``b+c``, the McNemar p (where the discordance floor is cleared), the Holm
    family decision (m=3 FIXED), and the per-pair verdict; then the reachability
    split (conceptual verdicts + lexical descriptive stats), the per-repo
    distribution, and the typed assembly."""
    survivors = tuple(surviving_models) if surviving_models is not None else tuple(cfg.model_tags)

    # First pass: per-pair cases, drops, and the raw McNemar p for pairs that
    # both clear coverage and reach the discordance floor (only those are tested).
    per_pair: dict[tuple[str, str], dict[str, Any]] = {}
    raw_p: dict[tuple[str, str], float] = {}
    for pair in cfg.pairs:
        cases, dropped_total, dropped_degrade = split_by_reachability(
            entries, reachability, pair[0], pair[1]
        )
        b, c = discordant_counts(cases)
        per_pair[pair] = {
            "cases": cases, "dropped_total": dropped_total,
            "dropped_degrade": dropped_degrade, "b": b, "c": c,
        }
        if len(cases) >= cfg.coverage_floor and (b + c) >= cfg.conceptual_min_discordant:
            raw_p[pair] = mcnemar_exact_p(b, c)

    rejections = holm_rejections(
        raw_p, alpha=cfg.alpha, m=cfg.holm_family_size, tie_order=cfg.pairs
    )
    adjusted = holm_adjusted_pvalues(
        raw_p, m=cfg.holm_family_size, tie_order=cfg.pairs
    )

    pair_results: dict[tuple[str, str], PairResult] = {}
    per_repo_distribution: dict[str, Mapping[str, int]] = {}
    for pair, facts in per_pair.items():
        result = decide_pair_outcome(
            cfg, pair, facts["cases"],
            dropped_total=facts["dropped_total"], dropped_degrade=facts["dropped_degrade"],
            rejected=rejections.get(pair, False),
            raw_p=raw_p.get(pair), adjusted_p=adjusted.get(pair),
        )
        pair_results[pair] = result
        per_repo_distribution[f"{pair[0]}|{pair[1]}"] = per_repo_bc_distribution(facts["cases"])

    lexical_stats = {
        model: lexical_descriptive_stats(entries, reachability, model)
        for model in cfg.model_tags
    }

    # The 0042/0043 per-model threads are aggregated from the durable artifact
    # fields on the ledger entries when the caller does not supply them.
    if symbols_adoption is None:
        symbols_adoption = _aggregate_symbols_adoption(entries, cfg.model_tags)
    if found_but_unsubmitted is None:
        found_but_unsubmitted = _aggregate_found_but_unsubmitted(entries, cfg.model_tags)

    return assemble_bakeoff(
        pair_results, surviving_models=survivors, exclusions=exclusions,
        lexical_stats=lexical_stats, per_repo_distribution=per_repo_distribution,
        symbols_adoption=symbols_adoption, found_but_unsubmitted=found_but_unsubmitted,
    )


def _cells_for_model(
    entries: Mapping[str, Mapping[str, Any]], model: str
) -> list[Mapping[str, Any]]:
    suffix = f"::{model}"
    return [v for k, v in entries.items() if k.endswith(suffix)]


def _aggregate_symbols_adoption(
    entries: Mapping[str, Mapping[str, Any]], models: Sequence[str]
) -> dict[str, float]:
    """Per-model fraction of cells that invoked the ``symbols`` tool (0042 at
    scale). A model with no cells reports 0.0 (honest, never a fabricated rate)."""
    out: dict[str, float] = {}
    for model in models:
        cells = _cells_for_model(entries, model)
        adopted = sum(1 for c in cells if c.get("symbols_adopted"))
        out[model] = (adopted / len(cells)) if cells else 0.0
    return out


def _aggregate_found_but_unsubmitted(
    entries: Mapping[str, Mapping[str, Any]], models: Sequence[str]
) -> dict[str, int]:
    """Per-model count of found-but-unsubmitted cells (0043's class at scale)."""
    return {
        model: sum(1 for c in _cells_for_model(entries, model) if c.get("found_but_unsubmitted"))
        for model in models
    }
