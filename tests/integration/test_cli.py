import json

from click.testing import CliRunner

from ghoststate.cli import main


def test_init_capture_compare_investigate_flow(tmp_path):
    runner = CliRunner()
    store_dir = str(tmp_path / ".ghoststate")

    init_result = runner.invoke(main, ["init", "--store-dir", store_dir])
    assert init_result.exit_code == 0, init_result.output

    cap_a = runner.invoke(main, ["capture", "--label", "success", "--store-dir", store_dir])
    assert cap_a.exit_code == 0, cap_a.output
    id_a = cap_a.output.split("#")[1].split(" ")[0]

    cap_b = runner.invoke(main, ["capture", "--label", "failure", "--store-dir", store_dir])
    assert cap_b.exit_code == 0, cap_b.output
    id_b = cap_b.output.split("#")[1].split(" ")[0]

    compare_result = runner.invoke(
        main, ["compare", "--before", id_a, "--after", id_b, "--store-dir", store_dir]
    )
    assert compare_result.exit_code == 0, compare_result.output
    assert "properties unchanged" in compare_result.output

    investigate_result = runner.invoke(
        main, ["investigate", "--before", id_a, "--after", id_b, "--json", "--store-dir", store_dir]
    )
    assert investigate_result.exit_code == 0, investigate_result.output
    payload = json.loads(investigate_result.output)
    assert "sufficient_evidence" in payload


def test_compare_on_unknown_id_fails_loudly(tmp_path):
    runner = CliRunner()
    store_dir = str(tmp_path / ".ghoststate")
    runner.invoke(main, ["init", "--store-dir", store_dir])

    result = runner.invoke(
        main, ["compare", "--before", "deadbeef0000", "--after", "deadbeef0001", "--store-dir", store_dir]
    )
    assert result.exit_code != 0
    assert "error" in result.output.lower()


def test_export_json_round_trips_through_snapshot_schema(tmp_path):
    runner = CliRunner()
    store_dir = str(tmp_path / ".ghoststate")
    runner.invoke(main, ["init", "--store-dir", store_dir])
    cap = runner.invoke(main, ["capture", "--label", "x", "--store-dir", store_dir])
    execution_id = cap.output.split("#")[1].split(" ")[0]

    export_result = runner.invoke(main, ["export", "--id", execution_id, "--store-dir", store_dir])
    assert export_result.exit_code == 0
    data = json.loads(export_result.output)
    assert data["execution_id"] == execution_id
    assert data["schema_version"] == "1.0"


def test_doctor_exits_zero_on_a_healthy_environment(tmp_path):
    runner = CliRunner()
    result = runner.invoke(main, ["doctor", "--store-dir", str(tmp_path / ".ghoststate")], obj={})
    assert result.exit_code == 0, result.output
    assert "OK" in result.output
