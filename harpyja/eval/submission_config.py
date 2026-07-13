"""Spec 0044 — PREREGISTERED_SUBMISSION_CONFIG_0044 (AC5, stage 2 of the freeze).

Stage 1 (the choosing rules — gate = symbols-derived exact span SOLELY, the
five-member verdict precedence, the power floors, the per-model readings) was
frozen in the reviewed spec BEFORE implementation. THIS object names the
frozen choice as data — the exact gate projection, the byte-pinned nudge
template, the baseline ledger identity, and the post-lever SUT hash — and is
hashed + committed (T21) AFTER the SUT lever lands, BEFORE any live call. The
AC8 verdict is a total pure function over THIS object and the retained
per-case cells; nothing about the re-measurement is chosen after the numbers
are seen.

Notes on the load-bearing fields:

- The config carries LITERALS, never references to the SUT constants — the
  test_submission_config drift pins bind them to the SUT truth (the 0042
  prompt↔surface drift-guard pattern), so a config↔SUT divergence is loud
  rather than tautologically green.
- ``baseline_table_*`` freezes the BEFORE side: the committed 0043 attribution
  table (the 0040/0042 pre-nudge ledger — the same axis 0043 was read on;
  fu_before = 6 clears the floor of 3). Measuring against the shipped 0043 SUT
  would start from fu_before = 2 and leave the drop conjunct vacuous.
- ``sut_delta`` names BOTH parts of the one lever: the shipped 0043
  unconditional sentence is REMOVED and the conditioned mid-loop injection is
  ADDED — the comparison is two-armed, never silently three-armed.
- ``never_fires_max_beneficiary_firings`` is the NEVER_FIRES threshold as
  NUMERIC data (round-2 codex), keyed to the pre-registered beneficiary model
  (14b) ONLY — an 8b zero-firing rate never triggers the label (its
  pre-registered success criterion is regressions = 0 at ANY firing rate).
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from pathlib import Path

from harpyja.eval.adoption_precheck import PREREGISTERED_ADOPTION_CONFIG_0042
from harpyja.eval.submission_gap import DETECTOR_VERSION

# The explorer SUT surface the lever rides — the 0043 list PLUS the new gate
# module (omitting it would let the predicate drift after the freeze).
_SUT_FILES = (
    "harpyja/scout/confidence_gate.py",
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
class SubmissionConfig:
    config_id: str = "0044/submission-config/1"
    # Cells + coverage: consumed from the frozen 0042 adoption config — the
    # same cells 0040/0042/0043 measured; never re-selected.
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
    # in the committed T21 config artifact, verified by the driver at startup).
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
    # BASELINE (BEFORE) identity — frozen path + per-source sha256 of the
    # committed pre-nudge table; fu_before re-derives to 6 from it.
    baseline_table_path: str = (
        "specs/.archive/0043-diagnosis/attribution/attribution_table.json"
    )
    baseline_table_sha256: str = (
        "4fa58df66e4119afd64d476340ba304f253a5f45d172dd5ce13b6f56d12a86a4"
    )
    baseline_run: str = "adoption_0042"
    # Power floors (reused verbatim from the frozen 0043 config).
    min_covered_before_cells: int = 8
    min_before_found_unsubmitted: int = 3
    # The gate projection — LITERALS, drift-pinned to the SUT constants.
    confidence_signal: str = "symbols-exact-span"
    max_qualifying_spans: int = 5
    nudge_template: str = (
        "Your symbols result contains the exact span(s): {spans}. "
        "If one of these spans answers the query, call submit_citations with it now."
    )
    nudge_role: str = "user"
    # NEVER_FIRES threshold — numeric data, keyed to the beneficiary ONLY.
    beneficiary_model: str = "qwen3:14b"
    never_fires_max_beneficiary_firings: int = 0
    # Pre-registered per-model readings (OQ2/OQ3 as DATA, never close-time prose).
    expected_model_readings: tuple[tuple[str, str], ...] = (
        (
            "qwen3:14b",
            "the pre-registered beneficiary (its 0043 failure mode was "
            "dawdle-after-locate); NEVER_FIRES is keyed to 14b firings == 0",
        ),
        (
            "qwen3:8b",
            "success criterion is regressions == 0 at ANY firing rate — high "
            "firing with zero regressions is the EXPECTED success shape (8b "
            "had the highest 0042 symbols adoption, 10/11); zero firing with "
            "zero regressions is also success, never instrument failure",
        ),
        (
            "qwen3.5:4b",
            "expected inert (its constraint is tool-output-byte/prefill cost, "
            "not dawdling — the 0043 named inversion); an unmoved 4b is "
            "consistent-with-expectation, its lever is the future compression "
            "spec",
        ),
    )
    # The ONE lever, both named parts (removal + conditioned addition).
    levers_under_test: tuple[str, ...] = ("confidence-conditioned-submit-nudge",)
    sut_delta: tuple[str, ...] = (
        "remove-0043-unconditional-nudge",
        "add-confidence-conditioned-mid-loop-nudge",
    )
    # The run knobs the 0042/0043 cells used — the AFTER run repeats them
    # verbatim (the lever is the ONLY deliberate SUT delta).
    scout_max_turns: int = 10
    scout_wall_clock_s: float = 240.0
    lm_http_timeout_s: float = 300.0
    explorer_think: bool | None = None


PREREGISTERED_SUBMISSION_CONFIG_0044 = SubmissionConfig()


def submission_config_hash(cfg: SubmissionConfig) -> str:
    payload = json.dumps(dataclasses.asdict(cfg), sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


SUBMISSION_CONFIG_HASH_0044 = submission_config_hash(
    PREREGISTERED_SUBMISSION_CONFIG_0044
)
