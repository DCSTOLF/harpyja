"""RED (task 14): sha256 file hashing (AC1)."""

import hashlib

from harpyja.index.hash import hash_file


def test_hash_file_sha256_prefixed(tmp_path):
    f = tmp_path / "a.txt"
    f.write_bytes(b"hello harpyja")
    expected = "sha256:" + hashlib.sha256(b"hello harpyja").hexdigest()
    assert hash_file(f) == expected


def test_hash_file_stable_for_same_content(tmp_path):
    a = tmp_path / "a.txt"
    b = tmp_path / "b.txt"
    a.write_bytes(b"same")
    b.write_bytes(b"same")
    assert hash_file(a) == hash_file(b)
