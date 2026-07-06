"""Spec 0022 (AC4/AC5/AC6) — live Scout-only locate probe (integration).

`@pytest.mark.integration`, gated through `require_live_stack`: on a host WITHOUT a
served 4B stack the tests SKIP (CI-safe); with `HARPYJA_REQUIRE_LIVE_STACK=1` set they
HARD-FAIL instead of skipping (the intentional closure run must not go green by
skipping — a skip may mask a broken stack). Scout runs in ISOLATION (no gate/judge/
Deep) driving the native explorer backend (spec 0025); turns-used is read from the
explorer's native `last_turns_used` seam, and the distribution is REGENERATED (not
inheriting 0021's contaminated counts). Includes the AC8 cutover proof: the eval
instrument runs end-to-end through the explorer with zero non-loopback egress.
"""

from __future__ import annotations

import shutil

import pytest

from harpyja.eval.locate_probe import (
    build_scout_only_stack,
    require_live_stack,
    run_locate_probe,
    run_paired_reformulation_probe,
    run_reformulation_probe,
    scout_stack_available,
)
from harpyja.eval.test_eval_integration import (
    _NEEDS_STACK,
    _deny_nonloopback_egress,
    _settings_live,
)
from harpyja.eval.test_swebench_integration import _LEGACY, _live_cases
from harpyja.scout.errors import ScoutUnavailable

_WINDOW = 50
# Scout-only availability — NOT the Deep-oriented `_live_stack_available` (which
# requires Deno + the Deep model, both irrelevant to a Scout probe and would
# false-skip a Scout-capable host).
_NEEDS_SCOUT = _NEEDS_STACK + " (Scout-only: rg + served tool-calling Scout endpoint)"


def _gate() -> None:
    action = require_live_stack(scout_stack_available(_settings_live()))
    if action == "skip":
        pytest.skip(_NEEDS_SCOUT)
    if action == "fail":
        pytest.fail(_NEEDS_SCOUT + " (HARPYJA_REQUIRE_LIVE_STACK set)")


def _distill(query: str) -> str:
    """A cheap one-line distillation: the issue's first non-empty line, clamped."""
    for line in query.splitlines():
        if line.strip():
            return line.strip()[:120]
    return query[:120]


def _legacy_repo(tmp_path) -> str:
    repo = str(tmp_path / "legacy")
    shutil.copytree(_LEGACY, repo)
    return repo


@pytest.mark.integration
def test_scout_only_stratified_regenerated_distribution(tmp_path):
    _gate()
    repo = _legacy_repo(tmp_path)
    stack = build_scout_only_stack(_settings_live(), repo)
    cases = _live_cases(repo, cap=2)
    res = run_locate_probe(cases, stack=stack, repo_path=repo, window=_WINDOW)
    assert res.distribution.n == len(cases)
    assert 0.0 <= res.distribution.empty_rate <= 1.0
    assert 0.0 <= res.distribution.file_level_accuracy <= 1.0
    # regenerated evidence: one auditable row per case (AC8).
    assert len(res.rows) == res.distribution.n


# --- Spec 0025 (T16/T17, AC8): the live cutover proof ------------------------


def _scout_cutover_settings():
    # The live cutover runs on the DEFAULT tool-calling Scout model (Qwen3-8B on
    # loopback Ollama, per repo memory) — NOT the Deep driver `_DEEP_MODEL`. This is
    # the explorer's own model, not the retired FastContext-4B.
    from dataclasses import replace

    from harpyja.config.settings import Settings

    return replace(Settings(), lm_api_base="http://127.0.0.1:11434/v1")


@pytest.mark.integration
def test_cutover_eval_instrument_runs_through_explorer_zero_egress(tmp_path):
    # AC8 — the cutover proof: the eval instrument runs end-to-end driving the
    # EXPLORER (the sole Scout backend post-0025) to a parsed citation list, with the
    # turns-used diagnostic reading the explorer's NATIVE seam ("explorer"), and ZERO
    # non-loopback egress observed (not merely asserted). The stack is Qwen3-8B on
    # loopback Ollama; the gateway pins that served tag (model="local" would 404).
    settings = _scout_cutover_settings()
    if require_live_stack(scout_stack_available(settings)) == "skip":
        pytest.skip(_NEEDS_SCOUT)
    if require_live_stack(scout_stack_available(settings)) == "fail":
        pytest.fail(_NEEDS_SCOUT + " (HARPYJA_REQUIRE_LIVE_STACK set)")

    repo = _legacy_repo(tmp_path)
    cases = _live_cases(repo, cap=1)
    try:
        with _deny_nonloopback_egress():
            stack = build_scout_only_stack(settings, repo)
            res = run_locate_probe(cases, stack=stack, repo_path=repo, window=_WINDOW)
    except ScoutUnavailable as err:
        # The endpoint's TCP port is open but the served model isn't usable (e.g. the
        # tag isn't pulled) — the STACK is unavailable, not the cutover broken. Skip
        # unless the closure run demands a hard stack (HARPYJA_REQUIRE_LIVE_STACK).
        if require_live_stack(False) == "fail":
            pytest.fail(f"{_NEEDS_SCOUT}: cutover run degraded ({err.cause})")
        pytest.skip(f"{_NEEDS_SCOUT}: served model not usable ({err.cause})")

    # The instrument produced a regenerated distribution through the explorer.
    assert res.distribution.n == len(cases)
    assert len(res.rows) == res.distribution.n
    # Turns-used came from the explorer's native seam (the migrated diagnostic works
    # live), or is honestly "unavailable" — never the retired trajectory scrape.
    assert res.turns_used_source in ("explorer", "unavailable")
    if res.turns_used_source == "explorer":
        assert res.turns_used is not None and all(t >= 1 for t in res.turns_used)


@pytest.mark.integration
def test_turns_used_and_suffix_recovery_recorded_at_eval_boundary(tmp_path):
    _gate()
    repo = _legacy_repo(tmp_path)
    stack = build_scout_only_stack(_settings_live(), repo)
    res = run_locate_probe(
        _live_cases(repo, cap=1), stack=stack, repo_path=repo, window=_WINDOW
    )
    # turns-used comes from the explorer's native per-run count (spec 0025) or is
    # honestly "unavailable" — never fabricated, never scraped from a trajectory.
    assert res.turns_used_source in ("explorer", "unavailable")
    if res.turns_used_source == "explorer":
        assert res.turns_used is not None and all(t >= 0 for t in res.turns_used)
    # suffix-recovery totals are read off ScoutTally at the eval boundary (spec 0025
    # keeps the shared tally core; recovered counts read zero post-cutover).
    assert res.recovered_spanned_total >= 0
    assert res.recovered_filelevel_total >= 0


@pytest.mark.integration
def test_reformulation_probe_raw_vs_distilled_empty_rate_delta(tmp_path):
    _gate()
    repo = _legacy_repo(tmp_path)
    stack = build_scout_only_stack(_settings_live(), repo)
    res = run_reformulation_probe(
        _live_cases(repo, cap=2), stack=stack, repo_path=repo, window=_WINDOW, distill=_distill
    )
    assert 0.0 <= res.raw_empty_rate <= 1.0
    assert 0.0 <= res.distilled_empty_rate <= 1.0
    assert res.delta_empty == res.raw_empty_rate - res.distilled_empty_rate


@pytest.mark.integration
def test_locate_probe_no_nonloopback_egress(tmp_path):
    _gate()
    repo = _legacy_repo(tmp_path)
    stack = build_scout_only_stack(_settings_live(), repo)
    # The Scout-only run must make no non-loopback call (air-gap holds end to end).
    with _deny_nonloopback_egress():
        res = run_locate_probe(
            _live_cases(repo, cap=1), stack=stack, repo_path=repo, window=_WINDOW
        )
    assert res.distribution.n == 1


# ---- Spec 0023 (AC1/AC8): live paired reformulation probe ------------------
# NOTE: on the terse legacy fixtures the raw arm is NOT a real multi-paragraph issue,
# so `is_raw_issue` excludes them and `usable_n` is honestly small (delta≈0 by
# construction). These tests pin the instrument's SHAPE and air-gap end-to-end; the
# real discriminator needs operator SWE-bench long-issue cases (see findings.md).


@pytest.mark.integration
def test_paired_reformulation_probe_records_both_arms(tmp_path):
    from harpyja.eval.distill import mechanical_distill

    _gate()
    repo = _legacy_repo(tmp_path)
    stack = build_scout_only_stack(_settings_live(), repo)
    res = run_paired_reformulation_probe(
        _live_cases(repo, cap=2),
        stack=stack,
        repo_path=repo,
        window=_WINDOW,
        mechanical=mechanical_distill,
    )
    # per-case pairs (AC3) — one row per USABLE case; deltas are bounded.
    assert res.usable_n == len(res.paired_rows)
    assert -1.0 <= res.delta_empty <= 1.0
    assert -1.0 <= res.delta_file_accuracy <= 1.0
    assert res.discordant_pairs >= 0


@pytest.mark.integration
def test_paired_probe_raw_provenance_and_usable_n(tmp_path):
    _gate()
    repo = _legacy_repo(tmp_path)
    stack = build_scout_only_stack(_settings_live(), repo)
    cases = _live_cases(repo, cap=2)
    res = run_paired_reformulation_probe(
        cases, stack=stack, repo_path=repo, window=_WINDOW
    )
    # every case is accounted for: usable + excluded == total (AC8).
    assert res.usable_n + len(res.excluded_case_ids) == len(cases)


@pytest.mark.integration
def test_paired_probe_no_nonloopback_egress(tmp_path):
    _gate()
    repo = _legacy_repo(tmp_path)
    stack = build_scout_only_stack(_settings_live(), repo)
    with _deny_nonloopback_egress():
        res = run_paired_reformulation_probe(
            _live_cases(repo, cap=1), stack=stack, repo_path=repo, window=_WINDOW
        )
    assert res.usable_n + len(res.excluded_case_ids) == 1
