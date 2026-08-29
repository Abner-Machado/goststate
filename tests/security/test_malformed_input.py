"""Regression tests for parser/robustness bugs found during the internal red team pass."""

import shlex

import pytest

from ghoststate.storage import SnapshotCorrupted, SnapshotStore


def test_corrupted_snapshot_file_raises_a_clean_error_not_a_raw_traceback(tmp_path):
    store = SnapshotStore(tmp_path / ".ghoststate")
    store.init()
    bad_file = store.base_dir / "snapshots" / "deadbeef1234.json"
    bad_file.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(SnapshotCorrupted):
        store.load("deadbeef1234")


def test_snapshot_with_wrong_shape_raises_snapshot_corrupted(tmp_path):
    store = SnapshotStore(tmp_path / ".ghoststate")
    store.init()
    bad_file = store.base_dir / "snapshots" / "deadbeef1234.json"
    bad_file.write_text('"just a json string, not an object"', encoding="utf-8")

    with pytest.raises(SnapshotCorrupted):
        store.load("deadbeef1234")


def test_experiment_command_with_quoted_arguments_parses_correctly():
    # regression: a naive `str.split()` would break "python3 -c 'print(1 + 1)'"
    # into the wrong argv; shlex.split respects the quoting.
    parsed = shlex.split("python3 -c 'print(1 + 1)'")
    assert parsed == ["python3", "-c", "print(1 + 1)"]
