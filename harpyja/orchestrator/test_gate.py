"""RED (spec 0008, T07): VerificationGate — scoring, top-N, air-gap (AC10, AC11).

Unit tests inject a fake judge so no model is touched; the gate reads the cited
lines back from a real tmp repo (the read-back is genuine, not mocked).
"""

from __future__ import annotations

import ipaddress
import logging
import socket

import pytest

from harpyja.config.settings import Settings
from harpyja.gateway.gateway import AirGapError, ModelGateway
from harpyja.orchestrator.gate import VerificationGate, _parse_score
from harpyja.server.types import Citation

LOOPBACK = "http://127.0.0.1:11434/v1"
REMOTE = "http://10.0.0.5:11434/v1"


def _settings(**kw) -> Settings:
    base = {"verify_threshold": 0.6, "verify_top_n": 3}
    base.update(kw)
    return Settings(**base)


def _repo_with_file(tmp_path, name="mod.py", lines=20):
    body = "\n".join(f"line {i}" for i in range(1, lines + 1))
    (tmp_path / name).write_text(body, encoding="utf-8")
    return str(tmp_path)


def _cite(path="mod.py", start=1, end=3):
    return Citation(path=path, start_line=start, end_line=end, source_tier=1)


class _CountingJudge:
    def __init__(self, score=0.9, raises=False):
        self.score = score
        self.raises = raises
        self.calls = 0

    def __call__(self, query: str, cited_text: str) -> float:
        self.calls += 1
        if self.raises:
            raise RuntimeError("judge backend exploded")
        return self.score


def _make_gate(judge):
    return VerificationGate(ModelGateway(api_base=LOOPBACK, model="scout"), judge=judge)


def test_gate_passes_when_score_at_or_above_threshold(tmp_path):
    repo = _repo_with_file(tmp_path)
    gate = _make_gate(_CountingJudge(0.9))
    outcome = gate.verify("find the thing", [_cite()], repo_path=repo, settings=_settings())
    assert outcome.passed is True
    assert outcome.failed is False
    assert outcome.score >= 0.6


def test_gate_fails_when_score_below_threshold(tmp_path):
    repo = _repo_with_file(tmp_path)
    gate = _make_gate(_CountingJudge(0.3))
    outcome = gate.verify("find the thing", [_cite()], repo_path=repo, settings=_settings())
    assert outcome.passed is False
    assert outcome.failed is False


def test_gate_scores_at_most_top_n_and_logs_dropped(tmp_path, caplog):
    repo = _repo_with_file(tmp_path, lines=40)
    cites = [_cite(start=i, end=i + 1) for i in range(1, 11)]  # 10 citations
    judge = _CountingJudge(0.9)
    gate = VerificationGate(ModelGateway(api_base=LOOPBACK, model="scout"), judge=judge)
    with caplog.at_level(logging.INFO):
        outcome = gate.verify("q", cites, repo_path=repo, settings=_settings(verify_top_n=3))
    assert judge.calls <= 3
    assert outcome.scored_count == 3
    assert outcome.dropped_count == 7
    # The dropped count is logged so a bounded scan is never indistinguishable
    # from a full one (no-silent-truncation).
    assert "7" in caplog.text


def test_gate_asserts_local_before_judge(tmp_path):
    repo = _repo_with_file(tmp_path)
    judge = _CountingJudge(0.9)
    gate = VerificationGate(ModelGateway(api_base=REMOTE, model="scout"), judge=judge)
    with pytest.raises(AirGapError):
        gate.verify("q", [_cite()], repo_path=repo, settings=_settings())
    # The judge is never called when the air-gap floor trips.
    assert judge.calls == 0


def test_gate_scoring_failed_when_judge_raises(tmp_path):
    repo = _repo_with_file(tmp_path)
    judge = _CountingJudge(raises=True)
    gate = VerificationGate(ModelGateway(api_base=LOOPBACK, model="scout"), judge=judge)
    # No exception escapes; the gate cannot vouch → failed.
    outcome = gate.verify("q", [_cite()], repo_path=repo, settings=_settings())
    assert outcome.failed is True
    assert outcome.passed is False


# --- Spec 0017 (B3): gate degrades on judge timeout, visibly (AC5, AC6) ---


def _timeout_judge(query: str, cited_text: str) -> float:
    raise TimeoutError("simulated judge read timeout")


def _runtime_judge(query: str, cited_text: str) -> float:
    raise RuntimeError("judge backend exploded")


def test_gate_degrades_on_judge_timeout(tmp_path):
    # AC5 (load-bearing): a timed-out judge degrades gracefully — no raise, not a
    # silent pass. This is exactly the path a finite gateway timeout now reaches.
    repo = _repo_with_file(tmp_path)
    gate = VerificationGate(ModelGateway(api_base=LOOPBACK, model="scout"), judge=_timeout_judge)
    outcome = gate.verify("q", [_cite()], repo_path=repo, settings=_settings())
    assert outcome.failed is True
    assert outcome.passed is False


def _warning_messages(caplog) -> list[str]:
    # The record MESSAGE only (never the exc_info traceback) — so a match proves the
    # message itself names the cause, not merely that the exception class appears in
    # a formatted traceback.
    return [r.getMessage().lower() for r in caplog.records if r.levelno == logging.WARNING]


def test_gate_logs_timeout_naming_warning_on_timeout(tmp_path, caplog):
    # AC6 / D4: the timeout degrade is DISTINGUISHABLE — a WARNING whose MESSAGE
    # names the timeout, so operators can separate "judge timed out" from others.
    repo = _repo_with_file(tmp_path)
    gate = VerificationGate(ModelGateway(api_base=LOOPBACK, model="scout"), judge=_timeout_judge)
    with caplog.at_level(logging.WARNING):
        gate.verify("q", [_cite()], repo_path=repo, settings=_settings())
    msgs = _warning_messages(caplog)
    assert any("timed out" in m or "timeout" in m for m in msgs)


def test_gate_timeout_log_distinct_from_parse_failure(tmp_path, caplog):
    # AC6: a non-timeout failure logs the GENERIC "scoring failed" message and NOT
    # the timeout-naming one — the two degrade causes are separable in diagnostics.
    repo = _repo_with_file(tmp_path)
    gate = VerificationGate(ModelGateway(api_base=LOOPBACK, model="scout"), judge=_runtime_judge)
    with caplog.at_level(logging.WARNING):
        gate.verify("q", [_cite()], repo_path=repo, settings=_settings())
    msgs = _warning_messages(caplog)
    assert any("scoring failed" in m for m in msgs)
    assert not any("timed out" in m or "timeout" in m for m in msgs)


@pytest.mark.integration
def test_gate_runs_under_network_deny_loopback_only(tmp_path, monkeypatch):
    """AC10 (integration): the assembled gate scores via the loopback Gateway and
    makes **zero** non-loopback egress (the Scout/Deep network-deny pattern)."""
    repo = _repo_with_file(tmp_path)

    real_connect = socket.socket.connect
    tripped: list[str] = []

    def guarded_connect(self, address):
        host = address[0] if isinstance(address, tuple) else address
        try:
            is_loopback = ipaddress.ip_address(host).is_loopback
        except ValueError as err:
            tripped.append(str(host))
            raise OSError("network-deny: name resolution blocked") from err
        if not is_loopback:
            tripped.append(str(host))
            raise OSError("network-deny: non-loopback blocked")
        return real_connect(self, address)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)

    gateway = ModelGateway(api_base=LOOPBACK, model="scout")

    def loopback_transport(url, payload):
        # Stand-in for the local model; stays in-process, no real socket.
        return {"choices": [{"message": {"content": "0.9"}}]}

    def judge(query, cited_text):
        reply = gateway.complete(
            [{"role": "user", "content": query}], transport=loopback_transport
        )
        return float(reply)

    gate = VerificationGate(gateway, judge=judge)
    outcome = gate.verify("find the thing", [_cite()], repo_path=repo, settings=_settings())

    assert outcome.passed is True
    assert tripped == []  # the judge path made no non-loopback egress


# --- Spec 0018 (B2): strict `_parse_score` — score-shaped in, everything else None ---


@pytest.mark.parametrize(
    ("reply", "expected"),
    [
        ("0.8", 0.8),
        ("0.0", 0.0),
        ("1.0", 1.0),
        ("1", 1.0),
        ("0", 0.0),
        ("1.", 1.0),
        ("Score: 0.8", 0.8),
        ("Score: 0.8.", 0.8),
        ("  0.42  ", 0.42),
    ],
)
def test_parse_score_conforming_returns_value(reply, expected):
    # AC5: a conforming reply is a bare [0,1] score (an optional `Score:` label and a
    # single trailing period tolerated). It parses to that value.
    assert _parse_score(reply) == pytest.approx(expected)


@pytest.mark.parametrize(
    "reply",
    [
        "219",  # a bare line number — the exact B2 regression (must NOT clamp to 1.0)
        "…at line 219…",
        "Score: 219",  # even with the label, an out-of-range value is non-conforming
        "1.2",  # out of [0,1]
        "-0.1",  # out of [0,1]
        "0, because the span is unrelated",  # prose after the number (D6)
        "",  # empty
        "n/a",  # no number
    ],
)
def test_parse_score_nonconforming_returns_none(reply):
    # AC5 / D2: anything that is not exactly a bare [0,1] score returns None — the
    # gate must degrade on it, never fabricate a 1.0 pass or a 0.0 reject.
    assert _parse_score(reply) is None


# --- Spec 0018 (B2): the instruct-model judge (model, prompt, air-gap) ---


def _spy_complete_gateway(monkeypatch, api_base=LOOPBACK, reply="0.7"):
    """A gateway whose `complete` records the model/params/messages it was called with."""
    gateway = ModelGateway(api_base=api_base, model="unused")
    captured: dict = {}

    def spy_complete(messages, **params):
        captured["messages"] = messages
        captured["params"] = params
        return reply

    monkeypatch.setattr(gateway, "complete", spy_complete)
    return gateway, captured


def test_instruct_judge_scores_via_lm_model_not_scout_model(monkeypatch):
    # AC3: the instruct judge scores via `lm_model` (an in-distribution instruct model),
    # NOT the OOD finder `scout_model`, at temperature 0.
    from harpyja.orchestrator.gate import make_instruct_judge

    settings = _settings()
    gateway, captured = _spy_complete_gateway(monkeypatch, reply="0.7")
    judge = make_instruct_judge(gateway, settings)
    score = judge("find the thing", "def f(): ...")
    assert captured["params"]["model"] == settings.lm_model
    assert captured["params"]["model"] != settings.scout_model
    assert captured["params"]["temperature"] == 0
    assert score == pytest.approx(0.7)


def test_instruct_judge_prompt_demands_bare_number(monkeypatch):
    # AC4: the prompt constrains the reply to only a number in [0,1] (no prose) — a
    # stable, greppable instruction contract.
    from harpyja.orchestrator.gate import make_instruct_judge

    gateway, captured = _spy_complete_gateway(monkeypatch, reply="0.5")
    judge = make_instruct_judge(gateway, _settings())
    judge("q", "span")
    text = " ".join(m["content"] for m in captured["messages"]).lower()
    assert "number" in text
    assert "0" in text and "1" in text  # the [0,1] range is stated
    assert "only" in text  # a *bare* number is demanded (no prose)


def test_instruct_judge_asserts_local_before_egress(monkeypatch):
    # AC9: air-gap is preserved — a non-loopback gateway raises AirGapError and the
    # judge model is NEVER reached (parallel to 0017 AC9).
    import harpyja.gateway.gateway as gw
    from harpyja.orchestrator.gate import make_instruct_judge

    sent = {"called": False}

    def spy_transport(url, payload, **kw):
        sent["called"] = True
        return {"choices": [{"message": {"content": "0.5"}}]}

    monkeypatch.setattr(gw, "_default_transport", spy_transport)
    gateway = ModelGateway(api_base=REMOTE, model="unused")
    judge = make_instruct_judge(gateway, _settings())
    with pytest.raises(AirGapError):
        judge("q", "span")
    assert sent["called"] is False  # egress never happened


def test_instruct_judge_nonconforming_reply_degrades_not_fabricates(tmp_path, monkeypatch):
    # AC6: a non-conforming judge reply ("219", a bare line number) degrades the gate
    # (failed=True, passed=False) and NEVER fabricates a 1.0 pass from the line number.
    from harpyja.orchestrator.gate import make_instruct_judge

    repo = _repo_with_file(tmp_path)
    gateway, _ = _spy_complete_gateway(monkeypatch, reply="219")
    gate = VerificationGate(gateway, judge=make_instruct_judge(gateway, _settings()))
    outcome = gate.verify("q", [_cite()], repo_path=repo, settings=_settings())
    assert outcome.failed is True
    assert outcome.passed is False
    assert outcome.score != 1.0  # not a fabricated pass, not a line-number-derived score


def test_gate_whole_gate_degrades_on_single_nonconforming_reply(tmp_path, monkeypatch):
    # AC6 / D7: a single non-conforming reply degrades the WHOLE verify call (a model
    # not following the bare-number instruction is suspect for the entire batch), not a
    # per-span partial pass.
    from harpyja.orchestrator.gate import make_instruct_judge

    repo = _repo_with_file(tmp_path, lines=40)
    cites = [_cite(start=1, end=3), _cite(start=5, end=7)]
    gateway, _ = _spy_complete_gateway(monkeypatch, reply="219")
    gate = VerificationGate(gateway, judge=make_instruct_judge(gateway, _settings()))
    outcome = gate.verify("q", cites, repo_path=repo, settings=_settings(verify_top_n=3))
    assert outcome.failed is True
    assert outcome.passed is False


def _nonconformance_gate(tmp_path, monkeypatch):
    from harpyja.orchestrator.gate import make_instruct_judge

    repo = _repo_with_file(tmp_path)
    gateway, _ = _spy_complete_gateway(monkeypatch, reply="219")
    gate = VerificationGate(gateway, judge=make_instruct_judge(gateway, _settings()))
    return gate, repo


def test_gate_logs_single_nonconformance_warning(tmp_path, monkeypatch, caplog):
    # AC7 / D4: the non-conformance degrade logs EXACTLY ONE WARNING whose record
    # message names the parse non-conformance (separable in operator diagnostics).
    gate, repo = _nonconformance_gate(tmp_path, monkeypatch)
    with caplog.at_level(logging.WARNING):
        gate.verify("q", [_cite()], repo_path=repo, settings=_settings())
    nonconf = [m for m in _warning_messages(caplog) if "non-conforming" in m or "parse" in m]
    assert len(nonconf) == 1


def test_gate_nonconformance_warning_absent_generic_scoring_failed(tmp_path, monkeypatch, caplog):
    # AC7 (the 0017 double-emit lesson): a ScoreParseError must NOT also trip the
    # generic "scoring failed" WARNING — exactly one message, not two.
    gate, repo = _nonconformance_gate(tmp_path, monkeypatch)
    with caplog.at_level(logging.WARNING):
        gate.verify("q", [_cite()], repo_path=repo, settings=_settings())
    assert not any("scoring failed" in m for m in _warning_messages(caplog))


def test_gate_nonconformance_warning_distinct_from_timeout(tmp_path, monkeypatch, caplog):
    # AC7: the non-conformance message is distinct from the 0017 timeout WARNING.
    gate, repo = _nonconformance_gate(tmp_path, monkeypatch)
    with caplog.at_level(logging.WARNING):
        gate.verify("q", [_cite()], repo_path=repo, settings=_settings())
    assert not any("timed out" in m or "timeout" in m for m in _warning_messages(caplog))


def test_both_judges_degrade_identically_on_nonconforming_reply(tmp_path, monkeypatch, caplog):
    # AC13: `_parse_score` is shared plumbing — both `make_instruct_judge` and the
    # retained `make_scout_model_judge` must degrade IDENTICALLY on a non-conforming
    # reply (failed=True, passed=False, one non-conformance WARNING). The retained
    # finder judge cannot silently keep the old fabricating behavior.
    from harpyja.orchestrator.gate import make_instruct_judge, make_scout_model_judge

    repo = _repo_with_file(tmp_path)
    results = {}
    for name, factory in (("instruct", make_instruct_judge), ("scout", make_scout_model_judge)):
        gateway, _ = _spy_complete_gateway(monkeypatch, reply="219")
        gate = VerificationGate(gateway, judge=factory(gateway, _settings()))
        caplog.clear()
        with caplog.at_level(logging.WARNING):
            outcome = gate.verify("q", [_cite()], repo_path=repo, settings=_settings())
        nonconf = [m for m in _warning_messages(caplog) if "non-conforming" in m or "parse" in m]
        results[name] = (outcome.failed, outcome.passed, len(nonconf))
    assert results["instruct"] == (True, False, 1)
    assert results["scout"] == results["instruct"]  # identical degrade


def test_gate_passes_correct_citation_with_good_score(tmp_path, monkeypatch):
    # AC10: the inverted-harm regression — a correctly-scored correct citation PASSES
    # (the 0015 gate false-rejected it). This is a PLUMBING proof (faked score via the
    # instruct judge over a spy'd `complete`), NOT a live-model accuracy claim; the
    # `verify_threshold=0.6` operating point over the new score distribution is untested
    # and its calibration is deferred to the OQ2 re-run.
    from harpyja.orchestrator.gate import make_instruct_judge

    repo = _repo_with_file(tmp_path)
    gateway, _ = _spy_complete_gateway(monkeypatch, reply="0.9")
    gate = VerificationGate(gateway, judge=make_instruct_judge(gateway, _settings()))
    outcome = gate.verify("q", [_cite()], repo_path=repo, settings=_settings())
    assert outcome.passed is True
    assert outcome.failed is False
    assert outcome.score >= _settings().verify_threshold


# --- Spec 0018 (B2): optional live instruct-judge smoke (AC11) ---


def _endpoint_reachable(host, port, timeout=1.0):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


@pytest.mark.integration
def test_instruct_judge_live_smoke():
    """AC11: against a served `lm_model`, the instruct judge returns a PARSEABLE [0,1]
    score for a trivially relevant span. Skip-not-fail — a wiring/parse smoke only, NOT
    an accuracy or calibration claim; the gate's operating point is the OQ2 re-run's job.
    """
    from urllib.parse import urlsplit

    from harpyja.orchestrator.gate import ScoreParseError, make_instruct_judge

    settings = Settings()
    parts = urlsplit(settings.lm_api_base)
    host, port = parts.hostname or "127.0.0.1", parts.port or 11434
    if not _endpoint_reachable(host, port, timeout=1.0):
        pytest.skip(f"no local model endpoint reachable at {host}:{port}")

    gateway = ModelGateway(
        api_base=settings.lm_api_base,
        allow_remote=settings.allow_remote,
        timeout_s=settings.lm_http_timeout_s,
    )
    judge = make_instruct_judge(gateway, settings)
    span = "def add(a, b):\n    return a + b  # adds two numbers"
    try:
        score = judge("a function that adds two numbers", span)
    except ScoreParseError as err:  # model reachable but didn't emit a bare number
        pytest.skip(f"instruct model reachable but reply non-conforming (not a bug): {err!r}")
    except Exception as err:  # missing model / HTTP error is not a wiring regression
        pytest.skip(f"endpoint reachable but complete() errored: {err!r}")
    assert isinstance(score, float)
    assert 0.0 <= score <= 1.0  # parseable and in-range


# --- Spec 0011 (citation-shape): file-level (line-less) citation is not-verifiable ---


def _file_level_cite(path="mod.py"):
    return Citation(path=path, start_line=None, end_line=None, source_tier=1)


def test_gate_skips_file_level_citation_as_not_verifiable(tmp_path):
    # AC13: a file-level citation has no lines to read back. The gate detects it
    # BEFORE read-back (no crash), does NOT score it, does NOT record a verified
    # pass, and flags skipped_reason="no-line-range".
    repo = _repo_with_file(tmp_path)
    judge = _CountingJudge(0.9)
    gate = _make_gate(judge)
    outcome = gate.verify("q", [_file_level_cite()], repo_path=repo, settings=_settings())
    assert outcome.skipped_reason == "no-line-range"
    assert outcome.passed is False
    assert outcome.scored_count == 0
    assert judge.calls == 0  # never read/scored a line-less span


def test_gate_skipped_reason_distinct_from_scoring_failure(tmp_path):
    # AC13: not-verifiable (skipped_reason set, failed=False) is a DISTINCT state
    # from could-not-vouch (failed=True, skipped_reason None).
    repo = _repo_with_file(tmp_path)
    skipped = _make_gate(_CountingJudge(0.9)).verify(
        "q", [_file_level_cite()], repo_path=repo, settings=_settings()
    )
    failed = _make_gate(_CountingJudge(raises=True)).verify(
        "q", [_cite()], repo_path=repo, settings=_settings()
    )
    assert (skipped.skipped_reason, skipped.failed) == ("no-line-range", False)
    assert (failed.skipped_reason, failed.failed) == (None, True)


def test_gate_scores_lined_citations_alongside_file_level(tmp_path):
    # A mix: the lined citation is scored normally; the file-level one only sets
    # the marker. The verdict comes from the lined score.
    repo = _repo_with_file(tmp_path)
    judge = _CountingJudge(0.9)
    outcome = _make_gate(judge).verify(
        "q", [_cite(), _file_level_cite()], repo_path=repo, settings=_settings()
    )
    assert outcome.passed is True  # lined score 0.9 >= 0.6
    assert outcome.scored_count == 1
    assert outcome.skipped_reason == "no-line-range"
    assert judge.calls == 1
