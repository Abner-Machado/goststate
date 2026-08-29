from pathlib import Path

from click.testing import CliRunner

from ghoststate import demo_runner
from ghoststate.cli import main


def test_demo_runs_end_to_end_and_finds_the_git_hypothesis(tmp_path):
    runner = CliRunner()
    store_dir = str(tmp_path / "demo-store")

    result = runner.invoke(main, ["demo", "--store-dir", store_dir])

    assert result.exit_code == 0, result.output
    assert "STARTED OK" in result.output
    assert "STARTUP FAILED" in result.output
    assert "GhostState Investigation" in result.output
    assert "Insufficient evidence" not in result.output
    assert "git" in result.output.lower()


def test_demo_with_yes_runs_a_real_confirming_experiment(tmp_path):
    runner = CliRunner()
    store_dir = str(tmp_path / "demo-store")

    result = runner.invoke(main, ["demo", "--yes", "--store-dir", store_dir])

    assert result.exit_code == 0, result.output
    assert "Running confirming experiment" in result.output
    assert "SUPPORTS_HYPOTHESIS" in result.output


def test_demo_is_deterministic_across_repeated_runs(tmp_path):
    # Execution ids and git commit hashes are inherently non-deterministic
    # (hashes embed a commit timestamp) — what must stay identical across
    # runs is the *outcome*: how many properties changed, which section
    # wins as the top candidate, and its confidence score. That is the
    # actual determinism contract the diff/evidence engine makes.
    runner = CliRunner()
    outcomes = []
    for i in range(2):
        result = runner.invoke(main, ["demo", "--store-dir", str(tmp_path / f"run-{i}")])
        assert result.exit_code == 0, result.output
        lines = result.output.splitlines()
        changed_line = next(line for line in lines if "properties changed" in line)
        top_candidate_line = next(line for line in lines if "confidence candidate" in line)
        confidence_line = next(line for line in lines if "heuristic confidence" in line)
        outcomes.append((changed_line, top_candidate_line, confidence_line))
    assert outcomes[0] == outcomes[1]


def test_demo_fails_cleanly_when_target_app_is_missing(tmp_path, monkeypatch):
    # Regression: a real (non-editable) wheel install doesn't ship examples/,
    # so _TARGET_APP won't exist. This must be a clean CLI error, not a
    # raw traceback.
    monkeypatch.setattr(demo_runner, "_TARGET_APP", Path("/nonexistent/target_app.py"))
    runner = CliRunner()

    result = runner.invoke(main, ["demo", "--store-dir", str(tmp_path / "demo-store")])

    assert result.exit_code != 0
    assert "error" in result.output.lower()
    assert "Traceback" not in result.output
