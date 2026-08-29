"""Runtime collector: language runtimes detectable from the current host.

GhostState never claims support for a runtime it did not actually probe.
Each entry is either a concrete version or explicitly "not_detected" —
there is no silent guessing.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from typing import Any

_PROBES: dict[str, list[str]] = {
    "node": ["node", "--version"],
    "java": ["java", "-version"],
    "go": ["go", "version"],
    "dotnet": ["dotnet", "--version"],
    "ruby": ["ruby", "--version"],
    "php": ["php", "--version"],
}

_PROBE_TIMEOUT_SECONDS = 3


def collect_runtime() -> dict[str, Any]:
    data: dict[str, Any] = {
        "python": {
            "version": sys.version.split()[0],
            "implementation": sys.implementation.name,
            "executable": sys.executable,
        }
    }

    for name, command in _PROBES.items():
        data[name] = _probe(name, command)

    return data


def _probe(name: str, command: list[str]) -> dict[str, Any]:
    binary = shutil.which(command[0])
    if binary is None:
        return {"status": "not_detected"}

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=_PROBE_TIMEOUT_SECONDS,
            check=False,
        )
        output = (result.stdout or result.stderr).strip()
        first_line = output.splitlines()[0] if output else ""
        return {"status": "detected", "path": binary, "version_string": first_line}
    except (subprocess.TimeoutExpired, OSError) as exc:
        return {"status": "detection_failed", "path": binary, "error": str(exc)}
