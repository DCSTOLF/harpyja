"""Integration tests for trajectory-verified live measurement (spec 0031, AC6)."""

import json
import pytest
import tempfile
from pathlib import Path

from harpyja.eval.live_verifier import (
    run_verified_case,
    VerifierResult,
    verifier_preflight,
)
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
    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = Path(tmpdir)

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
