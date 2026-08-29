from ghoststate.diff import ChangeStatus, Relevance, diff_snapshots
from ghoststate.schema import Snapshot


def _snap(execution_id: str, **sections) -> Snapshot:
    return Snapshot(
        schema_version="1.0",
        execution_id=execution_id,
        timestamp="2026-01-01T00:00:00+00:00",
        label="",
        **sections,
    )


def test_diff_of_identical_snapshots_is_empty():
    a = _snap("a", system={"os": "Linux", "kernel": "6.8"})
    b = _snap("b", system={"os": "Linux", "kernel": "6.8"})
    result = diff_snapshots(a, b)
    assert result.changed() == []
    assert all(d.status == ChangeStatus.UNCHANGED for d in result.diffs)


def test_diff_invariant_self_comparison_is_always_empty():
    snap = _snap(
        "a",
        system={"os": "Linux"},
        network={"ipv6_loopback_bind": True},
        git={"commit": "deadbeef"},
    )
    result = diff_snapshots(snap, snap)
    assert result.changed() == []


def test_changed_value_is_flagged_changed_with_correct_relevance():
    a = _snap("a", network={"ipv6_loopback_bind": False})
    b = _snap("b", network={"ipv6_loopback_bind": True})
    result = diff_snapshots(a, b)
    (only,) = result.changed()
    assert only.status == ChangeStatus.CHANGED
    assert only.relevance == Relevance.HIGH
    assert only.before is False
    assert only.after is True


def test_added_and_removed_are_distinguished_from_changed():
    a = _snap("a", system={"os": "Linux"})
    b = _snap("b", system={"os": "Linux", "kernel": "6.8"})
    result = diff_snapshots(a, b)
    statuses = {d.path: d.status for d in result.changed()}
    assert statuses["system.kernel"] == ChangeStatus.ADDED

    result_reverse = diff_snapshots(b, a)
    statuses_reverse = {d.path: d.status for d in result_reverse.changed()}
    assert statuses_reverse["system.kernel"] == ChangeStatus.REMOVED


def test_unchanged_facts_always_carry_none_relevance():
    a = _snap("a", system={"os": "Linux"})
    b = _snap("b", system={"os": "Linux"})
    result = diff_snapshots(a, b)
    assert all(d.relevance == Relevance.NONE for d in result.diffs if d.status == ChangeStatus.UNCHANGED)


def test_schema_incompatibility_is_reported():
    a = Snapshot(schema_version="1.0", execution_id="a", timestamp="t", label="")
    b = Snapshot(schema_version="2.0", execution_id="b", timestamp="t", label="")
    result = diff_snapshots(a, b)
    assert result.schema_compatible is False


def test_dependency_package_diff_gets_low_relevance():
    a = _snap("a", dependencies={"python": {"packages": {"requests": "2.28.0"}}})
    b = _snap("b", dependencies={"python": {"packages": {"requests": "2.31.0"}}})
    result = diff_snapshots(a, b)
    (only,) = result.changed()
    assert only.relevance == Relevance.LOW


def test_git_commit_change_gets_high_relevance():
    a = _snap("a", git={"commit": "aaa"})
    b = _snap("b", git={"commit": "bbb"})
    result = diff_snapshots(a, b)
    (only,) = result.changed()
    assert only.relevance == Relevance.HIGH
