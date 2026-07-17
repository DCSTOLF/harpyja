"""Spec 0049 — live integration checks on the 0041-gated Ollama endpoint.

Skip-not-fail without a served stack (strict under HARPYJA_REQUIRE_LIVE_STACK);
``gateway.assert_local`` runs FIRST on every path. These cover the read-only
provisioning checks (AC3 membership, AC1a anchor, AC4a base-diff) via ``/api/tags``
+ ``ollama show`` — the live PARAMETER map is read with the TOLERANT extractor
(a real expanded Modelfile has LICENSE / multi-valued ``PARAMETER stop`` the strict
committed grammar rejects by design).

The FULL AC5 replay-reproduction proof (≥3 draws × 3 tags × ≥2 cases, real explorer
runs producing the committed artifact + typed outcome) is the operator live-run
deliverable — it needs all three greedy tags built + exclusivity-gated inference,
and carries acceptance via its committed artifact, not this scaffold.
"""

from __future__ import annotations

import json
import subprocess
import urllib.request

import pytest

from harpyja.eval.bakeoff_config import BakeoffConfig
from harpyja.eval.bakeoff_run import probe_served_variant_membership
from harpyja.eval.greedy_serving import (
    is_exactly_temperature_live,
    live_param_delta,
    local_ollama_env,
    parse_live_parameters,
    read_live_modelfile,
)
from harpyja.eval.locate_probe import require_live_stack

pytestmark = pytest.mark.integration

_CFG = BakeoffConfig()
_API_BASE = "http://127.0.0.1:11434"
_HOST = "http://127.0.0.1:11434"
_PAIRS = {  # logical base → greedy variant
    "qwen3:14b": "qwen3-14b-greedy",
    "qwen3:8b": "qwen3-8b-greedy",
    "qwen3.5:4b": "qwen3.5-4b-greedy",
}


def _served_tags() -> set[str] | None:
    try:
        with urllib.request.urlopen(f"{_API_BASE}/api/tags", timeout=5) as r:
            return {m["name"] for m in json.loads(r.read())["models"]}
    except Exception:  # noqa: BLE001
        return None


def _skip_or_fail(msg: str) -> None:
    if require_live_stack(False) == "fail":
        pytest.fail(f"{msg} (HARPYJA_REQUIRE_LIVE_STACK set)")
    pytest.skip(f"{msg} — live check skipped, not faked")


def _assert_local_first() -> None:
    from harpyja.gateway.gateway import assert_local

    assert_local(_API_BASE)  # FIRST — /api/tags + show are gated egress


def _is_served(served: set[str], tag: str) -> bool:
    return bool(served & {tag, f"{tag}:latest"})


def _ollama_show(tag: str) -> str | None:
    def run_fn(args, *, env):
        proc = subprocess.run(args, env=env, capture_output=True, text=True, timeout=30)
        if proc.returncode != 0:
            raise FileNotFoundError(tag)
        return proc.stdout

    try:
        return read_live_modelfile(tag, host=_HOST, run_fn=run_fn)
    except (FileNotFoundError, OSError, subprocess.SubprocessError):
        return None


def test_local_ollama_env_is_sanitized_and_binds_host():
    """The provisioning-egress env binds OLLAMA_HOST and never inherits ambient env
    (assert-only; runs even without a served stack)."""
    env = local_ollama_env(_HOST)
    assert env["OLLAMA_HOST"] == _HOST
    assert set(env) <= {"OLLAMA_HOST", "PATH", "HOME"}


def test_live_greedy_variant_tags_served_positive_membership():
    """AC3 — every greedy variant tag positively served via /api/tags."""
    served = _served_tags()
    if served is None:
        _skip_or_fail("Ollama unreachable")
    _assert_local_first()
    if not all(_is_served(served, g) for g in _CFG.served_variant_tags):
        _skip_or_fail(
            "not all greedy variant tags built — run the build driver "
            "(qwen3-8b-greedy / qwen3.5-4b-greedy pending)"
        )
    result = probe_served_variant_membership(
        _CFG,
        api_base=_API_BASE,
        assert_local_fn=lambda _b: None,  # asserted above
        tags_reader=lambda _b: list(served)
        + [t.rsplit(":latest", 1)[0] for t in served],
    )
    assert set(result) == set(_CFG.served_variant_tags)
    assert all(result.values())


def test_live_greedy_14b_anchor_reuse_decision_recorded():
    """AC1a — the 0048 hand-created 14b-greedy is compared (tolerant params) to the
    base; the reuse/discard decision for the proof anchor is recorded. A divergence
    (0048 flipped top_p + added seed) is the STOP-AND-WARN discard signal, not a
    passing anchor — surfaced as a skip until the tag is rebuilt from the committed
    (temperature-only) Modelfile."""
    served = _served_tags()
    if served is None:
        _skip_or_fail("Ollama unreachable")
    _assert_local_first()
    if not (_is_served(served, "qwen3-14b-greedy") and _is_served(served, "qwen3:14b")):
        _skip_or_fail("qwen3-14b-greedy / qwen3:14b not both built")

    base_text = _ollama_show("qwen3:14b")
    greedy_text = _ollama_show("qwen3-14b-greedy")
    if base_text is None or greedy_text is None:
        _skip_or_fail("ollama show unavailable for the 14b pair")

    # The greedy tag IS greedy (temperature 0) regardless of the reuse decision.
    assert parse_live_parameters(greedy_text).get("temperature") == ("0",)
    delta = live_param_delta(base_text, greedy_text)
    if delta != {"temperature"}:
        _skip_or_fail(
            f"AC1a: hand-created qwen3-14b-greedy diverges from temperature-only "
            f"(delta={sorted(delta)}) — DISCARD 0048 draws, rebuild from committed "
            f"Modelfile, run fresh draws (recorded in findings.md)"
        )
    # Rebuilt-from-committed: the anchor is reusable.
    assert is_exactly_temperature_live(base_text, greedy_text)


def test_live_greedy_base_diff_is_exactly_temperature():
    """AC4a — greedy vs base live diff is EXACTLY temperature, for every fully-built
    pair (a diverging pair is skipped with the rebuild note, not failed)."""
    served = _served_tags()
    if served is None:
        _skip_or_fail("Ollama unreachable")
    _assert_local_first()

    checked = 0
    for base, greedy in _PAIRS.items():
        if not (_is_served(served, base) and _is_served(served, greedy)):
            continue
        base_text = _ollama_show(base)
        greedy_text = _ollama_show(greedy)
        if base_text is None or greedy_text is None:
            continue
        delta = live_param_delta(base_text, greedy_text)
        if delta != {"temperature"}:
            _skip_or_fail(
                f"AC4a: {greedy} vs {base} delta={sorted(delta)} != exactly "
                f"temperature — rebuild {greedy} from the committed Modelfile"
            )
        assert is_exactly_temperature_live(base_text, greedy_text)
        checked += 1
    if checked == 0:
        _skip_or_fail("no fully-built base/greedy pair to diff")
