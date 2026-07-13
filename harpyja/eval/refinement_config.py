"""Spec 0045 — PREREGISTERED_REFINEMENT_CONFIG_0045 (AC4, stage 2 of the freeze).

Stage 1 (the choosing rule) was frozen in ``discriminator_table.py`` and
committed BEFORE the per-cell attribution. THIS object names the frozen choice
as data — the refined-rule key, the gate projection literals drift-pinned to
the SUT constants, BOTH comparison axes pinned by path + sha256, the comparison
literals (re-derived from the pinned 0044 artifacts in the pin test), the power
floors, the six-member verdict precedence, and the named cells — and is hashed +
committed (T23) AFTER the refined gate lands, BEFORE any live call.

``compute_sut_hash`` covers the refined gate AND the moved gold-blind signals,
so the config cannot be frozen until the SUT surface is byte-final.
"""

from __future__ import annotations

import dataclasses
import glob
import hashlib
import json
from collections import Counter
from pathlib import Path

from harpyja.eval.adoption_precheck import PREREGISTERED_ADOPTION_CONFIG_0042
from harpyja.eval.refinement_outcome import RefinementVerdict

# The explorer SUT surface the refinement rides — the refined gate + the moved
# gold-blind signals PLUS the loop/backend/context files the injection touches.
_SUT_FILES = (
    "harpyja/scout/confidence_gate.py",
    "harpyja/scout/confidence_signals.py",
    "harpyja/scout/context_map.py",
    "harpyja/scout/explorer_backend.py",
    "harpyja/scout/explorer_loop.py",
    "harpyja/scout/explorer_tools.py",
    "harpyja/config/settings.py",
)

_COMPARATOR_ARTIFACTS_DIR = (
    "specs/.archive/0044-submission/submission_run/artifacts"
)
_BASELINE_RUN = "adoption_0042"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def compute_sut_hash() -> str:
    """sha256 over the frozen SUT file list (name + bytes, in list order)."""
    h = hashlib.sha256()
    root = _repo_root()
    for rel in _SUT_FILES:
        h.update(rel.encode("utf-8"))
        h.update((root / rel).read_bytes())
    return h.hexdigest()


def derive_0044_comparator() -> dict:
    """RE-DERIVE the 0044 comparison literals from the pinned artifacts (the
    anti-tautology discipline): net per model (BEFORE(adoption_0042) x AFTER
    bucket join), fu_after, and s->wc (fired-on-wrong-span wrong-file cells)."""
    root = _repo_root()
    results = json.loads(
        (root / "specs/.archive/0044-submission/submission_run"
         "/submission_results.json").read_text(encoding="utf-8")
    )
    after = {
        k: v for k, v in results["entries"].items() if not v.get("degrade")
    }
    baseline = json.loads(
        (root / "specs/.archive/0043-diagnosis/attribution"
         "/attribution_table.json").read_text(encoding="utf-8")
    )
    before = {
        f"{c['case']}::{c['model']}": c["bucket"]
        for c in baseline["cases"] if c.get("run") == _BASELINE_RUN
    }
    net: Counter = Counter()
    for k in set(before) & set(after):
        model = k.split("::", 1)[1]
        bb, ab = before[k], after[k]["bucket"]
        if bb != "correct" and ab == "correct":
            net[model] += 1
        if bb == "correct" and ab != "correct":
            net[model] -= 1

    fu_after = sum(
        1 for v in after.values() if v.get("submission_outcome") == "found-unsubmitted"
    )
    # s->wc (comparator): fired-on-wrong-span cells that submitted a wrong file.
    swc: Counter = Counter()
    for f in sorted(glob.glob(str(root / _COMPARATOR_ARTIFACTS_DIR / "*.submission.json"))):
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        if d.get("confidence_null") == "fired-on-wrong-span" and d.get(
            "terminal_bucket"
        ) == "wrong-file":
            swc[d["model"]] += 1
    return {
        "net_by_model": dict(net),
        "fu_after": fu_after,
        "swc_by_model": dict(swc),
        "swc_total": sum(swc.values()),
    }


@dataclasses.dataclass(frozen=True)
class RefinementConfig:
    config_id: str = "0045/refinement-config/1"
    # Cells + coverage: consumed from the frozen 0042 adoption config.
    pilot_case_ids: tuple[str, ...] = PREREGISTERED_ADOPTION_CONFIG_0042.pilot_case_ids
    required_models: tuple[str, ...] = PREREGISTERED_ADOPTION_CONFIG_0042.required_models
    optional_models: tuple[str, ...] = PREREGISTERED_ADOPTION_CONFIG_0042.optional_models
    # The SUT pin (refined gate + moved signals — recomputed at import).
    sut_files: tuple[str, ...] = _SUT_FILES
    sut_hash: str = dataclasses.field(default_factory=compute_sut_hash)
    gate_proof_version: str = "0041/exclusivity/1"
    ledger_schema_version: str = "0041/pilot/2"
    verifier_schema_version: str = "0045/1"
    # BEFORE (bucket) axis — the committed pre-nudge baseline (fu_before = 6).
    baseline_table_path: str = (
        "specs/.archive/0043-diagnosis/attribution/attribution_table.json"
    )
    baseline_table_sha256: str = (
        "4fa58df66e4119afd64d476340ba304f253a5f45d172dd5ce13b6f56d12a86a4"
    )
    baseline_run: str = _BASELINE_RUN
    # Head-to-head (0044 comparator) axis — pinned by path + sha256.
    comparator_results_path: str = (
        "specs/.archive/0044-submission/submission_run/submission_results.json"
    )
    comparator_results_sha256: str = (
        "e75b0a29e1bf3b27eb7939b921064fddfeee00b7d63222def70e70ab2bf02616"
    )
    comparator_config_path: str = (
        "specs/.archive/0044-submission/submission_config/submission_config.json"
    )
    comparator_config_sha256: str = (
        "f5088aa4fb77f5d6e82900d239c43770e8800a3abf197a791b9503370781255f"
    )
    comparator_artifacts_dir: str = _COMPARATOR_ARTIFACTS_DIR
    comparator_artifacts_count: int = 32
    # The comparison LITERALS (re-derived from the pinned artifacts in the pin
    # test — a hand-restated literal alone is not a pin).
    comparator_net_by_model: tuple[tuple[str, int], ...] = (
        ("qwen3:14b", 1), ("qwen3:8b", 0), ("qwen3.5:4b", 1),
    )
    comparator_fu_after: int = 1
    comparator_swc_by_model: tuple[tuple[str, int], ...] = (("qwen3:8b", 5),)
    comparator_swc_total: int = 5
    # Power floors (consumed by the UNDER_POWERED branch).
    min_covered_joined_cells: int = 8
    min_comparator_swc: int = 3
    min_comparator_swc_role: str = (
        "re-derivation guard on the pinned baseline (checked against the "
        "freeze-time re-derived comparator swc=5, so it can only pass at "
        "runtime) — NOT a live power check"
    )
    # The frozen verdict precedence (six members, worse-first).
    verdict_precedence: tuple[str, ...] = tuple(m.name for m in RefinementVerdict)
    # Gate projection — LITERALS drift-pinned to the SUT constants.
    max_qualifying_spans: int = 5
    refined_rule_key: str = "require-corroboration"
    discriminator_table_hash: str = ""
    # Named cells (AC5/AC6 targets).
    residual_cell: str = "django__django-14315::qwen3:8b"
    never_fired_cell: str = "pytest-dev__pytest-10081::qwen3:14b"
    rescued_cells_hold_correct: tuple[str, ...] = (
        "pallets__flask-5014::qwen3:14b",
        "pallets__flask-5014::qwen3:8b",
    )
    # Pre-registered per-model readings (DATA, never close-time prose).
    expected_model_readings: tuple[tuple[str, str], ...] = (
        ("qwen3:14b", "fired 5/11 with ZERO regressions in 0044 — the gate "
         "works for it; require-corroboration should not regress it"),
        ("qwen3:8b", "the crux: fired 9/11 in 0044 and every miscalibration "
         "concentrates here; require-corroboration demotes its weak singletons"),
        ("qwen3.5:4b", "INERT (unfired); its 0044 +1 came from the sentence "
         "removal, not the gate — its lever is the parked compression spec"),
    )
    # Run knobs — repeated verbatim from the 0042/0044 cells.
    scout_max_turns: int = 10
    scout_wall_clock_s: float = 240.0
    lm_http_timeout_s: float = 300.0
    explorer_think: bool | None = None


def _default_discriminator_hash() -> str:
    from harpyja.eval.discriminator_table import DISCRIMINATOR_TABLE_HASH_0045

    return DISCRIMINATOR_TABLE_HASH_0045


PREREGISTERED_REFINEMENT_CONFIG_0045 = dataclasses.replace(
    RefinementConfig(), discriminator_table_hash=_default_discriminator_hash()
)


def refinement_config_hash(cfg: RefinementConfig) -> str:
    payload = json.dumps(dataclasses.asdict(cfg), sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


REFINEMENT_CONFIG_HASH_0045 = refinement_config_hash(
    PREREGISTERED_REFINEMENT_CONFIG_0045
)
