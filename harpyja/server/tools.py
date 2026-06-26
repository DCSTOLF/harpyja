"""Wave-0 stub implementations of the MCP tools.

`locate_stub` proves the contract end-to-end: it accepts every documented input
field and returns a schema-valid EMPTY :class:`LocateResult` — no retrieval, no
exceptions (AC5). Real retrieval arrives in Wave 1+.
"""

from __future__ import annotations

from harpyja.server.types import LocateResult, Mode

_STUB_NOTE = "wave-0 stub: no retrieval"


def locate_stub(
    query: str,
    repo_path: str,
    mode: Mode = "auto",
    max_results: int = 8,
    language_hint: str | None = None,
) -> LocateResult:
    """Return an empty, schema-valid LocateResult regardless of inputs."""
    return LocateResult(
        citations=[],
        confidence="low",
        tiers_run=[],
        notes=_STUB_NOTE,
    )
