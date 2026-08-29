"""Git collector: commit, branch, dirty state. Never source code content."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

_TIMEOUT_SECONDS = 3


def collect_git(repo_path: str = ".") -> dict[str, Any]:
    if not _looks_like_git_repo(repo_path):
        return {"status": "not_a_git_repository"}

    commit = _run(["git", "rev-parse", "HEAD"], repo_path)
    branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], repo_path)
    status = _run(["git", "status", "--porcelain"], repo_path)

    if commit is None:
        return {"status": "git_command_unavailable_or_failed"}

    return {
        "status": "ok",
        "commit": commit,
        "branch": branch,
        "dirty": bool(status) if status is not None else None,
        "changed_files_count": len(status.splitlines()) if status else 0,
    }


def _looks_like_git_repo(path: str) -> bool:
    return (Path(path) / ".git").exists()


def _run(command: list[str], cwd: str) -> str | None:
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_SECONDS,
            check=False,
        )
        if result.returncode != 0:
            return None
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, OSError):
        return None
