"""Model Gateway shell + the air-gap assertion (AC8).

This is the single place the air-gap guarantee is enforced. In Wave 0 the
gateway makes **no live calls** — it only validates that a configured endpoint
is loopback-only.

`assert_local` accepts an endpoint URL or bare host and passes iff the host is
loopback:
- IPv4 in ``127.0.0.0/8`` or IPv6 ``::1`` (via :mod:`ipaddress`),
- the literal ``localhost`` (canonically loopback, resolved with no DNS),
- a hostname whose injected resolver returns only loopback addresses.

Everything else raises :class:`AirGapError` unless ``allow_remote=True``. IP and
``localhost`` endpoints never invoke the resolver, so the common air-gapped case
makes no network call.
"""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlsplit

Resolver = Callable[[str], list[str]]


class AirGapError(ValueError):
    """Raised when a configured endpoint is not loopback-only."""


def _default_resolver(host: str) -> list[str]:
    """Resolve a hostname to its IP strings via the system resolver.

    Only called for non-``localhost`` hostnames; loopback IPs and ``localhost``
    short-circuit before reaching here, so an air-gapped loopback config never
    touches DNS.
    """
    infos = socket.getaddrinfo(host, None)
    return [info[4][0] for info in infos]


def _extract_host(endpoint: str) -> str:
    """Pull the host out of a URL or a bare host[:port] string."""
    candidate = endpoint.strip()
    # Raw IPv6 literal without scheme or brackets, e.g. "::1".
    if "://" not in candidate and not candidate.startswith("[") and candidate.count(":") >= 2:
        return candidate
    if "://" not in candidate:
        candidate = f"scheme://{candidate}"
    return urlsplit(candidate).hostname or endpoint.strip()


def _is_loopback_ip(host: str) -> bool | None:
    """True/False if ``host`` is an IP; None if it is not an IP literal."""
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return None


def assert_local(
    endpoint: str,
    allow_remote: bool = False,
    resolver: Resolver | None = None,
) -> None:
    """Assert ``endpoint`` is loopback-only, else raise :class:`AirGapError`."""
    if allow_remote:
        return

    host = _extract_host(endpoint)
    if not host:
        raise AirGapError(f"endpoint has no host: {endpoint!r}")

    loopback = _is_loopback_ip(host)
    if loopback is True:
        return
    if loopback is False:
        raise AirGapError(f"non-loopback endpoint rejected: {endpoint!r}")

    # Hostname (not an IP literal).
    if host.lower() == "localhost":
        return

    resolve = resolver or _default_resolver
    addresses = resolve(host)
    if not addresses or not all(
        _is_loopback_ip(addr) is True for addr in addresses
    ):
        raise AirGapError(
            f"host {host!r} does not resolve to loopback-only: {addresses}"
        )


@dataclass
class ModelGateway:
    """Single outbound abstraction over the local model endpoint.

    Wave 0: holds configuration and enforces the air-gap. No request path yet.
    """

    api_base: str
    model: str = "local"
    allow_remote: bool = False

    def assert_local(self, resolver: Resolver | None = None) -> None:
        assert_local(self.api_base, allow_remote=self.allow_remote, resolver=resolver)
