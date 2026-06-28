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
from harpyja.orchestrator.gate import VerificationGate
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
