"""Spec 0039 — thinking A/B: frozen pre-registered config + total pure verdict.

The paired None(default-on)-vs-False(off) A/B over the 0036 reachability-tagged
set, deciding whether reasoning-on causally moves the CONCEPTUAL stratum. Every
verdict-shaping choice is FROZEN here, hashed, and committed BEFORE any live arm
fires (the 0023/0026 ``PREREGISTERED_*`` convention): arm identities, the model
tag + serving transport (a runtime resolve is a servability check, not a
pre-registration), alpha, the K-repeat fold rule, per-stratum floors, the
invalid-pair ceiling, the degrade-asymmetry threshold, and the operational form
of distinctness factor (b).

Distinctness-guard ASYMMETRY (deliberate, per review): an OFF arm showing
reasoning is an instrument defect — the knob failed — so the pair is INVALID
(excluded-and-recorded; enough of them trips CONFOUNDED). An ON arm showing no
reasoning is LEGITIMATE behavior of the shipped ``explorer_think=None`` default —
the pair is KEPT; excluding it would bias the sample toward cases where thinking
fired, which is not the shipped contrast the default-flip decision needs. Do not
"fix" this into symmetry.

OQ1/OQ2 freeze (plan time): K=2 with an ``any-success`` fold for the paired
arms (the observational True("high") arm gets K=1 and NEVER enters the paired
verdict); a fixed per-repeat seed schedule (repeat k uses seed S_k for BOTH
arms) whose honoring claim starts ``"unverified"`` until the driver's two-call
probe confirms the ``/v1`` path honors ``seed`` — the 0037 lesson: never record
provenance an endpoint may silently drop.
"""

from __future__ import annotations

import dataclasses
import enum
import hashlib
from collections.abc import Sequence

from harpyja.eval.ac8_pilot import PilotPair, is_signal_discordant
from harpyja.eval.benchmark_fit import PREREGISTERED_CONFIG, mcnemar_rejects
from harpyja.eval.locate_accuracy import LocateBucket
from harpyja.eval.terse_dataset import STRATUM_UNDER_POPULATED

# The committed 0038 probe evidence this config pins (test-enforced against
# reconcile_probe.load_committed_reconcile_probe_result()).
_MODEL_TAG = "qwen3:14b"
_SERVING_TRANSPORT = "v1-reasoning-effort"


@dataclasses.dataclass(frozen=True)
class AbConfig:
    """Pre-registered thinking-A/B decision config (frozen; hashed pre-run)."""

    # Arms. A = shipped default (None ⇒ reasoning_effort omitted ⇒ default-ON,
    # 0038-proven 852–3457 reasoning chars/turn live). B = off (False ⇒
    # reasoning_effort:"none"). C = True ("high") — OBSERVATIONAL ONLY.
    arm_a_think: bool | None = None
    arm_b_think: bool | None = False
    arm_c_think: bool | None = True
    arm_c_observational_only: bool = True

    # Model identity — pre-registered, matching the committed 0038 probe.
    lm_model: str = _MODEL_TAG
    serving_transport: str = _SERVING_TRANSPORT

    # Statistics.
    alpha: float = 0.05
    # Per-stratum floor: FIXED at the committed 0023 exact-McNemar floor; the
    # derivation rule is pinned so the floor can never be re-derived downward
    # (e.g. to the arithmetic minimum of 6) after outcomes are visible.
    conceptual_min_discordant: int = PREREGISTERED_CONFIG.MIN_DISCORDANT_PAIRS
    floor_derivation: str = "fixed-not-re-derivable"
    # A stratum is VERDICTED only at or above this case count (the committed
    # 0023 min_n); below it the line is typed STRATUM_UNDER_POPULATED —
    # described, never verdicted (the lexical N=4 stratum).
    stratum_min_cases: int = PREREGISTERED_CONFIG.min_n

    # K policy (OQ1 frozen): 2 repeats per paired case+arm, folded to ONE binary
    # outcome per cell (McNemar's assumption) by any-success; observational K=1.
    k_repeats: int = 2
    k_fold_rule: str = "any-success"
    observational_k: int = 1

    # Run-integrity thresholds — the CONFOUNDED predicate inputs.
    invalid_pair_ceiling: float = 0.20
    degrade_asymmetry_threshold: float = 0.20

    # Factor (b) of the two-factor distinctness guard — operational form frozen:
    # per-case aggregate of per-turn completion_tokens, expected direction
    # on >= off, with a minimum delta before the factor bites. The factor bites
    # ONLY when the on arm reasoned substantially (>= factor_b_min_on_reasoning_
    # chars): a substantially-reasoning on arm whose budget is indistinguishable
    # from the off arm's is the hidden-thinking signature (a serialization-only
    # off arm keeps burning tokens); an easy case where the on arm thought
    # little has a legitimately small delta and is NEVER invalidated by (b).
    factor_b_scope: str = "per-case-aggregate"
    factor_b_direction: str = "on-at-least-off"
    min_on_vs_off_token_delta: int = 64
    factor_b_min_on_reasoning_chars: int = 256

    # Seed schedule (OQ2 frozen): repeat k uses seed_schedule[k] for BOTH arms.
    # The honoring claim is UNVERIFIED until the driver's two-call probe passes;
    # a negative probe downgrades the paired-per-repeat property, never fakes it.
    seed_schedule: tuple[int, ...] = (1039, 2039)
    seed_honoring: str = "unverified"


PREREGISTERED_AB_CONFIG_0039 = AbConfig()


def ab_config_hash(cfg: AbConfig) -> str:
    payload = "|".join(f"{k}={v}" for k, v in sorted(dataclasses.asdict(cfg).items()))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


AB_CONFIG_HASH_0039 = ab_config_hash(PREREGISTERED_AB_CONFIG_0039)


# ---- total pure verdict (AC1/AC2) -------------------------------------------


class AbVerdict(enum.Enum):
    """Direction-complete typed outcome — a one-sided label set would be a
    steering surface. CONFOUNDED is checked FIRST: a confounded run never emits
    a statistical verdict."""

    THINKING_HELPS = "thinking-helps"
    THINKING_HURTS = "thinking-hurts"
    NO_EFFECT = "no-effect"
    UNDER_POWERED = "under-powered"
    CONFOUNDED = "confounded"


@dataclasses.dataclass(frozen=True)
class PairRecord:
    """One case's K-folded on/off outcome pair, read from the verifier artifacts.

    ``bucket_*`` is the folded LocateBucket per arm (None only under a typed
    degrade or a missing artifact — never a silent hole). ``reasoning_chars_*``
    and ``completion_tokens_*`` are the per-case aggregates of the 0038/1
    artifact's per-turn fields — the two distinctness factors."""

    case_id: str
    reachability: str
    bucket_on: LocateBucket | None
    bucket_off: LocateBucket | None
    reasoning_chars_on: int
    reasoning_chars_off: int
    completion_tokens_on: int
    completion_tokens_off: int
    degrade_on: str | None = None
    degrade_off: str | None = None


@dataclasses.dataclass(frozen=True)
class AbVerdictResult:
    """The verdict plus every input a reader needs to audit it — exclusions are
    RECORDED with causes (0036 posture), never silent attrition of N."""

    verdict: AbVerdict
    pairs_total: int
    pairs_counted: int
    signal_discordant: int
    discordant_b: int  # off missed, on located — the flip favoring thinking-on
    discordant_c: int  # on missed, off located — the flip favoring thinking-off
    excluded: tuple[tuple[str, str], ...]  # (case_id, cause)
    invalid_pair_rate: float
    degrade_asymmetry: float
    confound_reasons: tuple[str, ...]


def _to_pilot_pair(record: PairRecord) -> PilotPair:
    # Adapter onto the committed 0026 oracle: arm A = thinking-on, B = off.
    assert record.bucket_on is not None and record.bucket_off is not None
    return PilotPair(
        case_id=record.case_id, bucket_a=record.bucket_on, bucket_b=record.bucket_off
    )


def located_via_oracle(bucket: LocateBucket) -> bool:
    """The SAME located set the 0026 oracle uses (CORRECT + RIGHT_FILE_WRONG_
    SPAN), reached through is_signal_discordant — never a re-derived local rule.
    The one home for the located predicate (verdict + pre-check both route here).
    """
    probe = PilotPair(case_id="_", bucket_a=bucket, bucket_b=LocateBucket.EMPTY)
    return is_signal_discordant(probe)


_located = located_via_oracle


def decide_ab_verdict(
    records: Sequence[PairRecord],
    cfg: AbConfig = PREREGISTERED_AB_CONFIG_0039,
    *,
    min_discordant: int | None = None,
) -> AbVerdictResult:
    """Total pure verdict over (config, pair records). Never raises on data,
    never silently defaults; every exclusion carries its cause.

    Order: partition (degrades excluded-and-recorded; missing artifacts are a
    CONFOUND, not an exclusion) → validity guard → CONFOUNDED gate (checked
    FIRST among verdicts) → discordant floor → directional exact McNemar.
    """
    floor = cfg.conceptual_min_discordant if min_discordant is None else min_discordant
    excluded: list[tuple[str, str]] = []
    confound_reasons: list[str] = []
    counted: list[PairRecord] = []
    invalid_count = 0
    validity_candidates = 0

    for record in records:
        if record.degrade_on or record.degrade_off:
            # A typed environment degrade on either arm is not a capability
            # observation — exclude and record (0036 posture).
            cause = "degrade:" + ";".join(
                part
                for part in (
                    f"on:{record.degrade_on}" if record.degrade_on else "",
                    f"off:{record.degrade_off}" if record.degrade_off else "",
                )
                if part
            )
            excluded.append((record.case_id, cause))
            continue
        if record.bucket_on is None or record.bucket_off is None:
            # A counted pair with a verifier-failed/missing artifact and NO
            # typed degrade cause is a run-integrity defect → CONFOUNDED.
            confound_reasons.append(f"missing-artifact:{record.case_id}")
            continue
        validity_candidates += 1
        valid, reason = classify_pair_validity(record, cfg)
        if not valid:
            invalid_count += 1
            excluded.append((record.case_id, f"invalid:{reason}"))
            continue
        counted.append(record)

    invalid_rate = invalid_count / validity_candidates if validity_candidates else 0.0
    total = len(records)
    deg_on_rate = sum(1 for r in records if r.degrade_on) / total if total else 0.0
    deg_off_rate = sum(1 for r in records if r.degrade_off) / total if total else 0.0
    degrade_asymmetry = abs(deg_on_rate - deg_off_rate)

    if invalid_rate > cfg.invalid_pair_ceiling:
        confound_reasons.append(
            f"invalid-pair-rate {invalid_rate:.2f} > ceiling {cfg.invalid_pair_ceiling}"
        )
    if degrade_asymmetry > cfg.degrade_asymmetry_threshold:
        confound_reasons.append(
            f"degrade-asymmetry {degrade_asymmetry:.2f} (on {deg_on_rate:.2f} vs "
            f"off {deg_off_rate:.2f}) > threshold {cfg.degrade_asymmetry_threshold}"
        )

    signal = sum(1 for r in counted if is_signal_discordant(_to_pilot_pair(r)))
    b = sum(
        1 for r in counted if _located(r.bucket_on) and not _located(r.bucket_off)
    )
    c = sum(
        1 for r in counted if _located(r.bucket_off) and not _located(r.bucket_on)
    )

    def _result(verdict: AbVerdict) -> AbVerdictResult:
        return AbVerdictResult(
            verdict=verdict,
            pairs_total=total,
            pairs_counted=len(counted),
            signal_discordant=signal,
            discordant_b=b,
            discordant_c=c,
            excluded=tuple(excluded),
            invalid_pair_rate=invalid_rate,
            degrade_asymmetry=degrade_asymmetry,
            confound_reasons=tuple(confound_reasons),
        )

    # CONFOUNDED first — a confounded run never emits a statistical verdict.
    if confound_reasons:
        return _result(AbVerdict.CONFOUNDED)
    # Floor gate — an under-floor null is UNDER_POWERED, never NO_EFFECT.
    if signal < floor:
        return _result(AbVerdict.UNDER_POWERED)
    if mcnemar_rejects(b, c, alpha=cfg.alpha):
        return _result(
            AbVerdict.THINKING_HELPS if b > c else AbVerdict.THINKING_HURTS
        )
    return _result(AbVerdict.NO_EFFECT)


def classify_pair_validity(record: PairRecord, cfg: AbConfig) -> tuple[bool, str | None]:
    """The two-factor arm-distinctness guard — DELIBERATELY ASYMMETRIC.

    - Off arm shows reasoning → the knob failed for this pair: instrument
      defect, INVALID (excluded-and-recorded; enough of them → CONFOUNDED).
    - On arm shows no/little reasoning → KEPT: legitimate behavior of the
      shipped ``explorer_think=None`` default; excluding it would bias the
      sample toward cases where thinking fired.
    - Factor (b): an on arm that reasoned SUBSTANTIALLY while the off arm burned
      an indistinguishable completion budget is the hidden-thinking signature
      (a serialization-only off arm keeps generating) → INVALID.
    """
    if record.reasoning_chars_off > 0:
        return False, "off-arm-reasoning-present"
    if (
        record.reasoning_chars_on >= cfg.factor_b_min_on_reasoning_chars
        and (record.completion_tokens_on - record.completion_tokens_off)
        < cfg.min_on_vs_off_token_delta
    ):
        return False, "factor-b-budget-indistinct"
    return True, None


# ---- AC4: reachability split + unified total report shape --------------------

# The ONE total outcome taxonomy the report speaks: the five direction-complete
# verdict members, the pre-check's typed stop, and the typed under-populated
# stratum line (the 0036 conceptual_stratum_report pattern). Nothing else.
PRECHECK_STOP = "under-powered-stop"

AB_REPORT_OUTCOMES = frozenset(v.value for v in AbVerdict) | {
    PRECHECK_STOP,
    STRATUM_UNDER_POPULATED,
}


@dataclasses.dataclass(frozen=True)
class StratumLine:
    """One reachability stratum's line: verdicted against its own floor, or
    TYPED under-populated — described but never verdicted, never implied
    comparable."""

    n: int
    status: str  # "verdicted" | STRATUM_UNDER_POPULATED
    floor: int
    result: AbVerdictResult | None


@dataclasses.dataclass(frozen=True)
class AbReport:
    """The split report. The headline is the CONCEPTUAL stratum line — the
    hypothesis and the majority — never a whole-set average (which would fold
    the RETRIEVAL_FUNDAMENTAL confound into "thinking doesn't help")."""

    config_hash: str
    headline: str
    strata: dict[str, StratumLine]


def decide_ab_report(
    records: Sequence[PairRecord],
    cfg: AbConfig = PREREGISTERED_AB_CONFIG_0039,
    *,
    precheck_stop: bool = False,
) -> AbReport:
    """Total pure report over (config, pair records), split by reachability.

    ``precheck_stop=True`` is the gated branch: the AC5 pre-check fired
    UNDER_POWERED_STOP, no live records exist, and the typed stop IS the
    headline — the same report shape, never a side-channel."""
    if precheck_stop:
        return AbReport(
            config_hash=ab_config_hash(cfg), headline=PRECHECK_STOP, strata={}
        )
    strata: dict[str, StratumLine] = {}
    for stratum in ("conceptual", "lexical"):
        subset = [r for r in records if r.reachability == stratum]
        if len(subset) >= cfg.stratum_min_cases:
            result = decide_ab_verdict(subset, cfg)
            strata[stratum] = StratumLine(
                n=len(subset),
                status="verdicted",
                floor=cfg.conceptual_min_discordant,
                result=result,
            )
        else:
            strata[stratum] = StratumLine(
                n=len(subset),
                status=STRATUM_UNDER_POPULATED,
                floor=cfg.conceptual_min_discordant,
                result=None,
            )
    conceptual = strata["conceptual"]
    headline = (
        f"conceptual: {conceptual.result.verdict.value}"
        if conceptual.result is not None
        else f"conceptual: {STRATUM_UNDER_POPULATED}"
    )
    return AbReport(config_hash=ab_config_hash(cfg), headline=headline, strata=strata)
