"""Air-gap audit for the Wave 2 symbol layer (AC17).

Tree-sitter parsing must be fully local: the index + locate path must make **no**
outbound network call, and the Wave-0 air-gap surfaces (`gateway.assert_local`, the
loopback inbound-bind default) must be untouched.
"""

from __future__ import annotations

import socket

from harpyja.config.settings import Settings
from harpyja.index.indexer import index_repo
from harpyja.orchestrator.locate import locate
from harpyja.server.types import CodeSpan, LocateRequest


class _SilentEngine:
    def search(self, pattern, scope=None) -> list[CodeSpan]:
        return []


def test_index_and_locate_make_no_outbound_network_call(tmp_path, monkeypatch):
    attempts = []

    def forbid(self, *args, **kwargs):
        attempts.append(args)
        raise AssertionError("network egress attempted in the index/locate path")

    monkeypatch.setattr(socket.socket, "connect", forbid)
    monkeypatch.setattr(socket.socket, "connect_ex", forbid)

    (tmp_path / "a.py").write_text("def foo():\n    pass\n", encoding="utf-8")
    (tmp_path / "b.go").write_text("package m\nfunc F() {}\n", encoding="utf-8")
    # 0004: the new grammars must parse just as locally (no runtime egress).
    (tmp_path / "lib.rs").write_text("fn bar() {}\n", encoding="utf-8")
    (tmp_path / "M.java").write_text("class C { void m() {} }\n", encoding="utf-8")
    (tmp_path / "P.cs").write_text("class C { void M() {} }\n", encoding="utf-8")
    (tmp_path / "u.ts").write_text("interface I { x: number }\n", encoding="utf-8")
    (tmp_path / "v.tsx").write_text("const X = 1;\n", encoding="utf-8")
    (tmp_path / "w.c").write_text("int f(){ return 0; }\n", encoding="utf-8")
    (tmp_path / "x.cpp").write_text("class K { void mm(){} };\n", encoding="utf-8")

    index_repo(tmp_path, Settings())  # real tree-sitter parsing, all grammars
    locate(
        LocateRequest(query="foo", repo_path=str(tmp_path)),
        Settings(),
        engine=_SilentEngine(),
    )
    assert attempts == []


def test_assert_local_and_inbound_bind_defaults_untouched():
    from harpyja.gateway.gateway import assert_local  # noqa: F401 — must still exist
    from harpyja.server.app import DEFAULT_HTTP_HOST

    assert DEFAULT_HTTP_HOST == "127.0.0.1"  # loopback inbound bind unchanged
