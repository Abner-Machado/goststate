"""Orchestrates all collectors into a single Snapshot.

This is the only place that knows about every collector module. Adding a
new collector means adding one call here and one section to
`Snapshot.sections()` — nothing else in the diff/evidence/investigation
layers needs to change, because they operate generically over
`Snapshot.sections()`.
"""

from __future__ import annotations

import datetime as _dt

from . import SCHEMA_VERSION
from .collectors.config import collect_configuration_metadata
from .collectors.containers import collect_containers
from .collectors.dependencies import collect_dependencies
from .collectors.git import collect_git
from .collectors.network import collect_network
from .collectors.runtime import collect_runtime
from .collectors.system import collect_system
from .schema import Snapshot, new_execution_id


def capture_snapshot(*, label: str = "", repo_path: str = ".", env: dict[str, str] | None = None) -> Snapshot:
    warnings: list[str] = []

    def _try(name: str, fn):
        try:
            return fn()
        except Exception as exc:  # a collector must never abort the capture
            warnings.append(f"{name} collector failed: {exc}")
            return {"status": "collector_error"}

    snapshot = Snapshot(
        schema_version=SCHEMA_VERSION,
        execution_id=new_execution_id(),
        timestamp=_dt.datetime.now(_dt.timezone.utc).isoformat(),
        label=label,
        system=_try("system", collect_system),
        runtime=_try("runtime", collect_runtime),
        dependencies=_try("dependencies", collect_dependencies),
        network=_try("network", collect_network),
        containers=_try("containers", collect_containers),
        git=_try("git", lambda: collect_git(repo_path)),
        configuration_metadata=_try("configuration_metadata", lambda: collect_configuration_metadata(env)),
        collector_warnings=warnings,
    )
    return snapshot
