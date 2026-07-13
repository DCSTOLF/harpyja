"""Spec 0043 T1 — the found-but-unsubmitted detector (AC2).

The detector is a PURE PROJECTION over one persisted trajectory. Gold overlap
routes through the ONE existing oracle (`metrics.span_hit_kind`, by identity —
never a second overlap definition); the submitted / submitted-then-dropped
split routes through the EXISTING 0033 `citations_submitted` /
`citations_surviving` counts (one-counter-reuse, never re-parsed from history);
an undecodable tool message is the distinct typed outcome
`DETECTOR_INCONCLUSIVE`, never silently folded into `NEVER_FOUND`.
"""

from harpyja.eval import metrics, submission_gap
from harpyja.eval.submission_gap import (
    DETECTOR_VERSION,
    SubmissionOutcome,
    classify_submission,
)
from harpyja.server.types import CodeSpan

GOLD = (CodeSpan(path="astropy/modeling/separable.py", start_line=66, end_line=102),)


def _traj(tool_contents, *, submitted=None, surviving=None):
    """A minimal persisted trajectory: alternating assistant/tool turns."""
    turns = [{"role": "user", "content": "locate the thing"}]
    for content in tool_contents:
        turns.append({
            "role": "assistant",
            "content": "",
            "tool_calls": [{"function": {"name": "grep", "arguments": "{}"}}],
        })
        turns.append({"role": "tool", "content": content})
    return {
        "model_turns": turns,
        "citations_submitted": submitted,
        "citations_surviving": surviving,
    }


_HIT = (
    "[CodeSpan(path='astropy/modeling/separable.py', start_line=66, end_line=102, "
    "symbol='separability_matrix', language='python', kind='function')]"
)
_MISS = (
    "[CodeSpan(path='astropy/modeling/convolution.py', start_line=7, end_line=7, "
    "symbol=None, language=None, kind=None)]"
)
_PATH_ONLY = (
    "[CodeSpan(path='astropy/modeling/separable.py', start_line=None, end_line=None, "
    "symbol=None, language=None, kind=None)]"
)
_UNPARSEABLE = "[CodeSpan(path='astropy/modeling/separable.py', start_line="


# ---- the 6-row fixture matrix, each row pinned to its enum value ------------

def test_submission_outcome_enum_is_total_over_fixture_matrix():
    # The enum has EXACTLY these 5 members …
    assert {m.name for m in SubmissionOutcome} == {
        "FOUND_UNSUBMITTED",
        "SUBMITTED",
        "SUBMITTED_THEN_DROPPED",
        "NEVER_FOUND",
        "DETECTOR_INCONCLUSIVE",
    }
    # … and the 6 fixture rows map onto them totally:
    rows = {
        # tool-result hit, never submitted → found-unsubmitted
        "tool-result-hit": (
            _traj([_MISS, _HIT]),
            SubmissionOutcome.FOUND_UNSUBMITTED,
        ),
        # submitted and survived → submitted (the success case)
        "submitted-hit": (
            _traj([_HIT], submitted=1, surviving=1),
            SubmissionOutcome.SUBMITTED,
        ),
        # submitted but normalization dropped it → its own class (0033 counts)
        "submitted-then-dropped": (
            _traj([_HIT], submitted=1, surviving=0),
            SubmissionOutcome.SUBMITTED_THEN_DROPPED,
        ),
        # path-only (file-level) span: NOT a hit — the oracle's line-overlap
        # predicate decides (span_hit_kind == "file" is not "line")
        "path-only": (
            _traj([_PATH_ONLY]),
            SubmissionOutcome.NEVER_FOUND,
        ),
        # no gold-overlapping span anywhere → never-found
        "never-found": (
            _traj([_MISS, "[]"]),
            SubmissionOutcome.NEVER_FOUND,
        ),
        # undecodable tool message and no hit elsewhere → inconclusive
        "unparseable": (
            _traj([_UNPARSEABLE]),
            SubmissionOutcome.DETECTOR_INCONCLUSIVE,
        ),
    }
    for name, (traj, expected_outcome) in rows.items():
        assert classify_submission(traj, GOLD) is expected_outcome, name


def test_detector_parses_stringified_codespan_reprs_from_tool_role_messages():
    # The persisted history stringifies tool results — the detector recovers a
    # gold-overlapping CodeSpan from the repr text of a tool-role message.
    traj = _traj([_HIT])
    assert classify_submission(traj, GOLD) is SubmissionOutcome.FOUND_UNSUBMITTED
    # Non-tool roles never contribute spans: the same repr in ASSISTANT content
    # is not a tool observation.
    traj2 = _traj(["[]"])
    traj2["model_turns"].append({"role": "assistant", "content": _HIT})
    assert classify_submission(traj2, GOLD) is SubmissionOutcome.NEVER_FOUND


def test_submission_gap_reuses_metrics_line_overlap_oracle():
    # One-oracle reuse BY IDENTITY (the 0040 is_signal_discordant precedent):
    # the detector's overlap predicate IS metrics.span_hit_kind.
    assert submission_gap.span_hit_kind is metrics.span_hit_kind
    # And behaviorally: a path-only span (span_hit_kind == "file") is NOT found.
    assert classify_submission(_traj([_PATH_ONLY]), GOLD) is SubmissionOutcome.NEVER_FOUND


def test_submitted_then_dropped_routes_through_0033_counts_not_history():
    # Identical histories, different 0033 counts → different outcomes: the
    # submit side is decided from the counts, never re-parsed from history.
    hist = [_HIT]
    assert (
        classify_submission(_traj(hist, submitted=1, surviving=0), GOLD)
        is SubmissionOutcome.SUBMITTED_THEN_DROPPED
    )
    assert (
        classify_submission(_traj(hist, submitted=2, surviving=2), GOLD)
        is SubmissionOutcome.SUBMITTED
    )
    # A submit-looking assistant turn in history with NO counts recorded does
    # NOT read as a submission (counts are the one authority).
    traj = _traj(hist)
    traj["model_turns"].append({
        "role": "assistant",
        "content": "",
        "tool_calls": [{"function": {"name": "submit_citations", "arguments": "{}"}}],
    })
    assert classify_submission(traj, GOLD) is SubmissionOutcome.FOUND_UNSUBMITTED


def test_unparseable_tool_message_is_inconclusive_never_never_found():
    # Undecodable list-shaped tool content with no hit elsewhere: the detector
    # cannot rule out a found span → INCONCLUSIVE, never NEVER_FOUND.
    assert (
        classify_submission(_traj([_MISS, _UNPARSEABLE]), GOLD)
        is SubmissionOutcome.DETECTOR_INCONCLUSIVE
    )
    # But a PROVEN hit in a parseable message dominates: found is found even if
    # another message is undecodable.
    assert (
        classify_submission(_traj([_UNPARSEABLE, _HIT]), GOLD)
        is SubmissionOutcome.FOUND_UNSUBMITTED
    )
    # 0035 marker strings (bare non-list content) are a KNOWN no-span shape —
    # parseable-as-no-spans, never inconclusive.
    assert (
        classify_submission(_traj(["ls-path-not-found: 'astropy/x.py'"]), GOLD)
        is SubmissionOutcome.NEVER_FOUND
    )


def test_detector_version_constant_present():
    # The frozen AC5 config cites the detector version — identical detector on
    # both sides of the BEFORE/AFTER comparison.
    assert DETECTOR_VERSION == "0043/1"
