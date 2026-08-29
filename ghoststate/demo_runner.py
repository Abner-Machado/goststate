"""Drives the reproducible end-to-end demo.

Everything here is real: a real temporary git repository, real
subprocess executions of examples/demo/target_app.py, real snapshots
captured by the real collectors, and a real experiment re-run. Nothing
in this module fabricates a snapshot, a diff, or a verdict — see
section "Demo integrity" in docs/ARCHITECTURE.md.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import click

from .capture import capture_snapshot
from .experiment import propose_experiment, run_experiment
from .investigation import investigate
from .storage import SnapshotStore

_REPO_ROOT = Path(__file__).resolve().parent.parent
_TARGET_APP = _REPO_ROOT / "examples" / "demo" / "target_app.py"


class DemoSetupError(RuntimeError):
    pass


def _git(args: list[str], cwd: Path) -> None:
    result = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, timeout=10, check=False
    )
    if result.returncode != 0:
        raise DemoSetupError(f"git {' '.join(args)} failed: {result.stderr.strip()}")


def _run_target_app(cwd: Path, env_overrides: dict[str, str]) -> subprocess.CompletedProcess:
    import os

    env = dict(os.environ)
    env.update(env_overrides)
    return subprocess.run(
        [sys.executable, str(_TARGET_APP)],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )


def run_demo(store_dir: str = ".ghoststate/demo", run_experiment_too: bool = False) -> None:
    if not _TARGET_APP.exists():
        raise DemoSetupError(
            f"demo target app not found at {_TARGET_APP} — run `ghoststate demo` from a source checkout."
        )

    store = SnapshotStore(store_dir)
    store.init()

    with tempfile.TemporaryDirectory(prefix="ghoststate-demo-") as tmp:
        repo = Path(tmp)
        _git(["init", "-q"], repo)
        _git(["config", "user.email", "demo@ghoststate.local"], repo)
        _git(["config", "user.name", "GhostState Demo"], repo)

        # --- Execution #1: the world that worked ---
        (repo / "behavior.json").write_text(json.dumps({"cache_backend": "valid"}), encoding="utf-8")
        _git(["add", "behavior.json"], repo)
        _git(["commit", "-q", "-m", "v1: valid cache backend"], repo)

        click.echo("Running execution #1 (the world that worked)...")
        result_a = _run_target_app(repo, {"CACHE_WARMED": "1"})
        snapshot_a = capture_snapshot(label="success", repo_path=str(repo), env={"CACHE_WARMED": "1"})
        store.save(snapshot_a)
        click.echo(f"  -> exit code {result_a.returncode}: {(result_a.stdout or result_a.stderr).strip()}")

        # --- Execution #2: the world that broke ---
        (repo / "behavior.json").write_text(
            json.dumps({"cache_backend": "missing_backend_v2"}), encoding="utf-8"
        )
        _git(["add", "behavior.json"], repo)
        _git(["commit", "-q", "-m", "v2: swap cache backend"], repo)

        click.echo("Running execution #2 (the world that broke)...")
        result_b = _run_target_app(repo, {})
        snapshot_b = capture_snapshot(label="failure", repo_path=str(repo), env={})
        store.save(snapshot_b)
        click.echo(f"  -> exit code {result_b.returncode}: {(result_b.stdout or result_b.stderr).strip()}")

        click.echo("")
        click.echo("GhostState Investigation")
        click.echo(f"Comparing execution #{snapshot_a.execution_id} -> #{snapshot_b.execution_id}")

        report = investigate(snapshot_a, snapshot_b)
        counts = report.diff.summary_counts()
        click.echo(f"{counts['UNCHANGED']} properties unchanged. {len(report.diff.changed())} properties changed.")

        if not report.sufficient_evidence:
            click.echo(click.style("Insufficient evidence.", fg="yellow", bold=True))
            return

        for h in report.hypotheses:
            click.echo("")
            click.echo(click.style(f"{h.confidence_bucket} confidence candidate: {h.section}", bold=True))
            click.echo(f"  {h.summary}")
            click.echo(f"  {h.language} the failure ({h.confidence_percent}% heuristic confidence)")

        top = report.hypotheses[0]
        click.echo("")
        click.echo(click.style(f"Candidate cause: {top.section}", bold=True))
        proposal = propose_experiment(top)
        click.echo(f"Recommended experiment: {proposal.description}")

        if not run_experiment_too:
            click.echo("(pass --yes to actually run the confirming experiment)")
            return

        click.echo("")
        click.echo("Running confirming experiment: re-check out execution #1's commit and re-run...")
        _git(["checkout", "-q", "HEAD~1", "--", "behavior.json"], repo)
        exp_result = run_experiment(
            proposal,
            command=[sys.executable, str(_TARGET_APP)],
            approved=True,
            expected_to_succeed=True,
            cwd=str(repo),
        )
        click.echo(f"Result: {exp_result.verdict.value}")
        if exp_result.detail:
            click.echo(f"  detail: {exp_result.detail}")
