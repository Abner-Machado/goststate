"""GhostState CLI.

Every command exits non-zero on failure with a message on stderr, and
supports --json where the output is meant to be piped into other tools.
"""

from __future__ import annotations

import json
import shlex
import shutil
import sys

import click

from . import SCHEMA_VERSION, __version__
from .capture import capture_snapshot
from .diff import ChangeStatus, diff_snapshots
from .experiment import propose_experiment, run_experiment
from .investigation import investigate
from .storage import InvalidExecutionId, SnapshotCorrupted, SnapshotNotFound, SnapshotStore

_RELEVANCE_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "NONE": 4}


def _store(store_dir: str) -> SnapshotStore:
    return SnapshotStore(store_dir)


def _die(message: str, code: int = 1) -> None:
    click.echo(click.style(f"error: {message}", fg="red"), err=True)
    sys.exit(code)


@click.group()
@click.version_option(__version__, prog_name="ghoststate")
def main() -> None:
    """GhostState — find the condition that made your software break."""


@main.command()
@click.option("--store-dir", default=".ghoststate", show_default=True)
def init(store_dir: str) -> None:
    """Initialize the local snapshot store in the current directory."""
    store = _store(store_dir)
    store.init()
    click.echo(f"Initialized GhostState store at {store.base_dir}/ (schema v{SCHEMA_VERSION})")


@main.command()
@click.option("--label", default="", help="Free-form label, e.g. 'success' or 'failure'.")
@click.option("--repo-path", default=".", help="Path to a git repository to fingerprint.")
@click.option("--store-dir", default=".ghoststate", show_default=True)
@click.option("--json", "as_json", is_flag=True, help="Print the captured snapshot as JSON.")
def capture(label: str, repo_path: str, store_dir: str, as_json: bool) -> None:
    """Capture a snapshot of the current execution environment."""
    snapshot = capture_snapshot(label=label, repo_path=repo_path)
    store = _store(store_dir)
    path = store.save(snapshot)

    if as_json:
        click.echo(snapshot.to_json())
        return

    click.echo(f"Captured execution #{snapshot.execution_id} ({label or 'unlabeled'})")
    click.echo(f"  saved to {path}")
    if snapshot.collector_warnings:
        for warning in snapshot.collector_warnings:
            click.echo(click.style(f"  warning: {warning}", fg="yellow"))


@main.command()
@click.option("--before", required=True, help="Execution id captured earlier.")
@click.option("--after", required=True, help="Execution id captured later / at failure time.")
@click.option("--store-dir", default=".ghoststate", show_default=True)
@click.option("--json", "as_json", is_flag=True)
def compare(before: str, after: str, store_dir: str, as_json: bool) -> None:
    """Show the deterministic diff between two snapshots."""
    store = _store(store_dir)
    try:
        before_snap = store.load(before)
        after_snap = store.load(after)
    except (SnapshotNotFound, InvalidExecutionId, SnapshotCorrupted) as exc:
        _die(str(exc))
        return

    result = diff_snapshots(before_snap, after_snap)

    if as_json:
        click.echo(json.dumps([d.to_dict() for d in result.diffs], indent=2, sort_keys=True))
        return

    changed = sorted(result.changed(), key=lambda d: _RELEVANCE_ORDER[d.relevance.value])
    counts = result.summary_counts()
    click.echo(
        f"{counts[ChangeStatus.UNCHANGED.value]} properties unchanged. "
        f"{len(changed)} properties changed."
    )
    for d in changed:
        click.echo(f"  [{d.relevance.value:<8}] {d.status.value:<9} {d.path}: {d.before!r} -> {d.after!r}")


@main.command(name="investigate")
@click.option("--before", required=True)
@click.option("--after", required=True)
@click.option("--store-dir", default=".ghoststate", show_default=True)
@click.option("--json", "as_json", is_flag=True)
def investigate_cmd(before: str, after: str, store_dir: str, as_json: bool) -> None:
    """Rank candidate causes for a failure between two snapshots."""
    store = _store(store_dir)
    try:
        before_snap = store.load(before)
        after_snap = store.load(after)
    except (SnapshotNotFound, InvalidExecutionId, SnapshotCorrupted) as exc:
        _die(str(exc))
        return

    report = investigate(before_snap, after_snap)

    if as_json:
        click.echo(json.dumps(report.to_dict(), indent=2, sort_keys=True))
        return

    click.echo("GhostState Investigation")
    click.echo(f"Comparing execution #{before} -> #{after}")
    click.echo(report.note)
    if not report.sufficient_evidence:
        click.echo(click.style("Insufficient evidence.", fg="yellow", bold=True))
    for h in report.hypotheses:
        click.echo("")
        click.echo(click.style(f"Hypothesis: {h.summary}", bold=True))
        click.echo(f"  {h.language} the failure (confidence: {h.confidence_bucket}, {h.confidence_percent}% heuristic)")
        for fact in h.evidence:
            click.echo(f"  + [{fact.relevance.value}] {fact.status.value} {fact.path}")


@main.command()
@click.option("--before", required=True)
@click.option("--after", required=True)
@click.option("--hypothesis", "hypothesis_id", required=True, help="Hypothesis id, e.g. hyp-network.")
@click.option("--command", "command_str", required=True, help="Shell command to re-run for the experiment.")
@click.option("--expect-success/--expect-failure", default=True)
@click.option("--yes", is_flag=True, help="Approve running the experiment (required to actually execute it).")
@click.option("--store-dir", default=".ghoststate", show_default=True)
@click.option("--json", "as_json", is_flag=True)
def experiment(
    before: str,
    after: str,
    hypothesis_id: str,
    command_str: str,
    expect_success: bool,
    yes: bool,
    store_dir: str,
    as_json: bool,
) -> None:
    """Propose (and, with --yes, run) a safe experiment for one hypothesis."""
    store = _store(store_dir)
    try:
        before_snap = store.load(before)
        after_snap = store.load(after)
    except (SnapshotNotFound, InvalidExecutionId, SnapshotCorrupted) as exc:
        _die(str(exc))
        return

    report = investigate(before_snap, after_snap)
    match = next((h for h in report.hypotheses if h.id == hypothesis_id), None)
    if match is None:
        available = ", ".join(h.id for h in report.hypotheses) or "(none)"
        _die(f"unknown hypothesis id {hypothesis_id!r}. Available: {available}")
        return

    proposal = propose_experiment(match)

    if not yes:
        if as_json:
            click.echo(json.dumps({"ran": False, "proposal": proposal.to_dict()}, indent=2))
        else:
            click.echo(f"Suggested experiment for {hypothesis_id}:")
            click.echo(f"  {proposal.description}")
            click.echo(f"  risk: {proposal.risk}  requires_approval: {proposal.requires_approval}")
            click.echo("Re-run with --yes to actually execute this experiment.")
        return

    result = run_experiment(
        proposal,
        command=shlex.split(command_str),
        approved=True,
        expected_to_succeed=expect_success,
    )

    if as_json:
        click.echo(json.dumps(result.to_dict(), indent=2))
        return

    click.echo(f"Ran experiment for {hypothesis_id}: {proposal.description}")
    click.echo(f"Result: {result.verdict.value}")
    if result.detail:
        click.echo(f"  detail: {result.detail}")


@main.command()
@click.option("--id", "execution_id", required=True)
@click.option("--out", type=click.File("w"), default="-")
@click.option("--store-dir", default=".ghoststate", show_default=True)
def export(execution_id: str, out, store_dir: str) -> None:
    """Export a raw snapshot as JSON."""
    store = _store(store_dir)
    try:
        snapshot = store.load(execution_id)
    except (SnapshotNotFound, InvalidExecutionId, SnapshotCorrupted) as exc:
        _die(str(exc))
        return
    out.write(snapshot.to_json())
    out.write("\n")


@main.command()
@click.option("--before", required=True)
@click.option("--after", required=True)
@click.option("--store-dir", default=".ghoststate", show_default=True)
def explain(before: str, after: str, store_dir: str) -> None:
    """Human-readable narrative of the investigation (deterministic, no LLM)."""
    store = _store(store_dir)
    try:
        before_snap = store.load(before)
        after_snap = store.load(after)
    except (SnapshotNotFound, InvalidExecutionId, SnapshotCorrupted) as exc:
        _die(str(exc))
        return

    report = investigate(before_snap, after_snap)
    click.echo(f'"{before_snap.label or before}" -> "{after_snap.label or after}"')
    click.echo(report.note)
    if report.hypotheses:
        top = report.hypotheses[0]
        click.echo(
            f"Most likely cause: {top.section} ({top.language}, confidence {top.confidence_bucket})."
        )
        click.echo("What GhostState cannot know: whether this is the only contributing factor,")
        click.echo("or whether an unobserved property (one no collector inspects) is the real cause.")
    else:
        click.echo("GhostState found no property reaching MEDIUM relevance or above.")


@main.command()
@click.option("--store-dir", default=".ghoststate", show_default=True)
def doctor(store_dir: str) -> None:
    """Diagnose GhostState's own environment: permissions, deps, storage, git, network."""
    import socket

    checks: list[tuple[str, bool, str]] = []

    checks.append(("python >= 3.9", sys.version_info >= (3, 9), sys.version.split()[0]))

    store = _store(store_dir)
    try:
        store.init()
        writable = True
    except OSError as exc:
        writable = False
        checks.append(("store writable", False, str(exc)))
    else:
        checks.append(("store writable", writable, str(store.base_dir)))

    checks.append(("git available", shutil.which("git") is not None, shutil.which("git") or "not found"))

    try:
        socket.getaddrinfo("localhost", None)
        dns_ok = True
    except OSError:
        dns_ok = False
    checks.append(("local DNS resolution", dns_ok, "localhost resolves" if dns_ok else "failed"))

    all_ok = True
    for name, ok, detail in checks:
        symbol = click.style("OK", fg="green") if ok else click.style("FAIL", fg="red")
        click.echo(f"[{symbol}] {name}: {detail}")
        all_ok = all_ok and ok

    if not all_ok:
        sys.exit(1)


@main.command()
@click.option("--store-dir", default=".ghoststate/demo", show_default=True)
@click.option("--yes", is_flag=True, help="Also run the confirming experiment (simulation, no --yes = proposal only).")
def demo(store_dir: str, yes: bool) -> None:
    """Run the end-to-end reproducible demo: SUCCESS -> FAILURE -> investigation -> experiment."""
    from .demo_runner import DemoSetupError, run_demo

    try:
        run_demo(store_dir=store_dir, run_experiment_too=yes)
    except DemoSetupError as exc:
        _die(str(exc))


if __name__ == "__main__":
    main()
