"""Spec 0021 (AC2/AC4) — the escalation-trigger classifier.

A pure, additive eval-side helper (the SUT in `harpyja/orchestrator/` is frozen).
Given a case's Tier-1 correctness, whether the gate rejected it, whether Deep was
available, and the PLANNED ladder (from `harpyja.orchestrator.matrix.plan_ladder`,
passed in — never re-derived here), it decides whether the auto path escalates and,
when it does not, WHY.

The "why" is the MECE `wrong_citation_fate` axis of the 0021 finding. It exists to
explain the 0020 contradiction: `escalation_rate=0` with 5 wrong Tier-1 citations
the gate saw. The metric itself is derived (`metrics.escalation_rate = mean(2 in
tiers_run)`); this classifier attributes the *reason* a case did or did not reach
Tier-2, which the derived rate cannot show on its own.
"""

from __future__ import annotations

import enum
from collections.abc import Sequence


class WrongCitationFate(enum.Enum):
    """Why a (potentially wrong) Tier-1 case did not escalate to Tier-2.

    - ``GATE_FALSE_ACCEPTANCE``: Tier-1 was wrong but the gate accepted (passed) it,
      so no escalation was triggered (a gate-quality lead, distinct from
      false-escalation).
    - ``NO_ESCALATION_PATH``: the case cannot escalate BY DESIGN — either Tier-2 is
      not on the planned ladder (e.g. fast-mode ``[0, 1]``), or Scout returned
      nothing so the gate was SKIPPED and the auto path took the honest-empty exit
      (``locate.py`` ``_honest_empty``, ``tiers_run=[0,1]``). Both share "there was
      never a live escalation decision to make."
    - ``DEEP_DEGRADED_OR_UNAVAILABLE``: the gate rejected and Tier-2 was on-ladder,
      but Deep was degraded/unavailable (``deep-degraded:<cause>`` / OOM), so
      escalation was honestly suppressed and ``tiers_run`` stayed ``[0,1]``.
    - ``NOT_APPLICABLE``: not a suppressed-wrong-citation case — either the case
      escalated normally, or Tier-1 was correct and the gate passed it.
    """

    GATE_FALSE_ACCEPTANCE = "gate-false-acceptance"
    NO_ESCALATION_PATH = "no-escalation-path"
    DEEP_DEGRADED_OR_UNAVAILABLE = "deep-degraded-or-unavailable"
    NOT_APPLICABLE = "not-applicable"


def classify_escalation(
    *,
    tier1_correct: bool,
    gate_rejected: bool,
    deep_available: bool,
    ladder: Sequence[int],
    tier1_empty: bool = False,
) -> tuple[bool, WrongCitationFate]:
    """Decide whether the auto path escalates, and the fate when it does not.

    A faithful projection of the frozen ``locate._locate_auto`` escalation decision.
    Precedence, most-structural first:

    1. Tier-2 not on the planned ``ladder`` -> cannot escalate: ``NO_ESCALATION_PATH``.
    2. ``tier1_empty`` -> Scout returned nothing, the gate is SKIPPED, and the auto
       path takes the honest-empty exit (``_honest_empty``, never escalates):
       ``NO_ESCALATION_PATH`` (escalation was never on the table).
    3. ``tier1_correct`` -> the gate passes a correct citation, no escalation needed:
       ``NOT_APPLICABLE``.
    4. Gate did NOT reject a wrong Tier-1 (it passed it) -> ``GATE_FALSE_ACCEPTANCE``.
    5. Gate rejected but Deep unavailable -> ``DEEP_DEGRADED_OR_UNAVAILABLE``.
    6. Otherwise the wrong/rejected case escalates -> ``(True, NOT_APPLICABLE)``.

    Ladder-first (then empty) is deliberate: a case that could never reach Tier-2 —
    because the ladder lacks it, or because the gate never ran — dominates every
    gate/Deep consideration.
    """
    if 2 not in tuple(ladder):
        return False, WrongCitationFate.NO_ESCALATION_PATH
    if tier1_empty:
        # honest-empty: gate skipped, `_honest_empty` exit, never escalates by design.
        return False, WrongCitationFate.NO_ESCALATION_PATH
    if tier1_correct:
        return False, WrongCitationFate.NOT_APPLICABLE
    if not gate_rejected:
        return False, WrongCitationFate.GATE_FALSE_ACCEPTANCE
    if not deep_available:
        return False, WrongCitationFate.DEEP_DEGRADED_OR_UNAVAILABLE
    return True, WrongCitationFate.NOT_APPLICABLE
