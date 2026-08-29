"""Local, file-based snapshot storage. No database, no network, no daemon.

Security note: `execution_id` is attacker-influenceable input whenever it
originates from `--id` on the CLI, so every path built from it is
validated against `_ID_PATTERN` first. This is what stands between
`ghoststate export --id ../../../../etc/passwd` and a real path
traversal — see tests/security/test_path_traversal.py.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .schema import Snapshot

_ID_PATTERN = re.compile(r"^[a-f0-9]{4,64}$")

DEFAULT_STORE_DIRNAME = ".ghoststate"


class InvalidExecutionId(ValueError):
    pass


class SnapshotNotFound(LookupError):
    pass


class SnapshotCorrupted(ValueError):
    """Raised when a stored snapshot file exists but is not valid JSON.

    Kept distinct from InvalidExecutionId/SnapshotNotFound so callers (the
    CLI in particular) can tell "you asked for something that doesn't
    exist" apart from "the thing on disk is broken" — the latter is
    something a user can fix (re-capture) but shouldn't have to debug
    from a raw traceback.
    """


def _validate_id(execution_id: str) -> str:
    if not _ID_PATTERN.match(execution_id):
        raise InvalidExecutionId(
            f"execution_id {execution_id!r} is not a valid id "
            "(expected 4-64 lowercase hex characters)"
        )
    return execution_id


class SnapshotStore:
    def __init__(self, base_dir: str | Path = DEFAULT_STORE_DIRNAME):
        self.base_dir = Path(base_dir)

    def _path_for(self, execution_id: str) -> Path:
        safe_id = _validate_id(execution_id)
        return self.base_dir / "snapshots" / f"{safe_id}.json"

    def init(self) -> None:
        (self.base_dir / "snapshots").mkdir(parents=True, exist_ok=True)

    def is_initialized(self) -> bool:
        return self.base_dir.exists()

    def save(self, snapshot: Snapshot) -> Path:
        self.init()
        path = self._path_for(snapshot.execution_id)
        path.write_text(snapshot.to_json(), encoding="utf-8")
        return path

    def load(self, execution_id: str) -> Snapshot:
        path = self._path_for(execution_id)
        if not path.exists():
            raise SnapshotNotFound(f"no snapshot found with id {execution_id!r}")
        raw = path.read_text(encoding="utf-8")
        try:
            return Snapshot.from_json(raw)
        except json.JSONDecodeError as exc:
            raise SnapshotCorrupted(
                f"snapshot file for {execution_id!r} at {path} is not valid JSON: {exc}"
            ) from exc
        except TypeError as exc:
            raise SnapshotCorrupted(
                f"snapshot file for {execution_id!r} at {path} does not match the expected schema: {exc}"
            ) from exc

    def list_ids(self) -> list[str]:
        snapshots_dir = self.base_dir / "snapshots"
        if not snapshots_dir.exists():
            return []
        ids = [p.stem for p in snapshots_dir.glob("*.json")]
        # sorted by file mtime, oldest first, so callers can pick "the last two"
        ids.sort(key=lambda i: (snapshots_dir / f"{i}.json").stat().st_mtime)
        return ids

    def latest(self, n: int = 2) -> list[Snapshot]:
        ids = self.list_ids()[-n:]
        return [self.load(i) for i in ids]
