"""Spec 0049 — greedy serving: fingerprint parser + build driver (unit).

The deterministic one-parser Modelfile-fingerprint grammar (What §1) and the
idempotent / STOP-AND-WARN build driver (AC1). Pure and I/O-free except the
committed ``serving/Modelfile.*`` reads; every subprocess/registry seam is
injected, so these run offline with no Ollama.
"""

from __future__ import annotations

import pathlib

import pytest

from harpyja.eval.greedy_serving import (
    GreedyBuildOutcome,
    ModelfileFingerprint,
    ModelfileGrammarError,
    build_greedy_variant,
    fingerprint_delta,
    fingerprint_digest,
    is_exactly_temperature_delta,
    is_exactly_temperature_live,
    live_param_delta,
    local_ollama_env,
    parse_live_parameters,
    parse_modelfile_fingerprint,
    read_live_modelfile,
)

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_SERVING = _REPO_ROOT / "serving"
_GREEDY_MODELFILES = {
    "qwen3-14b-greedy": _SERVING / "Modelfile.qwen3-14b",
    "qwen3-8b-greedy": _SERVING / "Modelfile.qwen3-8b",
    "qwen3.5-4b-greedy": _SERVING / "Modelfile.qwen3.5-4b",
}


# ---- Step 1: fingerprint grammar --------------------------------------------


def test_parse_modelfile_fingerprint_extracts_from_params_template_system():
    text = (
        "FROM qwen3:14b\n"
        "PARAMETER temperature 0\n"
        "PARAMETER top_p 1\n"
        'SYSTEM "you are a locator"\n'
        'TEMPLATE "{{ .Prompt }}"\n'
    )
    fp = parse_modelfile_fingerprint(text)
    assert isinstance(fp, ModelfileFingerprint)
    assert fp.from_base == "qwen3:14b"
    assert dict(fp.parameters) == {"temperature": "0", "top_p": "1"}
    assert fp.system == "you are a locator"
    assert fp.template == "{{ .Prompt }}"


def test_parse_modelfile_fingerprint_sorts_parameter_map():
    text = "FROM qwen3:8b\nPARAMETER top_p 1\nPARAMETER seed 0\nPARAMETER temperature 0\n"
    fp = parse_modelfile_fingerprint(text)
    # Canonical: sorted by key regardless of source order.
    assert fp.parameters == (("seed", "0"), ("temperature", "0"), ("top_p", "1"))


def test_parse_modelfile_fingerprint_rejects_duplicate_parameter_keys():
    text = "FROM qwen3:8b\nPARAMETER temperature 0\nPARAMETER temperature 1\n"
    with pytest.raises(ModelfileGrammarError):
        parse_modelfile_fingerprint(text)


def test_parse_modelfile_fingerprint_rejects_out_of_set_directive():
    text = "FROM qwen3:8b\nADAPTER ./some-lora\nPARAMETER temperature 0\n"
    with pytest.raises(ModelfileGrammarError):
        parse_modelfile_fingerprint(text)


def test_parse_modelfile_fingerprint_normalizes_line_endings_and_comments():
    clean = "FROM qwen3:14b\nPARAMETER temperature 0\nPARAMETER top_p 1\n"
    messy = (
        "# greedy variant\r\n"
        "FROM qwen3:14b\r\n"
        "\r\n"
        "PARAMETER temperature 0\r\n"
        "  PARAMETER  top_p  1  \r\n"
        "# trailing comment\r\n"
    )
    a = parse_modelfile_fingerprint(clean)
    b = parse_modelfile_fingerprint(messy)
    assert a == b
    assert fingerprint_digest(a) == fingerprint_digest(b)


def test_fingerprint_digest_is_64_hex():
    fp = parse_modelfile_fingerprint("FROM qwen3:8b\nPARAMETER temperature 0\n")
    digest = fingerprint_digest(fp)
    assert len(digest) == 64
    assert all(c in "0123456789abcdef" for c in digest)


def test_greedy_modelfiles_set_temperature_zero():
    for path in _GREEDY_MODELFILES.values():
        fp = parse_modelfile_fingerprint(path.read_text())
        assert dict(fp.parameters)["temperature"] == "0"


# ---- Step 3: build driver + live reader -------------------------------------


class _Recorder:
    """A call log so ordering (assert_local BEFORE any subprocess) is pinnable."""

    def __init__(self, *, live_text: str | None = None):
        self.calls: list[str] = []
        self.create_env: dict[str, str] | None = None
        self.show_env: dict[str, str] | None = None
        self._live_text = live_text

    def assert_local(self, host):
        self.calls.append(f"assert_local:{host}")

    def resolve_host(self):
        return "http://127.0.0.1:11434"

    def show(self, tag, *, env):
        self.calls.append(f"show:{tag}")
        self.show_env = env
        if self._live_text is None:
            raise FileNotFoundError(tag)  # tag absent
        return self._live_text

    def create(self, tag, modelfile_path, *, env):
        self.calls.append(f"create:{tag}")
        self.create_env = env


def _committed_fp():
    return parse_modelfile_fingerprint(
        _GREEDY_MODELFILES["qwen3-14b-greedy"].read_text()
    )


def test_build_greedy_variant_noop_on_fingerprint_match():
    committed = _committed_fp()
    rec = _Recorder(live_text=_GREEDY_MODELFILES["qwen3-14b-greedy"].read_text())
    outcome = build_greedy_variant(
        "qwen3-14b-greedy",
        _GREEDY_MODELFILES["qwen3-14b-greedy"],
        committed,
        host_resolver=rec.resolve_host,
        assert_local_fn=rec.assert_local,
        show_fn=rec.show,
        create_fn=rec.create,
    )
    assert outcome is GreedyBuildOutcome.NOOP_MATCH
    assert "create:qwen3-14b-greedy" not in rec.calls  # never overwrites


def test_build_greedy_variant_stops_and_warns_on_fingerprint_mismatch():
    committed = _committed_fp()
    divergent = "FROM qwen3:14b\nPARAMETER temperature 1\n"  # not greedy
    rec = _Recorder(live_text=divergent)
    outcome = build_greedy_variant(
        "qwen3-14b-greedy",
        _GREEDY_MODELFILES["qwen3-14b-greedy"],
        committed,
        host_resolver=rec.resolve_host,
        assert_local_fn=rec.assert_local,
        show_fn=rec.show,
        create_fn=rec.create,
    )
    assert outcome is GreedyBuildOutcome.STOP_AND_WARN_MISMATCH
    assert "create:qwen3-14b-greedy" not in rec.calls  # never overwrites on drift


def test_build_greedy_variant_creates_from_committed_file_when_absent():
    committed = _committed_fp()
    rec = _Recorder(live_text=None)  # tag absent → show raises FileNotFoundError
    outcome = build_greedy_variant(
        "qwen3-14b-greedy",
        _GREEDY_MODELFILES["qwen3-14b-greedy"],
        committed,
        host_resolver=rec.resolve_host,
        assert_local_fn=rec.assert_local,
        show_fn=rec.show,
        create_fn=rec.create,
    )
    assert outcome is GreedyBuildOutcome.CREATED
    assert "create:qwen3-14b-greedy" in rec.calls


def test_build_greedy_variant_asserts_local_on_resolved_host_first():
    committed = _committed_fp()
    rec = _Recorder(live_text=None)
    build_greedy_variant(
        "qwen3-14b-greedy",
        _GREEDY_MODELFILES["qwen3-14b-greedy"],
        committed,
        host_resolver=rec.resolve_host,
        assert_local_fn=rec.assert_local,
        show_fn=rec.show,
        create_fn=rec.create,
    )
    # assert_local must precede every subprocess seam (show/create).
    first_subprocess = next(
        i for i, c in enumerate(rec.calls) if c.startswith(("show:", "create:"))
    )
    assert rec.calls[0] == "assert_local:http://127.0.0.1:11434"
    assert first_subprocess > 0


def test_build_greedy_variant_passes_sanitized_env_with_ollama_host():
    committed = _committed_fp()
    rec = _Recorder(live_text=None)
    build_greedy_variant(
        "qwen3-14b-greedy",
        _GREEDY_MODELFILES["qwen3-14b-greedy"],
        committed,
        host_resolver=rec.resolve_host,
        assert_local_fn=rec.assert_local,
        show_fn=rec.show,
        create_fn=rec.create,
    )
    assert rec.create_env is not None
    assert rec.create_env["OLLAMA_HOST"] == "http://127.0.0.1:11434"


def test_read_live_modelfile_binds_ollama_host_in_sanitized_env():
    seen = {}

    def run_fn(args, *, env):
        seen["args"] = args
        seen["env"] = env
        return "FROM qwen3:8b\nPARAMETER temperature 0\n"

    text = read_live_modelfile(
        "qwen3-8b-greedy", host="http://127.0.0.1:11434", run_fn=run_fn
    )
    assert "ollama" in seen["args"][0]
    assert "show" in seen["args"] and "--modelfile" in seen["args"]
    assert "qwen3-8b-greedy" in seen["args"]
    assert seen["env"]["OLLAMA_HOST"] == "http://127.0.0.1:11434"
    # parseable by the SAME one parser
    assert parse_modelfile_fingerprint(text).from_base == "qwen3:8b"


# ---- Step 5: fingerprint delta (AC4) ----------------------------------------


def test_greedy_generation_pins_diff_base_is_exactly_temperature():
    # The 0034/0038 pinned generation params, expressed as a base fingerprint
    # (a non-greedy temperature); the committed greedy Modelfile changes ONLY it.
    base = ModelfileFingerprint(
        from_base="qwen3:14b", parameters=(("temperature", "0.7"),)
    )
    greedy = parse_modelfile_fingerprint(
        _GREEDY_MODELFILES["qwen3-14b-greedy"].read_text()
    )
    delta = fingerprint_delta(base, greedy)
    assert is_exactly_temperature_delta(delta)


def test_fingerprint_delta_added_temperature_is_exactly_temperature():
    base = ModelfileFingerprint(from_base="qwen3:8b", parameters=())  # no temperature
    greedy = ModelfileFingerprint(
        from_base="qwen3:8b", parameters=(("temperature", "0"),)
    )
    delta = fingerprint_delta(base, greedy)
    assert is_exactly_temperature_delta(delta)


def test_fingerprint_delta_excludes_from_base():
    # Live `ollama show` normalizes FROM to a blob path; a FROM diff is NOT drift.
    base = ModelfileFingerprint(
        from_base="qwen3:8b", parameters=(("temperature", "0.7"),)
    )
    greedy = ModelfileFingerprint(
        from_base="sha256:deadbeef", parameters=(("temperature", "0"),)
    )
    assert is_exactly_temperature_delta(fingerprint_delta(base, greedy))


def test_fingerprint_delta_other_key_change_fails():
    base = ModelfileFingerprint(
        from_base="qwen3:8b",
        parameters=(("temperature", "0.7"), ("top_p", "0.95")),
    )
    greedy = ModelfileFingerprint(
        from_base="qwen3:8b",
        parameters=(("temperature", "0"), ("top_p", "1")),
    )
    assert not is_exactly_temperature_delta(fingerprint_delta(base, greedy))


def test_fingerprint_delta_template_change_is_not_exactly_temperature():
    base = ModelfileFingerprint(
        from_base="qwen3:8b", parameters=(("temperature", "0.7"),), template="a"
    )
    greedy = ModelfileFingerprint(
        from_base="qwen3:8b", parameters=(("temperature", "0"),), template="b"
    )
    assert not is_exactly_temperature_delta(fingerprint_delta(base, greedy))


def test_fingerprint_delta_identical_is_not_exactly_temperature():
    # No change at all is NOT "exactly temperature" (temperature must be touched).
    fp = ModelfileFingerprint(from_base="qwen3:8b", parameters=(("temperature", "0"),))
    assert not is_exactly_temperature_delta(fingerprint_delta(fp, fp))


# ---- Live-Modelfile tolerant param extraction (AC4a) ------------------------
#
# A real ``ollama show --modelfile`` output is the FULLY-EXPANDED definition (blob
# FROM, a big TEMPLATE, a LICENSE block, MULTI-VALUED ``PARAMETER stop``) — the
# strict committed-file grammar rejects it by design. The live base-diff needs a
# tolerant PARAMETER extractor. These fixtures encode the REAL qwen3:14b params
# observed on the dev stack.

_LIVE_BASE_14B = """# Modelfile generated by "ollama show"
FROM /root/.ollama/models/blobs/sha256-abc123
TEMPLATE \"\"\"{{ .Prompt }}\"\"\"
PARAMETER repeat_penalty 1
PARAMETER stop <|im_start|>
PARAMETER stop <|im_end|>
PARAMETER temperature 0.6
PARAMETER top_k 20
PARAMETER top_p 0.95
LICENSE \"\"\"Apache License 2.0 ... boilerplate ...\"\"\"
"""

# A tag rebuilt from the temperature-only committed Modelfile: inherits every base
# param, overrides ONLY temperature.
_LIVE_GREEDY_TEMP_ONLY = _LIVE_BASE_14B.replace(
    "PARAMETER temperature 0.6", "PARAMETER temperature 0"
)

# The 0048 HAND-CREATED tag (as observed live): temperature 0 AND top_p 1 AND an
# added seed 0 — the divergence AC1a exists to catch.
_LIVE_GREEDY_0048 = """# Modelfile generated by "ollama show"
FROM /root/.ollama/models/blobs/sha256-abc123
TEMPLATE \"\"\"{{ .Prompt }}\"\"\"
PARAMETER top_k 20
PARAMETER top_p 1
PARAMETER repeat_penalty 1
PARAMETER seed 0
PARAMETER stop <|im_start|>
PARAMETER stop <|im_end|>
PARAMETER temperature 0
LICENSE \"\"\"Apache License 2.0 ... boilerplate ...\"\"\"
"""


def test_parse_live_parameters_groups_multivalued_stop():
    params = parse_live_parameters(_LIVE_BASE_14B)
    assert params["stop"] == ("<|im_end|>", "<|im_start|>")  # sorted, multi-valued
    assert params["temperature"] == ("0.6",)
    assert params["top_p"] == ("0.95",)
    assert "license" not in params and "template" not in params  # only PARAMETERs


def test_is_exactly_temperature_live_true_for_temperature_only_override():
    assert is_exactly_temperature_live(_LIVE_BASE_14B, _LIVE_GREEDY_TEMP_ONLY)
    assert live_param_delta(_LIVE_BASE_14B, _LIVE_GREEDY_TEMP_ONLY) == {"temperature"}


def test_is_exactly_temperature_live_false_for_hand_created_0048_tag():
    # The 0048 tag also flips top_p and adds seed → NOT exactly temperature.
    assert not is_exactly_temperature_live(_LIVE_BASE_14B, _LIVE_GREEDY_0048)
    assert live_param_delta(_LIVE_BASE_14B, _LIVE_GREEDY_0048) == {
        "temperature",
        "top_p",
        "seed",
    }


def test_local_ollama_env_is_sanitized_allowlist():
    env = local_ollama_env("http://127.0.0.1:11434")
    assert env["OLLAMA_HOST"] == "http://127.0.0.1:11434"
    # Sanitized allowlist — binds the daemon, carries only operational necessities.
    assert set(env) <= {"OLLAMA_HOST", "PATH", "HOME"}
    assert "OLLAMA_HOST" in env
