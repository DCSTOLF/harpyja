"""AC1 — dataset loader parses the fixture format; rejects malformed cases loudly."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harpyja.eval.dataset import (
    DATASET_SCHEMA_VERSION,
    DatasetError,
    EvalCase,
    load_dataset,
)


def _write_jsonl(path: Path, rows: list[dict]) -> Path:
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return path


_VALID_ROW = {
    "case_id": "c1",
    "query": "where is the retry backoff computed",
    "repo": "fixtures/legacy",
    "expected_spans": [{"path": "net/retry.py", "start_line": 10, "end_line": 20}],
    "classification": "point",
}


def test_load_dataset_parses_valid_fixture(tmp_path):
    f = _write_jsonl(
        tmp_path / "seed.jsonl",
        [
            _VALID_ROW,
            {
                "case_id": "c2",
                "query": "how does auth flow work end to end",
                "repo": "fixtures/legacy",
                "expected_spans": [
                    {"path": "auth/login.py", "start_line": 5, "end_line": 9},
                    {"path": "auth/session.py", "start_line": 40, "end_line": 60},
                ],
                "classification": "broad",
            },
        ],
    )
    cases = load_dataset(f)
    assert len(cases) == 2
    assert all(isinstance(c, EvalCase) for c in cases)
    c1 = cases[0]
    assert c1.case_id == "c1"
    assert c1.query.startswith("where is")
    assert c1.classification == "point"
    assert c1.expected_spans[0].path == "net/retry.py"
    assert c1.expected_spans[0].start_line == 10
    assert c1.expected_spans[0].end_line == 20
    assert len(cases[1].expected_spans) == 2


def test_load_dataset_rejects_missing_expected_span(tmp_path):
    bad = {k: v for k, v in _VALID_ROW.items() if k != "expected_spans"}
    f = _write_jsonl(tmp_path / "bad.jsonl", [bad])
    with pytest.raises(DatasetError):
        load_dataset(f)


def test_load_dataset_rejects_empty_expected_spans(tmp_path):
    bad = {**_VALID_ROW, "expected_spans": []}
    f = _write_jsonl(tmp_path / "bad.jsonl", [bad])
    with pytest.raises(DatasetError):
        load_dataset(f)


def test_load_dataset_rejects_unknown_classification_label(tmp_path):
    bad = {**_VALID_ROW, "classification": "fuzzy"}
    f = _write_jsonl(tmp_path / "bad.jsonl", [bad])
    with pytest.raises(DatasetError):
        load_dataset(f)


def test_load_dataset_raises_typed_error_never_silent_skip(tmp_path):
    # One good row, one malformed (bad JSON). A silent skip would yield 1 case;
    # the contract is a loud raise, never a dropped row.
    f = tmp_path / "mixed.jsonl"
    f.write_text(json.dumps(_VALID_ROW) + "\n" + "{not json}\n", encoding="utf-8")
    with pytest.raises(DatasetError):
        load_dataset(f)


def test_load_dataset_rejects_non_integer_line(tmp_path):
    bad = {
        **_VALID_ROW,
        "expected_spans": [{"path": "a.py", "start_line": "x", "end_line": 20}],
    }
    f = _write_jsonl(tmp_path / "bad.jsonl", [bad])
    with pytest.raises(DatasetError):
        load_dataset(f)


def test_load_dataset_rejects_inverted_line_range(tmp_path):
    bad = {
        **_VALID_ROW,
        "expected_spans": [{"path": "a.py", "start_line": 30, "end_line": 10}],
    }
    f = _write_jsonl(tmp_path / "bad.jsonl", [bad])
    with pytest.raises(DatasetError):
        load_dataset(f)


# --- spec 0026: schema-version-gated terse guard fields (AC3/AC5) ---------------

# A terse-schema (0026) row: tagged with schema_version, carries the guard fields,
# and OMITS expected_spans (they are joined by case_id from the pinned raw fixture).
_TERSE_ROW = {
    "schema_version": DATASET_SCHEMA_VERSION,
    "case_id": "astropy__astropy-12907",
    "query": "nested compound models report wrong separability",
    "repo": "astropy/astropy",
    "classification": "point",
    "gold_withheld": True,
    "query_provenance": "model-authored-blind",
    "classification_provenance": "hand-labeled-by-intent",
}


def test_dataset_schema_version_constant_exists():
    # A NEW constant is introduced (there is none today); it is not report.SCHEMA_VERSION.
    assert DATASET_SCHEMA_VERSION == "0026/1"


def test_parse_case_terse_schema_requires_guard_fields(tmp_path):
    bad = {k: v for k, v in _TERSE_ROW.items() if k != "query_provenance"}
    f = _write_jsonl(tmp_path / "terse.jsonl", [bad])
    with pytest.raises(DatasetError):
        load_dataset(f)


def test_parse_case_terse_schema_requires_gold_withheld(tmp_path):
    bad = {k: v for k, v in _TERSE_ROW.items() if k != "gold_withheld"}
    f = _write_jsonl(tmp_path / "terse.jsonl", [bad])
    with pytest.raises(DatasetError):
        load_dataset(f)


def test_parse_case_terse_schema_omits_spans_ok(tmp_path):
    # A terse row with NO expected_spans loads (spans are joined later); the guard
    # fields come back populated, expected_spans defaults empty.
    f = _write_jsonl(tmp_path / "terse.jsonl", [_TERSE_ROW])
    cases = load_dataset(f)
    assert len(cases) == 1
    c = cases[0]
    assert c.schema_version == DATASET_SCHEMA_VERSION
    assert c.expected_spans == ()
    assert c.gold_withheld is True
    assert c.query_provenance == "model-authored-blind"
    assert c.classification_provenance == "hand-labeled-by-intent"


def test_legacy_row_without_version_still_requires_spans(tmp_path):
    # The gate is version-scoped: a LEGACY row (no schema_version) with no spans
    # still raises — only terse-schema rows may omit spans.
    bad = {k: v for k, v in _VALID_ROW.items() if k != "expected_spans"}
    f = _write_jsonl(tmp_path / "legacy.jsonl", [bad])
    with pytest.raises(DatasetError):
        load_dataset(f)


def test_parse_case_legacy_no_version_tag_loads_with_defaults(tmp_path):
    # An existing seed/legacy row loads unchanged; the new guard fields read back
    # as their defaults (additive last-with-defaults, backward-compat).
    f = _write_jsonl(tmp_path / "legacy.jsonl", [_VALID_ROW])
    cases = load_dataset(f)
    c = cases[0]
    assert c.case_id == "c1"
    assert c.schema_version is None
    assert c.gold_withheld is False
    assert c.query_provenance is None
    assert c.leaked_tokens == ()
    assert c.classification_provenance is None
    assert c.label_provenance is None


# --- spec 0036: version-gated tag fields (reachability + concept-vs-patch) -------

# A 0036/1 row: everything a 0026/1 terse row carries PLUS the two mandatory tags
# (reachability + provenance, concept_patch_relation); concept_span(+provenance)
# appear ONLY on divergent rows.
_TERSE_0036_ROW = {
    "schema_version": "0036/1",
    "case_id": "astropy__astropy-12907",
    "query": "nested compound models report wrong separability",
    "repo": "astropy/astropy",
    "classification": "point",
    "gold_withheld": True,
    "query_provenance": "model-authored-blind",
    "classification_provenance": "hand-labeled-by-intent",
    "reachability": "conceptual",
    "reachability_provenance": "mechanical",
    "concept_patch_relation": "same",
}

_TERSE_0036_DIVERGENT_ROW = {
    **_TERSE_0036_ROW,
    "case_id": "astropy__astropy-12907-div",
    "concept_patch_relation": "divergent",
    "concept_span": {
        "path": "astropy/modeling/separable.py",
        "start_line": 66,
        "end_line": 102,
    },
    "concept_span_provenance": "hand-labeled-concept-span",
}


def test_dataset_known_terse_schema_versions_set(tmp_path):
    # Detection is known-versions-SET membership, not exact match: a 0026/1 legacy
    # row and a 0036/1 row BOTH load down the terse branch (spans omitted OK).
    from harpyja.eval.dataset import (
        DATASET_SCHEMA_VERSION_0036,
        _KNOWN_TERSE_SCHEMA_VERSIONS,
    )

    assert DATASET_SCHEMA_VERSION_0036 == "0036/1"
    assert _KNOWN_TERSE_SCHEMA_VERSIONS == frozenset({"0026/1", "0036/1"})
    f = _write_jsonl(tmp_path / "both.jsonl", [_TERSE_ROW, _TERSE_0036_ROW])
    cases = load_dataset(f)
    assert [c.schema_version for c in cases] == ["0026/1", "0036/1"]
    assert all(c.expected_spans == () for c in cases)


def test_parse_case_0036_requires_reachability_and_provenance(tmp_path):
    for missing in ("reachability", "reachability_provenance"):
        bad = {k: v for k, v in _TERSE_0036_ROW.items() if k != missing}
        f = _write_jsonl(tmp_path / f"bad-{missing}.jsonl", [bad])
        with pytest.raises(DatasetError):
            load_dataset(f)


def test_parse_case_0036_requires_concept_patch_relation(tmp_path):
    bad = {k: v for k, v in _TERSE_0036_ROW.items() if k != "concept_patch_relation"}
    f = _write_jsonl(tmp_path / "bad-relation.jsonl", [bad])
    with pytest.raises(DatasetError):
        load_dataset(f)


def test_parse_case_0036_divergent_requires_concept_span_and_provenance(tmp_path):
    for missing in ("concept_span", "concept_span_provenance"):
        bad = {k: v for k, v in _TERSE_0036_DIVERGENT_ROW.items() if k != missing}
        f = _write_jsonl(tmp_path / f"bad-{missing}.jsonl", [bad])
        with pytest.raises(DatasetError):
            load_dataset(f)


def test_parse_case_0036_same_forbids_concept_span(tmp_path):
    # relation=same with a concept_span present is a contradiction — rejected, the
    # two validation contracts (mandatory tag vs conditional span) stay loud.
    bad = {
        **_TERSE_0036_ROW,
        "concept_span": {"path": "a.py", "start_line": 1, "end_line": 2},
    }
    f = _write_jsonl(tmp_path / "bad-same-span.jsonl", [bad])
    with pytest.raises(DatasetError):
        load_dataset(f)


def test_parse_case_0036_rejects_bad_tag_enums(tmp_path):
    for field, bad_value in (
        ("reachability", "easy"),
        ("reachability_provenance", "vibes"),
        ("concept_patch_relation", "sorta"),
    ):
        bad = {**_TERSE_0036_ROW, field: bad_value}
        f = _write_jsonl(tmp_path / f"bad-enum-{field}.jsonl", [bad])
        with pytest.raises(DatasetError):
            load_dataset(f)


def test_parse_case_0036_valid_rows_load_with_tags(tmp_path):
    f = _write_jsonl(
        tmp_path / "good.jsonl", [_TERSE_0036_ROW, _TERSE_0036_DIVERGENT_ROW]
    )
    same, divergent = load_dataset(f)
    assert same.reachability == "conceptual"
    assert same.reachability_provenance == "mechanical"
    assert same.concept_patch_relation == "same"
    assert same.concept_span is None
    assert same.concept_span_provenance is None
    assert divergent.concept_patch_relation == "divergent"
    assert divergent.concept_span.path == "astropy/modeling/separable.py"
    assert divergent.concept_span.start_line == 66
    assert divergent.concept_span.end_line == 102
    assert divergent.concept_span_provenance == "hand-labeled-concept-span"


def test_legacy_0026_row_defaults_new_fields(tmp_path):
    # A 0026/1 row (no 0036 tags) keeps loading; the new fields read back as their
    # defaults — the gate binds the tag-required rule to 0036/1+ rows only.
    f = _write_jsonl(tmp_path / "legacy-terse.jsonl", [_TERSE_ROW])
    c = load_dataset(f)[0]
    assert c.schema_version == "0026/1"
    assert c.reachability is None
    assert c.reachability_provenance is None
    assert c.concept_patch_relation is None
    assert c.concept_span is None
    assert c.concept_span_provenance is None
