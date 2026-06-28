"""RED (spec 0008, T03): query classifier — point vs broad (AC2).

The classifier biases to the cheap path: anything ambiguous is `point`, and the
gate/ladder catch under-classification by escalating. Heuristic only this wave;
the callable is the pluggable seam for a future model classifier.
"""

import pytest

from harpyja.orchestrator.classify import classify_query

POINT_QUERIES = [
    "where is parse_config defined",
    "find the User class",
    "locate handle_request",
    "def login",
    "ModelGateway.complete",
    "the function that loads settings",
]

BROAD_QUERIES = [
    "trace the request lifecycle",
    "audit all the auth checks",
    "how does authentication flow through the system",
    "explain the overall architecture",
    "everywhere we write to the database",
    "walk through the end-to-end indexing pipeline",
]

AMBIGUOUS_QUERIES = [
    "config",
    "login",
    "settings",
    "user",
]


@pytest.mark.parametrize("query", POINT_QUERIES)
def test_classify_point_query_returns_point(query):
    assert classify_query(query) == "point"


@pytest.mark.parametrize("query", BROAD_QUERIES)
def test_classify_broad_query_returns_broad(query):
    assert classify_query(query) == "broad"


@pytest.mark.parametrize("query", AMBIGUOUS_QUERIES)
def test_classify_ambiguous_returns_point(query):
    # Bias to the cheap path: ambiguous → point (spec §Query classifier).
    assert classify_query(query) == "point"


def test_classify_empty_query_is_point():
    assert classify_query("") == "point"
    assert classify_query("   ") == "point"
