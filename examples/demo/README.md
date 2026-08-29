# GhostState demo

Run it:

```bash
ghoststate demo --yes
```

## What it actually does (nothing here is scripted output)

1. Creates a temporary git repository.
2. Writes `behavior.json` with `{"cache_backend": "valid"}` and commits it.
3. Runs [`target_app.py`](target_app.py) — a standalone script with no
   dependency on the `ghoststate` package — which reads `behavior.json` and
   starts. It succeeds.
4. Captures a real snapshot of the execution environment at that point
   (`ghoststate.capture_snapshot`), labeled `"success"`.
5. Rewrites `behavior.json` to `{"cache_backend": "missing_backend_v2"}` and
   commits again.
6. Runs `target_app.py` again. `missing_backend_v2` isn't an implemented
   backend, so it fails.
7. Captures a second real snapshot, labeled `"failure"`.
8. Runs the real deterministic diff → evidence → investigation pipeline
   over the two real snapshots.
9. With `--yes`, proposes and actually runs a confirming experiment: checks
   `behavior.json` back out to the first commit and re-runs `target_app.py`,
   recording whether the failure disappears.

The only thing "staged" about this demo is that it deliberately creates the
before/after scenario (as the project's own design brief requires for
reproducibility) — every snapshot, diff, and experiment result comes from
the deterministic engine actually running, not from example fixtures.

See [`ghoststate/demo_runner.py`](../../ghoststate/demo_runner.py) for the
full orchestration.
