"""RED (task 8): language classification by extension (AC5)."""

from harpyja.index.classify import classify_language


def test_classify_python_extension():
    assert classify_language("src/a.py") == "python"


def test_classify_go_extension():
    assert classify_language("cmd/main.go") == "go"


def test_classify_unknown_extension_is_none():
    assert classify_language("data/blob.xyz") is None


def test_classify_extensionless_is_none():
    assert classify_language("bin/run") is None
