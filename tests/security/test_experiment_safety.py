"""GhostState must never mutate a real system without explicit approval."""

import os

from ghoststate.evidence import Hypothesis
from ghoststate.experiment import Verdict, propose_experiment, run_experiment


def _hypothesis() -> Hypothesis:
    return Hypothesis(
        id="hyp-network",
        section="network",
        summary="test",
        evidence=[],
        confidence_percent=50,
        confidence_bucket="MEDIUM",
    )


def test_experiment_does_not_run_without_approval(tmp_path):
    marker = tmp_path / "should_not_exist"
    proposal = propose_experiment(_hypothesis())
    result = run_experiment(
        proposal,
        command=["python3", "-c", f"open({str(marker)!r}, 'w').close()"],
        approved=False,
    )
    assert result.verdict == Verdict.NOT_RUN
    assert result.ran is False
    assert not marker.exists()


def test_experiment_only_runs_the_explicitly_supplied_command(tmp_path):
    marker = tmp_path / "ran"
    proposal = propose_experiment(_hypothesis())
    result = run_experiment(
        proposal,
        command=["python3", "-c", f"open({str(marker)!r}, 'w').close()"],
        approved=True,
    )
    assert result.ran is True
    assert marker.exists()


def test_experiment_env_overrides_do_not_leak_into_the_real_process_env():
    proposal = propose_experiment(_hypothesis(), env_overrides={"GHOSTSTATE_TEST_OVERRIDE": "1"})
    run_experiment(proposal, command=["python3", "-c", "pass"], approved=True)
    assert "GHOSTSTATE_TEST_OVERRIDE" not in os.environ
