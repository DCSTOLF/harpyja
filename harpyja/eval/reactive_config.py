"""Spec 0046 (AC7) — PREREGISTERED_REACTIVE_CONFIG_0046 (stage-2 of the freeze).

Stage 1 (the choosing rules — the FIVE-sided predicate, the three-member verdict
precedence, the power floors, the per-model readings, the baseline-relative
threshold DERIVATION RULE) is frozen in the reviewed spec BEFORE implementation
and committed at T22 (the predicate freeze, pre-baseline). THIS object names the
frozen choice as DATA — the post-lever SUT hash (covering the gate +
reactive_policy + confirm + confidence_signals), the sanity band, the derivation
rule — and is hashed + committed (T27) AFTER the baseline arm yields the derived
literals, BEFORE any new-arm spend.

Mirror-not-share vs ``submission_config`` (spec 0044): that object is a frozen
historical pin; this is its 0046 sibling. The derived literals
(``flagged_wrong_emitted_ceiling`` / ``flag_rate_max``) are ``None`` until T27 —
the verdict applies the frozen FRACTION to the measured baseline s->wc, so the
rule is frozen pre-baseline and the number is committed post-baseline.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from pathlib import Path

from harpyja.eval.adoption_precheck import PREREGISTERED_ADOPTION_CONFIG_0042
from harpyja.eval.submission_gap import DETECTOR_VERSION

# The explorer SUT surface the two levers ride — the 0044 list PLUS the new
# reactive_policy + confirm + the retained gold-blind confidence_signals
# (omitting any would let the predicate drift after the freeze).
_SUT_FILES = (
    "harpyja/scout/confidence_gate.py",
    "harpyja/scout/confidence_signals.py",
    "harpyja/scout/reactive_policy.py",
    "harpyja/scout/confirm.py",
    "harpyja/scout/context_map.py",
    "harpyja/scout/explorer_backend.py",
    "harpyja/scout/explorer_loop.py",
    "harpyja/scout/explorer_tools.py",
    "harpyja/config/settings.py",
)


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


@dataclasses.dataclass(frozen=True)
class ReactiveConfig:
    config_id: str = "0046/reactive-config/1"
    # Cells + coverage: the SAME 33 (11 cases x 3 models) 0040/0042/0044 measured.
    pilot_case_ids: tuple[str, ...] = PREREGISTERED_ADOPTION_CONFIG_0042.pilot_case_ids
    required_models: tuple[str, ...] = PREREGISTERED_ADOPTION_CONFIG_0042.required_models
    optional_models: tuple[str, ...] = PREREGISTERED_ADOPTION_CONFIG_0042.optional_models
    # The SUT pin (post-lever surface — recomputed at import, recorded verbatim in
    # the committed T27 config artifact, verified by the driver at startup).
    sut_files: tuple[str, ...] = _SUT_FILES
    sut_hash: str = dataclasses.field(default_factory=compute_sut_hash)
    gate_proof_version: str = "0041/exclusivity/1"
    ledger_schema_version: str = "0041/pilot/2"
    detector_version: str = DETECTOR_VERSION
    # BASELINE arm: the reverted-0044-gate re-measurement on the CURRENT SUT.
    # Its aggregate NET is expected in this frozen sanity band; outside -> the
    # typed BASELINE_DRIFT_STOP (a sanity check on SUT reproduction, NOT a
    # pass/fail gate on the new lever — AC6 measures NEW-vs-baseline).
    baseline_band: tuple[int, int] = (1, 3)
    # Power floors (reused from the 0044 discipline).
    min_covered_baseline_cells: int = 8
    min_baseline_swc: int = 3
    # The FIVE-sided predicate's threshold DERIVATION RULE (frozen pre-baseline).
    # The flagged-wrong-emitted ceiling is a relabel-tolerance FRACTION (< 1) of
    # the baseline s->wc: a pure relabel of the WHOLE baseline mass into flags
    # (fwe == baseline_swc) breaches it. The verdict applies the fraction to the
    # measured baseline; the DERIVED absolute is committed at T27.
    flagged_wrong_emitted_ceiling_fraction: float = 0.5
    flagged_wrong_emitted_ceiling: int | None = None  # derived, committed T27
    flag_rate_rule: str = (
        "flag-rate is a record-only per-model diagnostic (flagged fraction of "
        "confirmed cells); its upper-bound range is derived post-baseline (T27)"
    )
    flag_rate_max: float | None = None  # derived, committed T27
    # Per-model readings, pre-registered (AC7).
    beneficiary_model: str = "qwen3:14b"
    inert_model: str = "qwen3.5:4b"
    expected_model_readings: tuple[tuple[str, str], ...] = (
        ("qwen3:14b", "benefits from submit-discipline (0044: fired 5/11, zero regressions)"),
        ("qwen3:8b", "where miscalibration concentrates; its dawdle IS verification — a LOW "
                     "trigger rate is a SUCCESS, not a failure"),
        ("qwen3.5:4b", "inert to submission levers (constraint is tool-output bytes/prefill). "
                       "CONFIRM adds no turn; a 4b net-negative on a triggered-and-explored "
                       "cell is an inert-with-cost null, NOT trades-again"),
    )
    # The TWO levers under test (the ONE reverted + the two new mechanisms).
    levers_under_test: tuple[str, ...] = (
        "revert-0045-require-corroboration",
        "reactive-submit-best-span-default",
        "confirm-before-submit-interceptor",
    )
    # Named cells reported head-to-head (AC6).
    named_cells: tuple[str, ...] = (
        "pallets__flask-5014::qwen3:14b",
        "pallets__flask-5014::qwen3:8b",
        "django__django-14315::qwen3:8b",
        "pytest-dev__pytest-10081::qwen3:14b",
    )
    # The frozen three-member verdict precedence (first-true-wins), with the
    # UNDER_POWERED guard ahead of it (a returned member, never prose).
    verdict_precedence: tuple[str, ...] = (
        "under-powered",
        "trades-again",
        "dissolves-trade",
        "no-effect",
    )
    # The run knobs the 0044 cells used — both arms repeat them verbatim.
    scout_max_turns: int = 10
    scout_wall_clock_s: float = 240.0
    lm_http_timeout_s: float = 300.0
    explorer_think: bool | None = None


PREREGISTERED_REACTIVE_CONFIG_0046 = ReactiveConfig()


def reactive_config_hash(cfg: ReactiveConfig) -> str:
    payload = json.dumps(dataclasses.asdict(cfg), sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


REACTIVE_CONFIG_HASH_0046 = reactive_config_hash(PREREGISTERED_REACTIVE_CONFIG_0046)
