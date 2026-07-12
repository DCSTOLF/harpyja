"""Spec 0041 — exclusivity-gate contract tests (AC1).

The exclusivity record (``0041/exclusivity/1``) is the run-level proof that the
endpoint's RESIDENT SET was exclusive at every recorded check. The record's
claim never exceeds the mechanism: ``/api/ps`` exposes resident models, not
queued/in-flight requests, so the contract names the TWO residuals the check
structurally cannot see (intra-block window; same-tag contention).
"""

from __future__ import annotations

import pytest

from harpyja.eval.exclusivity_gate import (
    EXCLUSIVITY_CHECK_KIND,
    EXCLUSIVITY_SCHEMA_VERSION,
    EXCLUSIVITY_UNSEEABLE_RESIDUALS,
    ExclusiveEndpointContended,
    ExclusivityError,
    build_exclusivity_record,
    check_exclusive_endpoint,
    foreign_residents,
    validate_exclusivity_record,
)
from harpyja.gateway.gateway import AirGapError

FROZEN_MODEL_SET = ("qwen3:14b", "qwen3:8b", "qwen3.5:4b")


def _clean_check(ts: str = "2026-07-11T00:00:00+00:00") -> dict:
    return {
        "label": "start",
        "timestamp": ts,
        "clean": True,
        "residents": ["qwen3:14b"],
        "foreign": [],
    }


def test_exclusivity_schema_version_is_0041_exclusivity_1():
    assert EXCLUSIVITY_SCHEMA_VERSION == "0041/exclusivity/1"


def test_exclusivity_check_kind_is_start_plus_per_block():
    """The kind names the actual strength — never 'continuous run-duration'."""
    assert EXCLUSIVITY_CHECK_KIND == "start-plus-per-block"
    record = build_exclusivity_record(
        checks=[_clean_check()], model_set=FROZEN_MODEL_SET
    )
    assert record["exclusivity_check_kind"] == "start-plus-per-block"


def test_exclusivity_record_names_two_unseeable_residuals():
    """The claim must not exceed what /api/ps can show: the record itself
    carries the two named residuals the check cannot see."""
    assert EXCLUSIVITY_UNSEEABLE_RESIDUALS == (
        "intra-block-window",
        "same-tag-contention",
    )
    record = build_exclusivity_record(
        checks=[_clean_check()], model_set=FROZEN_MODEL_SET
    )
    assert record["unseeable_residuals"] == [
        "intra-block-window",
        "same-tag-contention",
    ]


def test_foreign_residents_flags_only_tags_outside_frozen_model_set():
    residents = ["qwen3:14b", "llama3:8b", "qwen3.5:4b", "mistral:7b"]
    assert foreign_residents(residents, FROZEN_MODEL_SET) == [
        "llama3:8b",
        "mistral:7b",
    ]
    # The run's own configured models are NEVER foreign — the driver's
    # block-by-block loads must not self-trigger the gate.
    assert foreign_residents(list(FROZEN_MODEL_SET), FROZEN_MODEL_SET) == []
    assert foreign_residents([], FROZEN_MODEL_SET) == []


def test_check_exclusive_endpoint_routes_through_assert_local_first():
    """The 0019 rule: /api/ps is the same loopback-gated egress class as
    /api/tags — a non-loopback base raises BEFORE the reader is touched."""
    calls: list[str] = []

    def ps_reader(api_base: str) -> list[str]:
        calls.append(api_base)
        return []

    with pytest.raises(AirGapError):
        check_exclusive_endpoint(
            "http://10.0.0.5:11434", FROZEN_MODEL_SET, ps_reader=ps_reader
        )
    assert calls == []


def test_check_exclusive_endpoint_refuses_on_foreign_resident_typed_stop():
    def ps_reader(api_base: str) -> list[str]:
        return ["qwen3:14b", "llama3:8b"]

    with pytest.raises(ExclusiveEndpointContended) as exc:
        check_exclusive_endpoint(
            "http://127.0.0.1:11434",
            FROZEN_MODEL_SET,
            label="pre-block:qwen3:14b",
            ps_reader=ps_reader,
        )
    assert exc.value.stop_id == "exclusive-endpoint-contended"
    assert exc.value.foreign == ["llama3:8b"]
    # The stop names the residuals the check could not see — no overclaim.
    assert "same-tag-contention" in str(exc.value)


def test_check_exclusive_endpoint_passes_on_configured_only_and_records_check():
    def ps_reader(api_base: str) -> list[str]:
        return ["qwen3:14b", "qwen3.5:4b"]

    check = check_exclusive_endpoint(
        "http://127.0.0.1:11434",
        FROZEN_MODEL_SET,
        label="start",
        ps_reader=ps_reader,
        now=lambda: "2026-07-11T01:02:03+00:00",
    )
    assert check == {
        "label": "start",
        "timestamp": "2026-07-11T01:02:03+00:00",
        "clean": True,
        "residents": ["qwen3:14b", "qwen3.5:4b"],
        "foreign": [],
    }
    # A recorded check slots straight into a valid record.
    validate_exclusivity_record(
        build_exclusivity_record(checks=[check], model_set=FROZEN_MODEL_SET)
    )


def test_validate_exclusivity_record_rejects_missing_checks_or_model_set_or_kind():
    good = build_exclusivity_record(
        checks=[_clean_check()], model_set=FROZEN_MODEL_SET
    )
    validate_exclusivity_record(good)  # conforming record passes

    with pytest.raises(ExclusivityError):
        validate_exclusivity_record({**good, "schema_version": "0040/nope/1"})
    with pytest.raises(ExclusivityError):
        validate_exclusivity_record({k: v for k, v in good.items() if k != "checks"})
    with pytest.raises(ExclusivityError):
        validate_exclusivity_record({**good, "checks": []})
    with pytest.raises(ExclusivityError):
        validate_exclusivity_record(
            {k: v for k, v in good.items() if k != "model_set"}
        )
    with pytest.raises(ExclusivityError):
        validate_exclusivity_record(
            {k: v for k, v in good.items() if k != "exclusivity_check_kind"}
        )
    with pytest.raises(ExclusivityError):
        validate_exclusivity_record(
            {**good, "unseeable_residuals": ["intra-block-window"]}
        )
    # A check entry missing its timestamp or clean flag is not a valid check.
    with pytest.raises(ExclusivityError):
        validate_exclusivity_record(
            {**good, "checks": [{"label": "start", "clean": True}]}
        )
    with pytest.raises(ExclusivityError):
        validate_exclusivity_record(
            {
                **good,
                "checks": [
                    {"label": "start", "timestamp": "2026-07-11T00:00:00+00:00"}
                ],
            }
        )
