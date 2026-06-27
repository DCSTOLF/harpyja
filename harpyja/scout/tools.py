"""The exact, local-only tool set handed to the Scout backend (AC10).

FastContext gets **only** these four entries — bounded read-only `read`/`glob`/
`grep` wrappers plus the loopback-enforced Gateway model client — and nothing
else (no raw base_url, no env-derived endpoint, no HTTP client/session). This
constrains everything Harpyja hands the backend; it is asserted by a positive
equality on the returned mapping, not by trying to prove a negative.
"""

from __future__ import annotations

from typing import Any


def build_tool_whitelist(
    model_client: Any,
    *,
    read: Any,
    glob: Any,
    grep: Any,
) -> dict[str, Any]:
    """Return exactly the four whitelisted tools, keyed by name."""
    return {"read": read, "glob": glob, "grep": grep, "model": model_client}
