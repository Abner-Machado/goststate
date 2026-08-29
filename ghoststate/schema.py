"""Versioned, deterministic snapshot schema.

A Snapshot is the atomic unit GhostState compares. It must be:
  - deterministic: capturing twice on an unchanged system yields an
    identical snapshot body (timestamp/execution_id excluded).
  - versioned: `schema_version` lets diff/evidence code refuse to compare
    snapshots produced by incompatible collector versions instead of
    silently producing garbage.
  - independent of any LLM: this module has no network access and no
    dependency on ghoststate.llm (which does not exist in the core).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

from . import SCHEMA_VERSION


@dataclass
class Snapshot:
    schema_version: str
    execution_id: str
    timestamp: str
    label: str  # free-form, e.g. "success" / "failure" / "" — never interpreted by the core
    system: dict[str, Any] = field(default_factory=dict)
    runtime: dict[str, Any] = field(default_factory=dict)
    dependencies: dict[str, Any] = field(default_factory=dict)
    network: dict[str, Any] = field(default_factory=dict)
    containers: dict[str, Any] = field(default_factory=dict)
    git: dict[str, Any] = field(default_factory=dict)
    configuration_metadata: dict[str, Any] = field(default_factory=dict)
    collector_warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, *, indent: int | None = 2) -> str:
        # sort_keys=True is what makes the body deterministic/diffable
        # across runs and across machines with different dict insertion
        # order (Python dicts preserve insertion order, JSON does not
        # guarantee it on disk unless we force it here).
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True, default=str)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Snapshot:
        if not isinstance(data, dict):
            raise TypeError(f"snapshot data must be a JSON object, got {type(data).__name__}")
        known_fields = {f for f in cls.__dataclass_fields__}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        try:
            return cls(**filtered)
        except TypeError as exc:
            raise TypeError(f"snapshot data is missing required fields: {exc}") from exc

    @classmethod
    def from_json(cls, raw: str) -> Snapshot:
        return cls.from_dict(json.loads(raw))

    def sections(self) -> dict[str, dict[str, Any]]:
        """Sections eligible for diffing (excludes identity/bookkeeping fields)."""
        return {
            "system": self.system,
            "runtime": self.runtime,
            "dependencies": self.dependencies,
            "network": self.network,
            "containers": self.containers,
            "git": self.git,
            "configuration_metadata": self.configuration_metadata,
        }


def new_execution_id() -> str:
    import secrets

    return secrets.token_hex(6)


def is_schema_compatible(version: str) -> bool:
    """v1.x snapshots are mutually comparable; a major bump means incompatible."""
    return version.split(".")[0] == SCHEMA_VERSION.split(".")[0]
