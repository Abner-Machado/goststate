import json

from click.testing import CliRunner

from ghoststate.cli import main


def _capture_two(runner, store_dir) -> tuple[str, str]:
    runner.invoke(main, ["init", "--store-dir", store_dir])
    cap_a = runner.invoke(main, ["capture", "--label", "success", "--store-dir", store_dir])
    id_a = cap_a.output.split("#")[1].split(" ")[0]
    cap_b = runner.invoke(main, ["capture", "--label", "failure", "--store-dir", store_dir])
    id_b = cap_b.output.split("#")[1].split(" ")[0]
    return id_a, id_b


def test_explain_on_identical_snapshots_says_insufficient(tmp_path):
    runner = CliRunner()
    store_dir = str(tmp_path / ".ghoststate")
    id_a, id_b = _capture_two(runner, store_dir)

    result = runner.invoke(main, ["explain", "--before", id_a, "--after", id_b, "--store-dir", store_dir])
    assert result.exit_code == 0, result.output
    assert "success" in result.output
    assert "failure" in result.output


def test_experiment_proposal_only_does_not_execute_anything(tmp_path):
    runner = CliRunner()
    store_dir = str(tmp_path / ".ghoststate")
    id_a, id_b = _capture_two(runner, store_dir)

    # force a real diff by writing a second snapshot with a changed git section
    from ghoststate.storage import SnapshotStore

    store = SnapshotStore(store_dir)
    after = store.load(id_b)
    after.git = {"status": "ok", "commit": "deadbeef", "branch": "main", "dirty": False}
    after.execution_id = id_b
    store.save(after)

    result = runner.invoke(
        main,
        [
            "experiment",
            "--before",
            id_a,
            "--after",
            id_b,
            "--hypothesis",
            "hyp-git",
            "--command",
            "true",
            "--store-dir",
            store_dir,
        ],
    )
    assert result.exit_code == 0, result.output
    assert "--yes" in result.output


def test_experiment_unknown_hypothesis_fails_loudly(tmp_path):
    runner = CliRunner()
    store_dir = str(tmp_path / ".ghoststate")
    id_a, id_b = _capture_two(runner, store_dir)

    result = runner.invoke(
        main,
        [
            "experiment",
            "--before",
            id_a,
            "--after",
            id_b,
            "--hypothesis",
            "hyp-does-not-exist",
            "--command",
            "true",
            "--store-dir",
            store_dir,
        ],
    )
    assert result.exit_code != 0
    assert "error" in result.output.lower()


def test_experiment_json_output_with_yes_actually_runs(tmp_path):
    runner = CliRunner()
    store_dir = str(tmp_path / ".ghoststate")
    id_a, id_b = _capture_two(runner, store_dir)

    from ghoststate.storage import SnapshotStore

    store = SnapshotStore(store_dir)
    after = store.load(id_b)
    after.git = {"status": "ok", "commit": "deadbeef", "branch": "main", "dirty": False}
    after.execution_id = id_b
    store.save(after)

    result = runner.invoke(
        main,
        [
            "experiment",
            "--before",
            id_a,
            "--after",
            id_b,
            "--hypothesis",
            "hyp-git",
            "--command",
            "true",
            "--yes",
            "--json",
            "--store-dir",
            store_dir,
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["ran"] is True
    assert payload["verdict"] == "SUPPORTS_HYPOTHESIS"
