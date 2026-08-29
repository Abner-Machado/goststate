"""Dependency collector.

MVP scope: Python only, via `importlib.metadata` (stdlib, no subprocess,
no network). Other ecosystems (Node, Java, Go, .NET) are explicitly
reported as unsupported rather than silently omitted or guessed — see
`docs/ARCHITECTURE.md` for why this is a deliberate v0.1.0 cut, not an
oversight.
"""

from __future__ import annotations

from typing import Any


def collect_dependencies() -> dict[str, Any]:
    packages = _python_packages()
    return {
        "python": {
            "status": "ok",
            "package_count": len(packages),
            "packages": packages,
        },
        "node": {"status": "not_supported_in_v0.1"},
        "java": {"status": "not_supported_in_v0.1"},
        "go": {"status": "not_supported_in_v0.1"},
        "dotnet": {"status": "not_supported_in_v0.1"},
    }


def _python_packages() -> dict[str, str]:
    try:
        from importlib import metadata
    except ImportError:
        return {}

    packages: dict[str, str] = {}
    try:
        for dist in metadata.distributions():
            # PackageMetadata is a Message subclass and supports .get() at
            # runtime; the typeshed stub for this protocol doesn't expose
            # it, hence the targeted ignore rather than a real bug.
            name = dist.metadata.get("Name")  # type: ignore[attr-defined]
            version = dist.version
            if name and version:
                packages[name] = version
    except Exception:
        return {}
    return dict(sorted(packages.items(), key=lambda kv: kv[0].lower()))
