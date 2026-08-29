"""Adversarial tests against SnapshotStore's execution_id handling."""

import pytest

from ghoststate.schema import Snapshot
from ghoststate.storage import InvalidExecutionId, SnapshotStore

TRAVERSAL_PAYLOADS = [
    "../../../../etc/passwd",
    "..\\..\\..\\windows\\system32",
    "/etc/passwd",
    "a" * 4 + "/../../evil",
    "....//....//etc/passwd",
    "",
    "a;rm -rf /",
    "a$(rm -rf /)",
]


@pytest.mark.parametrize("payload", TRAVERSAL_PAYLOADS)
def test_load_rejects_path_traversal_payloads(tmp_path, payload):
    store = SnapshotStore(tmp_path / ".ghoststate")
    with pytest.raises(InvalidExecutionId):
        store.load(payload)


@pytest.mark.parametrize("payload", TRAVERSAL_PAYLOADS)
def test_save_path_is_confined_to_snapshots_dir_regardless_of_execution_id(tmp_path, payload):
    store = SnapshotStore(tmp_path / ".ghoststate")
    snap = Snapshot(schema_version="1.0", execution_id=payload, timestamp="t", label="")
    with pytest.raises(InvalidExecutionId):
        store.save(snap)
    # nothing should have been written outside the store, and the store
    # dir itself must not have escaped its intended root
    assert not (tmp_path / "etc").exists()


def test_valid_id_still_works_after_hardening(tmp_path):
    store = SnapshotStore(tmp_path / ".ghoststate")
    snap = Snapshot(schema_version="1.0", execution_id="deadbeef1234", timestamp="t", label="")
    path = store.save(snap)
    assert path.exists()
    assert path.resolve().is_relative_to((tmp_path / ".ghoststate").resolve())
