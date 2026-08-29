"""Experiment Engine.

GhostState never mutates a real system on its own. This module only:
  1. Proposes a safe, minimal experiment for a given hypothesis.
  2. Executes it ONLY when the caller passes `approved=True` explicitly
     (the CLI maps this to an interactive confirmation or an explicit
     `--yes` flag — see cli.py).
  3. Runs the experiment as a *subprocess* the caller supplies, with a
     documented environment override — it never touches system-wide
     network/kernel/container state. Toggling real IPv6/kernel/container
     state system-wide is out of scope for v0.1.0 and is not simulated
     as if it were done; see docs/ARCHITECTURE.md#roadmap.

A verdict of SUPPORTS or REFUTES is only ever produced from an experiment
that actually ran. There is no code path that fabricates a result.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from enum import Enum

from .evidence import Hypothesis

_EXPERIMENT_TIMEOUT_SECONDS = 30


class Verdict(str, Enum):
    NOT_RUN = "NOT_RUN"
    SUPPORTS_HYPOTHESIS = "SUPPORTS_HYPOTHESIS"
    REFUTES_HYPOTHESIS = "REFUTES_HYPOTHESIS"
    INCONCLUSIVE = "INCONCLUSIVE"


@dataclass
class ExperimentProposal:
    hypothesis_id: str
    description: str
    env_overrides: dict[str, str]
    risk: str = "LOW"
    requires_approval: bool = True

    def to_dict(self) -> dict:
        return {
            "hypothesis_id": self.hypothesis_id,
            "description": self.description,
            "env_overrides": self.env_overrides,
            "risk": self.risk,
            "requires_approval": self.requires_approval,
        }


@dataclass
class ExperimentResult:
    proposal: ExperimentProposal
    verdict: Verdict
    exit_code: int | None = None
    expected_to_succeed: bool = True
    ran: bool = False
    detail: str = ""

    def to_dict(self) -> dict:
        return {
            "proposal": self.proposal.to_dict(),
            "ran": self.ran,
            "verdict": self.verdict.value,
            "exit_code": self.exit_code,
            "detail": self.detail,
        }


# One template per section this evidence engine can group by. Each template
# describes, in plain language, what reverting that section's most relevant
# change would look like — this is intentionally a fixed, readable table,
# not a generated/inferred plan.
_TEMPLATES: dict[str, str] = {
    "network": "Re-run the target command with the network property reverted to its earlier value.",
    "git": "Re-run the target command against the earlier git commit.",
    "containers": "Re-run the target command outside the container runtime (or with the earlier one).",
    "system": "Re-run the target command with the system property reverted, if the platform allows it.",
    "runtime": "Re-run the target command under the earlier runtime version, if available.",
    "dependencies": "Re-run the target command with the changed dependency pinned to its earlier version.",
    "configuration_metadata": (
        "Re-run the target command with the environment variable reverted to its earlier presence/absence."
    ),
}


def propose_experiment(hypothesis: Hypothesis, env_overrides: dict[str, str] | None = None) -> ExperimentProposal:
    description = _TEMPLATES.get(
        hypothesis.section,
        "Re-run the target command with the top changed property reverted to its earlier value.",
    )
    return ExperimentProposal(
        hypothesis_id=hypothesis.id,
        description=description,
        env_overrides=env_overrides or {},
    )


def run_experiment(
    proposal: ExperimentProposal,
    command: list[str],
    *,
    approved: bool,
    expected_to_succeed: bool = True,
    cwd: str | None = None,
) -> ExperimentResult:
    """Execute `command` as a subprocess with `proposal.env_overrides` applied.

    Never runs without `approved=True`. The environment overrides are
    layered on top of a *copy* of the current process environment — the
    real environment is never mutated.
    """
    if not approved:
        return ExperimentResult(
            proposal=proposal,
            verdict=Verdict.NOT_RUN,
            ran=False,
            detail="Experiment requires explicit approval and was not run.",
        )

    env = dict(os.environ)
    env.update(proposal.env_overrides)

    try:
        result = subprocess.run(
            command,
            env=env,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=_EXPERIMENT_TIMEOUT_SECONDS,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return ExperimentResult(
            proposal=proposal,
            verdict=Verdict.INCONCLUSIVE,
            ran=True,
            detail=f"Experiment command failed to execute: {exc}",
        )

    succeeded = result.returncode == 0
    if succeeded == expected_to_succeed:
        verdict = Verdict.SUPPORTS_HYPOTHESIS
    else:
        verdict = Verdict.REFUTES_HYPOTHESIS

    return ExperimentResult(
        proposal=proposal,
        verdict=verdict,
        exit_code=result.returncode,
        expected_to_succeed=expected_to_succeed,
        ran=True,
        detail=(result.stdout or result.stderr or "").strip()[-500:],
    )
