"""Network collector: local capability probes only.

GhostState never performs outbound scanning or hits third-party hosts.
Every probe here is local: binding to loopback, and resolving `localhost`
through the system resolver. This is enough to observe the class of
failures the project targets (IPv4/IPv6 availability, resolver behavior
changing between two executions) without turning the tool into anything
that could be used offensively.
"""

from __future__ import annotations

import socket
from typing import Any


def collect_network() -> dict[str, Any]:
    return {
        "ipv4_loopback_bind": _can_bind(socket.AF_INET, "127.0.0.1"),
        "ipv6_loopback_bind": _can_bind(socket.AF_INET6, "::1"),
        "hostname": _safe(socket.gethostname),
        "localhost_resolves_a": _resolves("localhost", socket.AF_INET),
        "localhost_resolves_aaaa": _resolves("localhost", socket.AF_INET6),
    }


def _can_bind(family: int, address: str) -> bool:
    try:
        with socket.socket(family, socket.SOCK_STREAM) as sock:
            sock.bind((address, 0))
        return True
    except OSError:
        return False


def _resolves(host: str, family: int) -> bool:
    try:
        socket.getaddrinfo(host, None, family)
        return True
    except OSError:
        return False


def _safe(fn):
    try:
        return fn()
    except OSError:
        return None
