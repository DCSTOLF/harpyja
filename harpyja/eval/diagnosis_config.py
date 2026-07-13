"""Spec 0043 — PREREGISTERED_DIAGNOSIS_CONFIG_0043 (AC5, stage 2 of the freeze).

Frozen + hashed + committed AFTER the stage-1 lever table mechanically
selected the lever from the committed T9 attribution, BEFORE any live compute
is spent (the 0023/0026/0039/0040/0042 discipline). The AC6 verdict is a total
pure function over THIS object and the retained per-case pairs — nothing about
the re-measurement is chosen after the numbers are seen.

Notes on the load-bearing fields:

- ``pilot_case_ids`` / model coverage are CONSUMED from the frozen 0042
  adoption config — never re-selected.
- ``levers_under_test`` is the frozen record of what the stage-1 table
  selected over the committed attribution (``submit-early-prompt-nudge`` —
  the located-but-unsubmitted cells dawdle a median of 5 assistant turns
  after the gold span is in hand); the pin test recomputes the selection from
  the committed table and fails loudly on any mismatch.
- ``sut_hash`` pins the explorer SUT surface (the files the lever rides) so
  the AFTER cells provably ran on the named post-lever SUT — pre/post
  comparability is explicit, the 0042 SUT-frozen-per-run posture.
- TWO power floors (the 0042 ``MIN_RFWS_DENOMINATOR`` pattern): the covered
  BEFORE subset (cells whose full trajectory survived in machine-local
  ``eval_work``) and the BEFORE found-unsubmitted denominator — a floor on
  coverage alone would leave "found-but-unsubmitted drops" vacuously true at
  a zero denominator. Below either floor the verdict is the mechanical
  ``CLOCK_BOUND_UNDER_POWERED`` branch, never prose qualification.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from pathlib import Path

from harpyja.eval.adoption_precheck import PREREGISTERED_ADOPTION_CONFIG_0042
from harpyja.eval.lever_table import LEVER_TABLE_HASH_0043
from harpyja.eval.submission_gap import DETECTOR_VERSION

# The explorer SUT surface a lever may legitimately ride (messages / named
# Settings knobs) — the byte-frozen params pin lives in these files' tests.
_SUT_FILES = (
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
class DiagnosisConfig:
    config_id: str = "0043/diagnosis-config/1"
    # Cells + coverage: consumed from the frozen 0042 adoption config.
    pilot_case_ids: tuple[str, ...] = (
        PREREGISTERED_ADOPTION_CONFIG_0042.pilot_case_ids
    )
    required_models: tuple[str, ...] = (
        PREREGISTERED_ADOPTION_CONFIG_0042.required_models
    )
    optional_models: tuple[str, ...] = (
        PREREGISTERED_ADOPTION_CONFIG_0042.optional_models
    )
    # The SUT pin (post-lever surface — recomputed at import, recorded verbatim
    # in the committed config artifact).
    sut_files: tuple[str, ...] = _SUT_FILES
    sut_hash: str = dataclasses.field(default_factory=compute_sut_hash)
    # Gate + ledger proof versions the re-measurement must carry.
    gate_proof_version: str = "0041/exclusivity/1"
    ledger_schema_version: str = "0041/pilot/2"
    # The exact counted buckets for BIDIRECTIONAL movement (net surfaced).
    counted_buckets: tuple[str, ...] = (
        "correct",
        "right-file-wrong-span",
        "wrong-file",
        "empty",
    )
    # Identical detector on both sides of the BEFORE/AFTER comparison.
    detector_version: str = DETECTOR_VERSION
    # Power floors (the 0042 MIN_RFWS_DENOMINATOR pattern) — mechanical
    # UNDER_POWERED, never prose.
    min_covered_before_cells: int = 8
    min_before_found_unsubmitted: int = 3
    # The stage-1 selection, frozen: what the committed lever table picked over
    # the committed attribution (pin-tested against a recomputation).
    lever_table_hash: str = LEVER_TABLE_HASH_0043
    levers_under_test: tuple[str, ...] = ("submit-early-prompt-nudge",)
    # The run knobs the 0042 cells used — the AFTER run repeats them verbatim
    # (the lever is the ONLY deliberate SUT delta).
    scout_max_turns: int = 10
    scout_wall_clock_s: float = 240.0
    lm_http_timeout_s: float = 300.0
    explorer_think: bool | None = None


PREREGISTERED_DIAGNOSIS_CONFIG_0043 = DiagnosisConfig()


def diagnosis_config_hash(cfg: DiagnosisConfig) -> str:
    payload = json.dumps(dataclasses.asdict(cfg), sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


DIAGNOSIS_CONFIG_HASH_0043 = diagnosis_config_hash(
    PREREGISTERED_DIAGNOSIS_CONFIG_0043
)
