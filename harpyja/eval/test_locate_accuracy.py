"""Spec 0022 (AC1/AC2/AC3/AC7/AC10) — Scout locate-accuracy taxonomy + decision rule.

A pure, additive eval-side projection above the FROZEN oracle
(`harpyja.eval.metrics.span_hit_kind` / `span_hit_secondary`). The classifier reads
the oracle's overlap verdict; it never re-derives routing or re-implements suffix
recovery (that is the SUT's `ScoutEngine.search`, whose `last_tally` we read).

The one deliberate departure from the oracle — a path-only right-file citation
(`span_hit_kind == "file"`) is scored `RIGHT_FILE_WRONG_SPAN`, NOT `CORRECT` — lives
ONLY in this module (the whole diagnostic axis is "found the file" vs "found the
span"); `metrics.py` is untouched.
"""

from __future__ import annotations

from harpyja.scout.engine import ScoutTally
from harpyja.server.types import CodeSpan


def _span(path: str, start: int | None, end: int | None) -> CodeSpan:
    return CodeSpan(path=path, start_line=start, end_line=end)


# ---- AC3: citation normalization runs BEFORE classification ----------------

def test_normalize_citations_reads_recovery_counts_from_tally():
    # The recovery counts are READ off the SUT's ScoutTally (spec 0012), never
    # re-derived by the eval layer.
    from harpyja.eval.locate_accuracy import normalize_citations

    cites = [_span("a.py", 10, 20)]
    tally = ScoutTally(recovered_spanned=2, recovered_filelevel=1, dropped=0)
    norm = normalize_citations(cites, tally)
    assert norm.recovered_spanned == 2
    assert norm.recovered_filelevel == 1
    assert norm.effective == (_span("a.py", 10, 20),)


def test_normalize_citations_drops_malformed_into_normalization_dropped():
    # `dropped` (out-of-repo / nonexistent refs the SUT rejected) surfaces as
    # `normalization_dropped` — never silently re-bucketed as WRONG_FILE/EMPTY.
    from harpyja.eval.locate_accuracy import normalize_citations

    tally = ScoutTally(dropped=3)
    norm = normalize_citations([_span("a.py", 1, 2)], tally)
    assert norm.normalization_dropped == 3


def test_normalize_empty_only_after_drop_is_distinct_from_returned_nothing():
    # Two EMPTY-looking cases the taxonomy must keep DISTINCT: Scout dropped
    # everything (dropped>0) vs Scout genuinely returned nothing (dropped==0).
    from harpyja.eval.locate_accuracy import normalize_citations

    dropped_all = normalize_citations([], ScoutTally(dropped=4))
    returned_nothing = normalize_citations([], ScoutTally(dropped=0))
    assert dropped_all.effective == () and dropped_all.normalization_dropped == 4
    assert returned_nothing.effective == () and returned_nothing.normalization_dropped == 0


def test_normalize_citations_retains_file_level_shape():
    # A line-less (file-level, spec 0011) citation survives normalization as a
    # path-only citation — it is NOT coerced to a line range.
    from harpyja.eval.locate_accuracy import normalize_citations

    norm = normalize_citations([_span("a.py", None, None)], ScoutTally())
    assert len(norm.effective) == 1
    assert norm.effective[0].is_file_level is True


def test_normalize_citations_none_tally_is_zeroed():
    # No tally (tier never ran / not captured) → honest zeros, not a crash.
    from harpyja.eval.locate_accuracy import normalize_citations

    norm = normalize_citations([_span("a.py", 1, 2)], None)
    counts = (norm.normalization_dropped, norm.recovered_spanned, norm.recovered_filelevel)
    assert counts == (0, 0, 0)


# ---- AC1: the 4-way taxonomy — MECE + strict precedence --------------------
# Precedence: CORRECT > RIGHT_FILE_WRONG_SPAN > WRONG_FILE > EMPTY.
# window is the EvalConfig proximity window (pinned at 50 in the live run).

_GOLD = (_span("a.py", 100, 120),)
_W = 50


def test_classify_case_correct_on_line_overlap():
    from harpyja.eval.locate_accuracy import LocateBucket, classify_case

    bucket, flags = classify_case((_span("a.py", 110, 115),), _GOLD, window=_W)
    assert bucket is LocateBucket.CORRECT
    assert flags.within_window is False and flags.path_only_right_file is False


def test_classify_case_path_only_right_file_is_right_file_wrong_span():
    # oracle "file" (line-less, right file) is RE-MAPPED to RIGHT_FILE_WRONG_SPAN,
    # NOT CORRECT — the whole diagnostic point. path_only_right_file flag set.
    from harpyja.eval.locate_accuracy import LocateBucket, classify_case

    bucket, flags = classify_case((_span("a.py", None, None),), _GOLD, window=_W)
    assert bucket is LocateBucket.RIGHT_FILE_WRONG_SPAN
    assert flags.path_only_right_file is True


def test_classify_case_within_window_sets_within_window_flag():
    # right file, lined, misses gold but within `window` lines → RFWS + within_window.
    from harpyja.eval.locate_accuracy import LocateBucket, classify_case

    bucket, flags = classify_case((_span("a.py", 130, 140),), _GOLD, window=_W)
    assert bucket is LocateBucket.RIGHT_FILE_WRONG_SPAN
    assert flags.within_window is True


def test_classify_case_beyond_window_is_right_file_wrong_span_without_flag():
    # right file, lined, misses gold BEYOND the window → RFWS, no within_window.
    from harpyja.eval.locate_accuracy import LocateBucket, classify_case

    bucket, flags = classify_case((_span("a.py", 400, 410),), _GOLD, window=_W)
    assert bucket is LocateBucket.RIGHT_FILE_WRONG_SPAN
    assert flags.within_window is False


def test_classify_case_wrong_file_when_no_citation_in_gold_file():
    from harpyja.eval.locate_accuracy import LocateBucket, classify_case

    bucket, _ = classify_case((_span("z.py", 1, 5),), _GOLD, window=_W)
    assert bucket is LocateBucket.WRONG_FILE


def test_classify_case_empty_when_no_effective_citation():
    from harpyja.eval.locate_accuracy import LocateBucket, classify_case

    bucket, _ = classify_case((), _GOLD, window=_W)
    assert bucket is LocateBucket.EMPTY


def test_classify_case_multi_citation_precedence_takes_best():
    # a wrong-file AND a right-file(no span) citation → the BETTER bucket wins (RFWS).
    from harpyja.eval.locate_accuracy import LocateBucket, classify_case

    cites = (_span("z.py", 1, 5), _span("a.py", None, None))
    bucket, _ = classify_case(cites, _GOLD, window=_W)
    assert bucket is LocateBucket.RIGHT_FILE_WRONG_SPAN


def test_classify_case_correct_beats_right_file_wrong_span():
    # a line-overlap AND a path-only right-file citation in one case → CORRECT wins.
    from harpyja.eval.locate_accuracy import LocateBucket, classify_case

    cites = (_span("a.py", None, None), _span("a.py", 110, 115))
    bucket, _ = classify_case(cites, _GOLD, window=_W)
    assert bucket is LocateBucket.CORRECT


def test_classify_case_multi_gold_span_any_gold_file_counts():
    # gold has two files; a citation in the SECOND gold file (no line overlap) is RFWS.
    from harpyja.eval.locate_accuracy import LocateBucket, classify_case

    gold = (_span("a.py", 100, 120), _span("b.py", 5, 9))
    bucket, _ = classify_case((_span("b.py", None, None),), gold, window=_W)
    assert bucket is LocateBucket.RIGHT_FILE_WRONG_SPAN


def test_classify_case_is_mece_and_total_over_fixture_matrix():
    # Every fixture lands in exactly one bucket (totality) and the buckets are the
    # full enum (no case escapes classification).
    from harpyja.eval.locate_accuracy import LocateBucket, classify_case

    fixtures = [
        (_span("a.py", 110, 115),),      # CORRECT
        (_span("a.py", None, None),),    # RIGHT_FILE_WRONG_SPAN (path-only)
        (_span("a.py", 400, 410),),      # RIGHT_FILE_WRONG_SPAN (beyond window)
        (_span("z.py", 1, 5),),          # WRONG_FILE
        (),                              # EMPTY
    ]
    seen = set()
    for cites in fixtures:
        bucket, _ = classify_case(cites, _GOLD, window=_W)
        assert isinstance(bucket, LocateBucket)  # total: always a bucket
        seen.add(bucket)
    assert seen == {
        LocateBucket.CORRECT,
        LocateBucket.RIGHT_FILE_WRONG_SPAN,
        LocateBucket.WRONG_FILE,
        LocateBucket.EMPTY,
    }


# ---- AC2: two-granularity scoring + first-class gap ------------------------

def _classified(*buckets):
    # helper: turn a list of LocateBucket into the (bucket, SubFlags) pairs the
    # scorer consumes, with a trailing normalization_dropped count per case (0).
    from harpyja.eval.locate_accuracy import SubFlags

    return [(b, SubFlags(), 0) for b in buckets]


def test_file_level_and_span_level_computed_independently():
    from harpyja.eval.locate_accuracy import LocateBucket as B
    from harpyja.eval.locate_accuracy import score_distribution

    dist = score_distribution(
        _classified(B.CORRECT, B.RIGHT_FILE_WRONG_SPAN, B.WRONG_FILE, B.EMPTY)
    )
    # file-level = |CORRECT ∪ RFWS| / n = 2/4 ; span-level = |CORRECT| / n = 1/4.
    assert dist.file_level_accuracy == 0.5
    assert dist.span_level_accuracy == 0.25


def test_gap_is_first_class_all_path_only_file_one_span_zero():
    from harpyja.eval.locate_accuracy import LocateBucket as B
    from harpyja.eval.locate_accuracy import score_distribution

    # all cases found the file but never the span → FILE=1.0, SPAN=0.0, gap=1.0.
    dist = score_distribution(_classified(B.RIGHT_FILE_WRONG_SPAN, B.RIGHT_FILE_WRONG_SPAN))
    assert dist.file_level_accuracy == 1.0
    assert dist.span_level_accuracy == 0.0
    assert dist.gap == 1.0


def test_span_level_counts_only_correct():
    from harpyja.eval.locate_accuracy import LocateBucket as B
    from harpyja.eval.locate_accuracy import score_distribution

    dist = score_distribution(_classified(B.CORRECT, B.CORRECT, B.RIGHT_FILE_WRONG_SPAN))
    assert dist.span_level_accuracy == 2 / 3


def test_empty_rate_recorded_on_distribution():
    from harpyja.eval.locate_accuracy import LocateBucket as B
    from harpyja.eval.locate_accuracy import score_distribution

    dist = score_distribution(_classified(B.EMPTY, B.EMPTY, B.WRONG_FILE, B.CORRECT))
    assert dist.empty_rate == 0.5


def test_distribution_counts_are_mece_sum_to_n():
    from harpyja.eval.locate_accuracy import LocateBucket as B
    from harpyja.eval.locate_accuracy import score_distribution

    dist = score_distribution(
        _classified(B.CORRECT, B.RIGHT_FILE_WRONG_SPAN, B.WRONG_FILE, B.EMPTY, B.EMPTY)
    )
    assert dist.n == 5
    assert sum(dist.counts.values()) == dist.n


def test_distribution_normalization_dropped_total_summed():
    from harpyja.eval.locate_accuracy import LocateBucket as B
    from harpyja.eval.locate_accuracy import SubFlags, score_distribution

    classified = [(B.EMPTY, SubFlags(), 4), (B.WRONG_FILE, SubFlags(), 1)]
    dist = score_distribution(classified)
    assert dist.normalization_dropped_total == 5


def test_score_distribution_empty_population_is_zeroed():
    from harpyja.eval.locate_accuracy import score_distribution

    dist = score_distribution([])
    assert dist.n == 0
    assert dist.file_level_accuracy == 0.0
    assert dist.span_level_accuracy == 0.0
    assert dist.gap == 0.0
    assert dist.empty_rate == 0.0


# ---- AC7: the ordered typed-finding decision rule --------------------------

def _dist(*, n, correct, rfws, wrong, empty):
    # build a LocateDistribution directly from bucket counts (bypasses classify).
    from harpyja.eval.locate_accuracy import LocateBucket as B
    from harpyja.eval.locate_accuracy import LocateDistribution

    counts = {
        B.CORRECT: correct,
        B.RIGHT_FILE_WRONG_SPAN: rfws,
        B.WRONG_FILE: wrong,
        B.EMPTY: empty,
    }
    file_level = (correct + rfws) / n
    span_level = correct / n
    return LocateDistribution(
        n=n,
        counts=counts,
        file_level_accuracy=file_level,
        span_level_accuracy=span_level,
        gap=file_level - span_level,
        empty_rate=empty / n,
        normalization_dropped_total=0,
    )


def test_decide_finding_benchmark_unrepresentative_when_probe_fires():
    from harpyja.eval.locate_accuracy import FindingLabel, decide_finding

    # empty-dominant, low file-level, BUT the distilled probe cut the empty-rate.
    dist = _dist(n=10, correct=0, rfws=1, wrong=1, empty=8)
    finding = decide_finding(dist, delta_empty=0.5, representative=True)
    assert finding.label is FindingLabel.BENCHMARK_UNREPRESENTATIVE


def test_decide_finding_benchmark_unrepresentative_when_not_representative():
    from harpyja.eval.locate_accuracy import FindingLabel, decide_finding

    # empty-dominant/low-F and the representativeness judgment says "unrepresentative"
    # — rule 1's OR branch, no probe help needed.
    dist = _dist(n=10, correct=0, rfws=1, wrong=1, empty=8)
    finding = decide_finding(dist, delta_empty=0.0, representative=False)
    assert finding.label is FindingLabel.BENCHMARK_UNREPRESENTATIVE


def test_decide_finding_precision_fixable_when_gap_large_and_f_not_low():
    from harpyja.eval.locate_accuracy import FindingLabel, decide_finding

    # Scout finds files (F high) but misses spans (S low) → large gap.
    dist = _dist(n=10, correct=1, rfws=7, wrong=1, empty=1)  # F=0.8, S=0.1, gap=0.7
    finding = decide_finding(dist, delta_empty=0.0, representative=True)
    assert finding.label is FindingLabel.PRECISION_FIXABLE


def test_decide_finding_retrieval_fundamental_when_low_f_and_probe_flat():
    from harpyja.eval.locate_accuracy import FindingLabel, decide_finding

    # low file-level, empty-dominant, representative, and the probe did NOT help.
    dist = _dist(n=10, correct=0, rfws=1, wrong=1, empty=8)  # F=0.1, E=0.8
    finding = decide_finding(dist, delta_empty=0.0, representative=True)
    assert finding.label is FindingLabel.RETRIEVAL_FUNDAMENTAL


def test_decide_finding_mixed_when_no_dominant_mode():
    from harpyja.eval.locate_accuracy import FindingLabel, decide_finding

    # F not low, gap small, not empty-dominant, probe flat → no clean lead.
    dist = _dist(n=10, correct=4, rfws=1, wrong=3, empty=2)  # F=0.5, S=0.4, gap=0.1, E=0.2
    finding = decide_finding(dist, delta_empty=0.0, representative=True)
    assert finding.label is FindingLabel.MIXED


def test_decide_finding_evaluates_rules_in_declared_order():
    from harpyja.eval.locate_accuracy import FindingLabel, decide_finding

    # A distribution that satisfies BOTH rule 1 (empty-dominant + probe fires) AND
    # rule 2 (F not low + large gap): E=0.5, F=0.5, S=0.1, gap=0.4. Rule 1 wins.
    dist = _dist(n=10, correct=1, rfws=4, wrong=0, empty=5)
    assert dist.empty_rate == 0.5 and dist.file_level_accuracy == 0.5 and dist.gap == 0.4
    finding = decide_finding(dist, delta_empty=0.5, representative=True)
    assert finding.label is FindingLabel.BENCHMARK_UNREPRESENTATIVE


def test_decide_finding_records_observed_metrics_and_route():
    from harpyja.eval.locate_accuracy import decide_finding

    dist = _dist(n=10, correct=1, rfws=7, wrong=1, empty=1)
    finding = decide_finding(dist, delta_empty=0.0, representative=True)
    # the finding carries the observed numbers and a non-empty routed next-spec.
    assert finding.file_level_accuracy == 0.8
    assert finding.span_level_accuracy == 0.1
    assert finding.delta_empty == 0.0
    assert isinstance(finding.routes_to, str) and finding.routes_to


def test_decide_finding_bands_are_predeclared_named_constants():
    from harpyja.eval import locate_accuracy as la

    for name in ("LOW_FILE_BAND", "EMPTY_DOMINANT_BAND", "LARGE_GAP_BAND", "MATERIAL_DELTA_EMPTY"):
        assert hasattr(la, name), name
        assert isinstance(getattr(la, name), float)


# ---- AC10: no-SUT-change guard + frozen-oracle snapshot --------------------

def test_locate_accuracy_sut_surface_is_sanctioned_allowlist():
    # The module declares EXACTLY the frozen SUT names it is allowed to consume — a
    # behavior/allowlist lock, not a source grep. Widening it is a deliberate edit.
    from harpyja.eval.locate_accuracy import SUT_SURFACE

    assert SUT_SURFACE == frozenset(
        {
            "harpyja.eval.metrics.span_hit_kind",
            "harpyja.eval.metrics.span_hit_secondary",
            "harpyja.scout.engine.ScoutTally",
            "harpyja.server.types.CodeSpan",
        }
    )


def test_frozen_oracle_span_hit_kind_behavior_snapshot():
    # Pin the frozen oracle's verdicts the re-map depends on. Any edit to
    # metrics.span_hit_kind (line/file/None) breaks this lock (0020 P2 precedent).
    from harpyja.eval.metrics import span_hit_kind

    expected = _span("a.py", 100, 120)
    assert span_hit_kind(_span("a.py", 110, 115), expected) == "line"   # overlap
    assert span_hit_kind(_span("a.py", None, None), expected) == "file"  # path-only
    assert span_hit_kind(_span("a.py", 400, 410), expected) is None      # same file, disjoint
    assert span_hit_kind(_span("z.py", 110, 115), expected) is None      # wrong file


def test_locate_accuracy_makes_no_frozen_internal_reference():
    # The projection imports only the sanctioned surface — never Scout/orchestrator
    # internals (client, fastcontext, locate, gate, matrix, judge). Import-surface
    # check: a new coupling to a frozen internal fails here.
    import ast
    import pathlib

    src = pathlib.Path(__file__).with_name("locate_accuracy.py").read_text()
    tree = ast.parse(src)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
        elif isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
    forbidden = {
        "harpyja.scout.client",
        "harpyja.scout.wiring",
        "harpyja.orchestrator.locate",
        "harpyja.orchestrator.gate",
        "harpyja.orchestrator.matrix",
        "fastcontext",
    }
    assert not (imported & forbidden), imported & forbidden
    assert not any(m.startswith("fastcontext") for m in imported)
