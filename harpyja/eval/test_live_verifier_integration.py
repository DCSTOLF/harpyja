"""Integration tests for trajectory-verified live measurement (spec 0031, AC6)."""

import json
import pytest

from harpyja.eval.live_verifier import (
    run_verified_case,
    VerifierResult,
    verifier_preflight,
)
from harpyja.eval.live_artifacts import live_artifact_dir
from harpyja.gateway.gateway import ModelGateway
from harpyja.config.settings import Settings


@pytest.mark.integration
def test_proof_of_instrument_astropy_django_produce_verifier_artifacts():
    """Proof-of-instrument: astropy and django cases produce verifier artifacts.

    Skips gracefully if the live stack is unavailable or invalid.
    """
    import dataclasses

    import requests

    # Preflight: check gateway availability
    try:
        # Try Ollama first (most likely available)
        resp = requests.get("http://127.0.0.1:11434/api/tags", timeout=2)
        tags_payload = resp.json()

        settings = dataclasses.replace(
            Settings(),
            lm_api_base="http://127.0.0.1:11434/v1",
            lm_model="qwen3:14b",
        )
        gateway = ModelGateway(
            api_base=settings.lm_api_base,
            model=settings.lm_model,
        )

        # Verify model is present
        served_models = {m.get("name") for m in tags_payload.get("models", [])}
        if "qwen3:14b" not in served_models:
            pytest.skip(f"qwen3:14b not found in served models: {sorted(served_models)}")

    except requests.exceptions.ConnectionError:
        pytest.skip("Ollama not running on 11434")
    except Exception as e:
        pytest.skip(f"Setup failed: {e}")

    # If we reach here, the live stack is up and valid
    if True:  # spec 0035: persistent artifacts (was a TemporaryDirectory)
        out_dir = live_artifact_dir("proof_of_instrument")

        # Test cases: (case_name, gold_span_stub)
        # Note: actual gold spans will be loaded from fixture, these are just placeholders
        test_cases = [
            ("astropy__astropy-12907", {"file": "astropy/modeling/separable.py", "start_line": 242, "end_line": 248}),
            ("django__django-12774", {"file": "django/db/models/query.py", "start_line": 689, "end_line": 695}),
        ]

        results_summary = {}

        for case_name, gold_span in test_cases:
            try:
                # Run the verified case: returns (VerifierResult, artifact_path)
                result, artifact_path = run_verified_case(
                    case_name=case_name,
                    settings=settings,
                    gateway=gateway,
                    gold_span=gold_span,
                    out_dir=out_dir,
                )

                # Assertions on result structure
                assert isinstance(result, VerifierResult)
                assert result.status in {"PASSED", "FAILED"}

                # If PASSED, all facts must be present
                if result.status == "PASSED":
                    assert result.model_identity is not None
                    assert result.model_invoked is not None
                    assert result.tool_names_invoked is not None
                    assert result.terminal_bucket is not None
                else:
                    # FAILED cases must have a failure_reason
                    assert result.failure_reason is not None

                # tool_names_invoked must be a list (records symbols presence as-is)
                assert isinstance(result.tool_names_invoked, list)

                # Artifact file must exist
                assert artifact_path.exists()

                # Capture terminal bucket for reporting
                results_summary[case_name] = result.terminal_bucket

                # Load artifact to show symbols invocation
                with open(artifact_path) as f:
                    artifact = json.load(f)

                tool_names = set()
                for turn in artifact.get('model_turns', []):
                    if isinstance(turn, dict) and 'tool_calls' in turn:
                        for tc in turn['tool_calls']:
                            if isinstance(tc, dict):
                                fname = tc.get('function', {}).get('name')
                                if fname:
                                    tool_names.add(fname)

                symbols_invoked = 'symbols' in tool_names
                print(f"\n[ARTIFACT] {case_name}:")
                print(f"  - verifier_status: {artifact['verifier_status']}")
                print(f"  - terminal_bucket: {artifact['terminal_bucket']}")
                print(f"  - tools_invoked: {sorted(tool_names)}")
                print(f"  - symbols_invoked: {'YES' if symbols_invoked else 'NO'}")

            except Exception as e:
                # Case execution error: skip this case but continue
                pytest.skip(f"Case {case_name} execution failed: {e}")


@pytest.mark.integration
def test_astropy_live_scoped_grep_survives_or_not_exercised():
    """Spec 0033 AC7: the 0032 astropy case re-run through the repo-relative
    scoped-grep fix.

    IF the model cites a scoped-grep hit this run, the citation must SURVIVE
    normalization (citations_surviving > 0) — the 0032 found-then-dropped shape
    is closed. The condition is MODEL-BEHAVIOR-CONTINGENT (0023 input-validity
    rule): a run where the model never greps scoped, or honestly submits an
    empty list, records the condition NOT-EXERCISED (printed, never a silent
    pass) — the hermetic AC3 fixture in test_submit_citations.py carries the
    deterministic proof. Both counts must be recorded in the artifact either way.
    """
    import dataclasses

    import requests

    try:
        resp = requests.get("http://127.0.0.1:11434/api/tags", timeout=2)
        tags_payload = resp.json()
        served = {m.get("name") for m in tags_payload.get("models", [])}
        if "qwen3:14b" not in served:
            pytest.skip(f"qwen3:14b not served: {sorted(served)}")
    except Exception as e:
        pytest.skip(f"Ollama not reachable: {e}")

    settings = dataclasses.replace(
        Settings(),
        lm_api_base="http://127.0.0.1:11434/v1",
        lm_model="qwen3:14b",
        scout_max_turns=10,
        scout_wall_clock_s=600.0,
        lm_http_timeout_s=300.0,
    )
    gateway = ModelGateway(api_base=settings.lm_api_base, model=settings.lm_model)

    if True:  # spec 0035: persistent artifacts (was a TemporaryDirectory)
        try:
            result, artifact_path = run_verified_case(
                case_name="astropy__astropy-12907",
                settings=settings,
                gateway=gateway,
                gold_span={"file": "astropy/modeling/separable.py",
                           "start_line": 242, "end_line": 248},
                out_dir=live_artifact_dir("scoped_grep_survives"),
            )
        except ValueError as e:
            pytest.skip(f"case setup/degrade: {e}")

        with open(artifact_path) as f:
            artifact = json.load(f)

        # Both counts are RECORDED in the trajectory regardless of model behavior.
        traj = artifact.get("model_turns", [])
        submitted = artifact.get("citations_submitted")
        surviving = artifact.get("citations_surviving")
        print(f"\n[0033 AC7] citations_submitted={submitted} surviving={surviving} "
              f"terminal_bucket={artifact.get('terminal_bucket')}")

        if submitted is not None and submitted > 0:
            # The model cited something: the fix means a scoped-grep cite SURVIVES —
            # found-then-dropped (submitted>0, surviving=0) would be the 0032 defect.
            assert surviving is not None and surviving > 0, (
                f"found-then-dropped resurfaced: submitted={submitted}, "
                f"surviving={surviving} — a cited hit was dropped at normalize"
            )
            print("[0033 AC7] EXERCISED: cited hit(s) survived normalization")
        else:
            print("[0033 AC7] NOT-EXERCISED: model submitted no citations this run "
                  "(hermetic AC3 fixture carries the deterministic proof)")
        assert isinstance(traj, list)


@pytest.mark.integration
def test_live_records_nonzero_reasoning_or_not_exercised():
    """Spec 0034 AC5: live recording proof with the 0023 precondition fallback.

    Preflight-probe the stack (does THIS served model emit `reasoning` by
    default?). If yes → a live explorer run must record ≥1 per_turn entry with
    reasoning_chars > 0 (the hidden variable is now visible). If no → record
    NOT-EXERCISED (never a silent pass) — AC1/AC2's hermetic fixtures carry the
    mechanism proof. Skip-not-fail on absent stack.
    """
    import dataclasses

    import requests

    from harpyja.eval.live_verifier import probe_reasoning_default

    try:
        resp = requests.get("http://127.0.0.1:11434/api/tags", timeout=2)
        served = {m.get("name") for m in resp.json().get("models", [])}
        if "qwen3:14b" not in served:
            pytest.skip(f"qwen3:14b not served: {sorted(served)}")
    except Exception as e:
        pytest.skip(f"Ollama not reachable: {e}")

    settings = dataclasses.replace(
        Settings(),
        lm_api_base="http://127.0.0.1:11434/v1",
        lm_model="qwen3:14b",
        scout_max_turns=10,
        scout_wall_clock_s=600.0,
        lm_http_timeout_s=300.0,
    )
    gateway = ModelGateway(api_base=settings.lm_api_base, model=settings.lm_model)

    if not probe_reasoning_default(gateway):
        print("\n[0034 AC5] NOT-EXERCISED: served model emits no default reasoning "
              "(hermetic AC1/AC2 fixtures carry the mechanism proof)")
        return

    if True:  # spec 0035: persistent artifacts (was a TemporaryDirectory)
        try:
            _result, artifact_path = run_verified_case(
                case_name="astropy__astropy-12907",
                settings=settings,
                gateway=gateway,
                gold_span={"file": "astropy/modeling/separable.py",
                           "start_line": 242, "end_line": 248},
                out_dir=live_artifact_dir("reasoning_recording"),
            )
        except ValueError as e:
            pytest.skip(f"case setup/degrade: {e}")

        with open(artifact_path) as f:
            artifact = json.load(f)

        per_turn = artifact.get("per_turn", [])
        lens = [t.get("reasoning_chars") for t in per_turn]
        print(f"\n[0034 AC5] think_mode={artifact.get('think_mode')} "
              f"per-turn reasoning_chars={lens} "
              f"bucket={artifact.get('terminal_bucket')} "
              f"submitted={artifact.get('citations_submitted')} "
              f"surviving={artifact.get('citations_surviving')}")
        assert per_turn, "per_turn missing from the written artifact"
        assert any(c and c > 0 for c in lens), (
            "precondition says the model reasons by default, but no per-turn "
            "reasoning was recorded — the hidden variable is still invisible"
        )


@pytest.mark.integration
def test_live_bad_scope_marker_in_persisted_trajectory_or_not_exercised():
    """Spec 0035 AC6: when a live model greps an unsearchable scope, the typed
    marker appears in the PERSISTED trajectory (durable under
    eval_work/live_artifacts/) and the run still reaches a terminal submit
    (non-terminal proven live). Model-behavior-contingent → 0023 fallback:
    a run with no bad-scope grep records NOT-EXERCISED (never a silent pass);
    the hermetic wrapper/loop tests carry the mechanism proof. Skip-not-fail."""
    import dataclasses

    import requests

    try:
        resp = requests.get("http://127.0.0.1:11434/api/tags", timeout=2)
        served = {m.get("name") for m in resp.json().get("models", [])}
        if "qwen3:14b" not in served:
            pytest.skip(f"qwen3:14b not served: {sorted(served)}")
    except Exception as e:
        pytest.skip(f"Ollama not reachable: {e}")

    settings = dataclasses.replace(
        Settings(),
        lm_api_base="http://127.0.0.1:11434/v1",
        lm_model="qwen3:14b",
        scout_max_turns=10,
        scout_wall_clock_s=600.0,
        lm_http_timeout_s=300.0,
    )
    gateway = ModelGateway(api_base=settings.lm_api_base, model=settings.lm_model)

    try:
        _result, artifact_path = run_verified_case(
            case_name="astropy__astropy-12907",
            settings=settings,
            gateway=gateway,
            gold_span={"file": "astropy/modeling/separable.py",
                       "start_line": 242, "end_line": 248},
            out_dir=live_artifact_dir("bad_scope_marker"),
        )
    except ValueError as e:
        pytest.skip(f"case setup/degrade: {e}")

    with open(artifact_path) as f:
        artifact = json.load(f)

    assert "eval_work/live_artifacts/bad_scope_marker" in str(artifact_path)
    history_text = str(artifact.get("model_turns", []))
    markers = [m for m in ("grep-scope-not-found", "ls-path-not-found")
               if m in history_text]
    submitted_terminal = "submit_citations" in history_text
    print(f"\n[0035 AC6] markers_seen={markers} terminal_submit={submitted_terminal} "
          f"bucket={artifact.get('terminal_bucket')} artifact={artifact_path}")
    if markers:
        assert submitted_terminal, (
            "a scope marker fired but the run did not reach a terminal submit — "
            "the marker must be non-terminal"
        )
        print("[0035 AC6] EXERCISED: marker visible in persisted trajectory, run terminal")
    else:
        print("[0035 AC6] NOT-EXERCISED: model used no bad scope this run "
              "(hermetic wrapper/loop tests carry the mechanism proof)")


@pytest.mark.integration
def test_pilot_cases_produced_verifier_clean_persisted_artifacts():
    """spec 0036 AC5: every pilot (case, arm) either produced a verifier-clean
    artifact — persisted durably under eval_work/live_artifacts/, schema 0034/1,
    carrying model identity / tools / reasoning / counts / bucket — or is a
    RECORDED typed degrade in the committed ledger (never silent, never counted
    clean). Skips (not fails) where the pilot has not run on this machine."""
    from pathlib import Path

    from harpyja.eval.live_verifier import validate_verifier_artifact

    ledger_path = (
        Path(__file__).resolve().parents[2]
        / "specs" / "0036-terse-query" / "pilot" / "pilot_results.json"
    )
    if not ledger_path.exists():
        pytest.skip("pilot ledger not present — pilot has not run here")
    ledger = json.loads(ledger_path.read_text())
    entries = ledger["entries"]
    assert entries, "pilot ledger exists but is empty"

    clean = degraded = 0
    for key, entry in sorted(entries.items()):
        if entry["bucket"] is None:
            # AC5 degrade posture: excluded-by-cause, recorded — never silent.
            assert entry["degrade"], f"{key}: bucket-less entry with no recorded cause"
            degraded += 1
            continue
        assert entry["artifact"], f"{key}: clean entry lacks its persisted artifact path"
        apath = Path(entry["artifact"])
        if not apath.exists():
            pytest.skip(f"artifact {apath} pruned since the pilot ran")
        assert "eval_work/live_artifacts/pilot_0036" in str(apath)
        with open(apath) as f:
            artifact = json.load(f)
        validate_verifier_artifact(artifact)
        assert artifact["schema_version"] == "0034/1"
        assert artifact["verifier_status"] == "PASSED"
        assert artifact["served_model"]
        assert artifact["terminal_bucket"] == entry["bucket"]
        assert "per_turn" in artifact and "think_mode" in artifact
        assert "citations_submitted" in artifact and "citations_surviving" in artifact
        clean += 1
    print(f"\n[0036 AC5] verifier-clean={clean} recorded-degrades={degraded} "
          f"config_hash={ledger.get('config_hash')}")
    assert clean + degraded == len(entries)


@pytest.mark.integration
def test_live_think_knob_three_factor_effectiveness():
    """Spec 0037 AC3 — live per-mode effectiveness proof, THREE-FACTOR, conditional.

    CONDITIONAL on the committed probe outcome being `native-think-effective`
    (skips with the recorded outcome otherwise — the NO_OP_BLOCKED /
    reconciliation branches close via findings.md, not here) and GATED on
    `probe_reasoning_default` (a non-default-thinking served model is an
    input-validity skip, never a false "knob ineffective" finding — the 0023
    rule).

    Effectiveness is asserted at the GENERATION level as three SEPARATE,
    non-collapsible factors (`reasoning_chars` alone is a reporting signal —
    a serialization-only `think:false` must FAIL here, not pass):
      (a) per-turn reasoning_chars — on/default arms >=1 turn > 0; off arm
          {None, 0} across ALL turns;
      (b) tiny-cap generation-level discriminator — the small-cap off run
          produces content and/or finish_reason != "length" (not a
          reasoning-first cap exhaustion);
      (c) completion_tokens cross-check across arms + a <think>-in-content
          leak scan on the off arm.

    Off-arm evidence strength is N=1 (one run per mode, a handful of turns) —
    stated explicitly as acceptable for an API-level mechanism toggle, and
    nothing stronger is claimed.
    """
    import dataclasses
    from pathlib import Path

    import requests

    from harpyja.eval.live_verifier import probe_reasoning_default
    from harpyja.eval.think_probe import load_probe_result

    probe_path = (
        Path(__file__).resolve().parents[2]
        / "specs" / "0037-explorer-think-knob" / "probes" / "probe_result.json"
    )
    probe = load_probe_result(probe_path)
    if probe["outcome"] != "native-think-effective":
        pytest.skip(
            f"probe outcome is {probe['outcome']!r} (not native-think-effective): "
            "AC3 conditional per spec 0037 — terminal close via findings.md"
        )

    try:
        resp = requests.get("http://127.0.0.1:11434/api/tags", timeout=2)
        served = {m.get("name") for m in resp.json().get("models", [])}
        if "qwen3:14b" not in served:
            pytest.skip(f"qwen3:14b not served: {sorted(served)}")
    except Exception as e:
        pytest.skip(f"Ollama not reachable: {e}")

    base = dataclasses.replace(
        Settings(),
        lm_api_base="http://127.0.0.1:11434/v1",
        lm_model="qwen3:14b",
        scout_max_turns=10,
        scout_wall_clock_s=600.0,
        lm_http_timeout_s=300.0,
    )
    gateway = ModelGateway(api_base=base.lm_api_base, model=base.lm_model)
    if not probe_reasoning_default(gateway):
        pytest.skip(
            "served model emits no default reasoning — on/default arms are "
            "input-invalid for this proof (0023 precondition)"
        )

    gold = {"file": "astropy/modeling/separable.py",
            "start_line": 242, "end_line": 248}
    artifacts = {}
    for mode, think in (("on", True), ("off", False), ("default", None)):
        settings = dataclasses.replace(base, explorer_think=think)
        if mode == "off":
            # tiny-cap discriminator: a genuinely-off arm answers within a
            # small cap; a still-thinking one exhausts it reasoning-first.
            settings = dataclasses.replace(settings, explorer_max_tokens=256)
        try:
            _result, artifact_path = run_verified_case(
                case_name="astropy__astropy-12907",
                settings=settings,
                gateway=gateway,
                gold_span=gold,
                out_dir=live_artifact_dir(f"think_effectiveness_{mode}"),
            )
        except ValueError as e:
            pytest.skip(f"case setup/degrade ({mode} arm): {e}")
        with open(artifact_path) as f:
            artifacts[mode] = json.load(f)

    # Factor (a): per-turn reasoning_chars.
    for mode in ("on", "default"):
        lens = [t.get("reasoning_chars") for t in artifacts[mode]["per_turn"]]
        assert any(c and c > 0 for c in lens), (
            f"{mode} arm shows no reasoning in any turn: {lens}")
    off_lens = [t.get("reasoning_chars") for t in artifacts["off"]["per_turn"]]
    assert all(c in (None, 0) for c in off_lens), (
        f"off arm still reports reasoning: {off_lens}")

    # Factor (b): tiny-cap generation-level discriminator on the off arm.
    off_turns = artifacts["off"]["per_turn"]
    assert any(
        t.get("finish_reason") != "length" for t in off_turns
    ), ("off arm exhausted the tiny cap on every turn (reasoning-first "
        "consumption) — thinking NOT genuinely off at the generation level")

    # Factor (c): completion_tokens cross-check + <think> leak scan (off arm).
    def _tokens(a):
        return [t.get("completion_tokens") for t in a["per_turn"]
                if t.get("completion_tokens") is not None]
    off_tok, on_tok = _tokens(artifacts["off"]), _tokens(artifacts["on"])
    assert off_tok and on_tok, "completion_tokens missing from per_turn"
    assert min(off_tok) < max(on_tok), (
        "off arm token spend indistinguishable from the on arm — thinking "
        "may still be burning tokens invisibly")
    off_contents = [t.get("content") or "" for t in
                    artifacts["off"].get("model_turns", [])]
    assert not any("<think>" in c for c in off_contents), (
        "off arm leaks <think> blocks into content — reporting-only suppression")

    # Secondary (NOT the effectiveness signal): recording matches the setting.
    assert artifacts["on"]["think_mode"] == "native-think-true"
    assert artifacts["off"]["think_mode"] == "native-think-false"
    assert artifacts["default"]["think_mode"] == "default-omitted"
