"""`harpyja doctor` — environment preflight (AC10).

Reports presence of ``rg`` and ``deno`` on PATH, the configured model-endpoint
URL, and a **static** air-gap status (the same loopback check the gateway
enforces). It makes **no live call** to the endpoint — a loopback/IP endpoint
never touches DNS.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable
from dataclasses import dataclass

from harpyja.config.settings import Settings
from harpyja.gateway.gateway import AirGapError, assert_local

Which = Callable[[str], str | None]


@dataclass
class DoctorReport:
    rg_present: bool
    deno_present: bool
    endpoint_url: str
    air_gap_ok: bool
    air_gap_detail: str


def run_doctor(settings: Settings, which: Which = shutil.which) -> DoctorReport:
    """Gather preflight facts without making any network call."""
    rg_present = which("rg") is not None
    deno_present = which("deno") is not None

    endpoint = settings.lm_api_base
    try:
        assert_local(endpoint, allow_remote=settings.allow_remote)
        air_gap_ok = True
        detail = "loopback-only" if not settings.allow_remote else "allow_remote set"
    except AirGapError as exc:
        air_gap_ok = False
        detail = str(exc)

    return DoctorReport(
        rg_present=rg_present,
        deno_present=deno_present,
        endpoint_url=endpoint,
        air_gap_ok=air_gap_ok,
        air_gap_detail=detail,
    )


def format_report(report: DoctorReport) -> str:
    """Render a human-readable preflight report."""

    def mark(ok: bool) -> str:
        return "ok" if ok else "MISSING"

    lines = [
        "harpyja doctor",
        f"  ripgrep (rg):   {mark(report.rg_present)}",
        f"  deno:           {mark(report.deno_present)}",
        f"  model endpoint: {report.endpoint_url}",
        f"  air-gap:        {'ok' if report.air_gap_ok else 'FAIL'} ({report.air_gap_detail})",
    ]
    return "\n".join(lines)
