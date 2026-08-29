"""Deterministic Execution Diff Engine.

No LLM, no randomness, no network. Given two snapshots it always
produces the same list of PropertyDiff objects. This is the part of
GhostState the rest of the system (evidence, investigation) is built on
top of, and it must be trustworthy on its own — see docs/ARCHITECTURE.md
for why this boundary exists.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from .schema import Snapshot


class ChangeStatus(str, Enum):
    UNCHANGED = "UNCHANGED"
    CHANGED = "CHANGED"
    ADDED = "ADDED"
    REMOVED = "REMOVED"
    UNKNOWN = "UNKNOWN"


class Relevance(str, Enum):
    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


_RELEVANCE_ORDER = [
    Relevance.NONE,
    Relevance.LOW,
    Relevance.MEDIUM,
    Relevance.HIGH,
    Relevance.CRITICAL,
]

# Ordered (regex, relevance) rules matched against the dotted property
# path, e.g. "network.ipv6_loopback_bind" or "dependencies.python.packages.requests".
# First match wins. This table is the whole "why does this matter" model —
# it is data, not a black box, and is meant to be read and extended.
_RELEVANCE_RULES: list[tuple[re.Pattern, Relevance]] = [
    (re.compile(r"^git\.commit$"), Relevance.HIGH),
    (re.compile(r"^git\.dirty$"), Relevance.MEDIUM),
    (re.compile(r"^network\.(ipv4|ipv6)_loopback_bind$"), Relevance.HIGH),
    (re.compile(r"^network\.localhost_resolves_(a|aaaa)$"), Relevance.HIGH),
    (re.compile(r"^system\.kernel$"), Relevance.MEDIUM),
    (re.compile(r"^system\.os_release$"), Relevance.MEDIUM),
    (re.compile(r"^system\.distro\."), Relevance.MEDIUM),
    (re.compile(r"^system\.filesystem\.root_fs_type$"), Relevance.MEDIUM),
    (re.compile(r"^system\.memory\."), Relevance.LOW),
    (re.compile(r"^system\.limits\."), Relevance.LOW),
    (re.compile(r"^containers\.running_in_container$"), Relevance.HIGH),
    (re.compile(r"^containers\.runtime$"), Relevance.HIGH),
    (re.compile(r"^containers\.container_id_short$"), Relevance.LOW),
    (re.compile(r"^runtime\.python\.version$"), Relevance.HIGH),
    (re.compile(r"^runtime\.\w+\.version_string$"), Relevance.MEDIUM),
    (re.compile(r"^runtime\.\w+\.status$"), Relevance.MEDIUM),
    (re.compile(r"^dependencies\.python\.packages\."), Relevance.LOW),
    (re.compile(r"^dependencies\.python\.package_count$"), Relevance.LOW),
    (re.compile(r"^configuration_metadata\.variables\."), Relevance.MEDIUM),
    (re.compile(r"^configuration_metadata\.variable_count$"), Relevance.LOW),
]

_DEFAULT_RELEVANCE = Relevance.LOW


@dataclass
class PropertyDiff:
    path: str
    status: ChangeStatus
    relevance: Relevance
    before: object
    after: object

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "status": self.status.value,
            "relevance": self.relevance.value,
            "before": self.before,
            "after": self.after,
        }


@dataclass
class DiffResult:
    diffs: list[PropertyDiff]
    schema_compatible: bool

    def changed(self) -> list[PropertyDiff]:
        return [d for d in self.diffs if d.status != ChangeStatus.UNCHANGED]

    def by_relevance(self, relevance: Relevance) -> list[PropertyDiff]:
        return [d for d in self.diffs if d.relevance == relevance]

    def summary_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {status.value: 0 for status in ChangeStatus}
        for d in self.diffs:
            counts[d.status.value] += 1
        return counts


def _relevance_for(path: str) -> Relevance:
    for pattern, relevance in _RELEVANCE_RULES:
        if pattern.search(path):
            return relevance
    return _DEFAULT_RELEVANCE


def _flatten(value, prefix: str = "") -> dict[str, object]:
    """Flatten a nested dict into {dotted.path: leaf_value}.

    Lists are treated as opaque leaves (compared by equality, not
    element-wise) to keep the algorithm's behavior easy to reason about;
    element-wise list diffing is a documented non-goal for v0.1.
    """
    flat: dict[str, object] = {}
    if isinstance(value, dict):
        if not value:
            flat[prefix] = {}
            return flat
        for key, sub_value in value.items():
            new_prefix = f"{prefix}.{key}" if prefix else str(key)
            flat.update(_flatten(sub_value, new_prefix))
    else:
        flat[prefix] = value
    return flat


def diff_snapshots(before: Snapshot, after: Snapshot) -> DiffResult:
    schema_compatible = before.schema_version == after.schema_version

    before_flat = _flatten(before.sections())
    after_flat = _flatten(after.sections())

    all_paths = sorted(set(before_flat) | set(after_flat))
    diffs: list[PropertyDiff] = []

    for path in all_paths:
        has_before = path in before_flat
        has_after = path in after_flat
        before_value = before_flat.get(path)
        after_value = after_flat.get(path)

        if has_before and has_after:
            status = ChangeStatus.UNCHANGED if before_value == after_value else ChangeStatus.CHANGED
        elif has_after and not has_before:
            status = ChangeStatus.ADDED
        elif has_before and not has_after:
            status = ChangeStatus.REMOVED
        else:  # pragma: no cover - unreachable given the union above
            status = ChangeStatus.UNKNOWN

        relevance = Relevance.NONE if status == ChangeStatus.UNCHANGED else _relevance_for(path)

        diffs.append(
            PropertyDiff(
                path=path,
                status=status,
                relevance=relevance,
                before=before_value,
                after=after_value,
            )
        )

    return DiffResult(diffs=diffs, schema_compatible=schema_compatible)
