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

import functools
import ipaddress
import json
import socket
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

Resolver = Callable[[str], list[str]]
# A transport takes (url, json-payload) and returns the parsed JSON response.
Transport = Callable[[str, dict[str, Any]], dict[str, Any]]


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
    if not addresses or not all(_is_loopback_ip(addr) is True for addr in addresses):
        raise AirGapError(f"host {host!r} does not resolve to loopback-only: {addresses}")


def _default_transport(
    url: str, payload: dict[str, Any], *, timeout_s: float = 120.0
) -> dict[str, Any]:
    """POST an OpenAI-compatible chat-completions request to a local endpoint.

    Only ever reached after :func:`assert_local` has passed, so ``url`` is
    loopback. Kept tiny and stdlib-only; tests inject a fake transport instead.

    Spec 0017 (B3): ``timeout_s`` bounds the call so a stalled/torn-down endpoint
    raises instead of blocking forever. It is a **per-socket-op** timeout
    (``urlopen(timeout=)`` — connect and each blocking read), **not** a total
    deadline. The default is finite (never ``None``) so a bare call can never hang;
    :class:`ModelGateway` binds its configured ``timeout_s`` here at call time.
    """
    body = json.dumps(payload).encode("utf-8")
    req = Request(url, data=body, headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=timeout_s) as resp:  # noqa: S310 - loopback-only, air-gap asserted
        return json.loads(resp.read().decode("utf-8"))


@dataclass
class ModelGateway:
    """Single outbound abstraction over the local model endpoint.

    The air-gap is asserted (at name-resolution time) before any request leaves
    the process; the request itself goes through an injectable transport so the
    gateway stays endpoint-agnostic and unit-testable without a network.
    """

    api_base: str
    model: str = "local"
    allow_remote: bool = False
    # Spec 0017 (B3 / D3): the outbound HTTP timeout, bound onto the default
    # transport. Finite by default (never None) so any direct construction — not
    # just the wired sites — is hang-bounded out of the box.
    timeout_s: float = 120.0

    def assert_local(self, resolver: Resolver | None = None) -> None:
        assert_local(self.api_base, allow_remote=self.allow_remote, resolver=resolver)

    def complete(
        self,
        messages: Sequence[dict[str, str]],
        *,
        transport: Transport | None = None,
        resolver: Resolver | None = None,
        **params: Any,
    ) -> str:
        """Run a chat completion against the local endpoint, air-gap first.

        ``assert_local`` runs **before** the transport is touched, so a
        non-loopback (or non-loopback-resolving) endpoint raises
        :class:`AirGapError` and nothing is ever sent.
        """
        self.assert_local(resolver=resolver)
        # D3: bind the configured timeout onto the default transport ONLY when no
        # transport is injected — an explicit two-arg fake must stay untouched.
        send = transport or functools.partial(_default_transport, timeout_s=self.timeout_s)
        url = urljoin(self.api_base.rstrip("/") + "/", "chat/completions")
        payload: dict[str, Any] = {"model": self.model, "messages": list(messages), **params}
        response = send(url, payload)
        return response["choices"][0]["message"]["content"]
