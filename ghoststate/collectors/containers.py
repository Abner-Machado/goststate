"""Container collector: detect containerization metadata, never secrets.

Only detects presence and coarse metadata (runtime name, cgroup-derived
container id, image digest if exposed via a well-known env var). Never
inspects container image layers, mounted volumes, or env values beyond
the redaction-safe presence check already applied by config.py.
"""

from __future__ import annotations

import os
from typing import Any


def collect_containers() -> dict[str, Any]:
    in_container, runtime_name = _detect_container_runtime()
    data: dict[str, Any] = {"running_in_container": in_container}
    if runtime_name:
        data["runtime"] = runtime_name

    container_id = _cgroup_container_id()
    if container_id:
        data["container_id_short"] = container_id[:12]

    return data


def _detect_container_runtime() -> tuple[bool, str | None]:
    if os.path.exists("/.dockerenv"):
        return True, "docker"
    if os.environ.get("KUBERNETES_SERVICE_HOST"):
        return True, "kubernetes"
    cgroup_path = "/proc/1/cgroup"
    if os.path.exists(cgroup_path):
        try:
            with open(cgroup_path, encoding="utf-8") as fh:
                content = fh.read()
            if "docker" in content:
                return True, "docker"
            if "containerd" in content:
                return True, "containerd"
            if "kubepods" in content:
                return True, "kubernetes"
        except OSError:
            pass
    return False, None


def _cgroup_container_id() -> str | None:
    cgroup_path = "/proc/self/cgroup"
    if not os.path.exists(cgroup_path):
        return None
    try:
        with open(cgroup_path, encoding="utf-8") as fh:
            for line in fh:
                parts = line.strip().split("/")
                candidate = parts[-1]
                if len(candidate) == 64 and all(c in "0123456789abcdef" for c in candidate):
                    return candidate
    except OSError:
        return None
    return None
