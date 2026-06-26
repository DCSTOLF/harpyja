"""RED (task 6): the `prior` ranking heuristic.

AC7 — pure function; vendored/test/generated rank below an equivalent source
file; source-dir bonus applies; deeper paths are penalized. Placeholder weights
must preserve these orderings.
"""

from harpyja.index.prior import prior


def test_prior_is_pure_same_input_same_output():
    assert prior("src/billing/gateway.py") == prior("src/billing/gateway.py")


def test_prior_vendored_ranks_below_equivalent_source():
    assert prior("vendor/x.py") < prior("src/x.py")


def test_prior_test_file_ranks_below_source():
    assert prior("tests/foo.py") < prior("src/foo.py")
    assert prior("src/foo_test.py") < prior("src/foo.py")


def test_prior_generated_ranks_below_source():
    assert prior("generated/x.go") < prior("src/x.go")
    assert prior("src/x.pb.go") < prior("src/x.go")


def test_prior_source_dir_bonus_applies():
    # A recognised source dir beats a neutral directory at the same depth.
    assert prior("src/x.py") > prior("misc/x.py")


def test_prior_deeper_path_penalized_all_else_equal():
    # Neutral dirs (no source/test/vendor signal) — only depth differs.
    assert prior("a/b/c/x.py") < prior("a/x.py")
