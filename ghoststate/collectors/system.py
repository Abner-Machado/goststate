"""System-level collector: OS, kernel, architecture, CPU, memory, filesystem, mounts."""

from __future__ import annotations

import os
import platform
import shutil
from typing import Any


def collect_system() -> dict[str, Any]:
    data: dict[str, Any] = {
        "os": platform.system(),
        "os_release": _safe(platform.release),
        "os_version": _safe(platform.version),
        "kernel": _safe(platform.release) if platform.system() == "Linux" else None,
        "architecture": platform.machine(),
        "cpu_count": os.cpu_count(),
        "python_build": platform.python_build(),
    }

    distro = _linux_distro()
    if distro:
        data["distro"] = distro

    mem = _memory_info()
    if mem:
        data["memory"] = mem

    fs = _filesystem_info()
    if fs:
        data["filesystem"] = fs

    limits = _resource_limits()
    if limits:
        data["limits"] = limits

    return data


def _safe(fn):
    try:
        return fn()
    except Exception:
        return None


def _linux_distro() -> dict[str, str] | None:
    path = "/etc/os-release"
    if not os.path.exists(path):
        return None
    try:
        info: dict[str, str] = {}
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if "=" not in line:
                    continue
                key, _, value = line.strip().partition("=")
                info[key] = value.strip('"')
        return {
            "id": info.get("ID", "unknown"),
            "version_id": info.get("VERSION_ID", "unknown"),
            "pretty_name": info.get("PRETTY_NAME", "unknown"),
        }
    except OSError:
        return None


def _memory_info() -> dict[str, Any] | None:
    path = "/proc/meminfo"
    if not os.path.exists(path):
        return None
    try:
        values: dict[str, int] = {}
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                key, _, rest = line.partition(":")
                parts = rest.strip().split()
                if parts and parts[0].isdigit():
                    values[key] = int(parts[0])
        total_kb = values.get("MemTotal")
        if total_kb is None:
            return None
        return {
            "total_mb": round(total_kb / 1024),
            "swap_total_mb": round(values.get("SwapTotal", 0) / 1024),
        }
    except OSError:
        return None


def _filesystem_info() -> dict[str, Any] | None:
    try:
        usage = shutil.disk_usage("/")
    except OSError:
        return None

    fs_type = _mount_fs_type("/")
    return {
        "root_fs_type": fs_type,
        "root_total_gb": round(usage.total / (1024**3), 1),
    }


def _mount_fs_type(path: str) -> str | None:
    """Best-effort filesystem type for `path` by scanning /proc/mounts.

    Picks the mount entry with the longest matching prefix, which is the
    same "closest ancestor mount" rule the kernel itself uses.
    """
    mounts_path = "/proc/mounts"
    if not os.path.exists(mounts_path):
        return None
    best_match = ""
    best_type = None
    try:
        with open(mounts_path, encoding="utf-8") as fh:
            for line in fh:
                parts = line.split()
                if len(parts) < 3:
                    continue
                _, mount_point, fs_type = parts[0], parts[1], parts[2]
                if path.startswith(mount_point) and len(mount_point) > len(best_match):
                    best_match = mount_point
                    best_type = fs_type
    except OSError:
        return None
    return best_type


def _resource_limits() -> dict[str, Any] | None:
    try:
        import resource
    except ImportError:
        return None
    try:
        nofile = resource.getrlimit(resource.RLIMIT_NOFILE)
        nproc_limit = None
        if hasattr(resource, "RLIMIT_NPROC"):
            nproc_limit = resource.getrlimit(resource.RLIMIT_NPROC)[0]
        return {
            "open_files_soft": nofile[0],
            "open_files_hard": nofile[1],
            "max_processes_soft": nproc_limit,
        }
    except (ValueError, OSError):
        return None
