# Threat model

## Assets to protect

1. Secrets that might exist in the environment GhostState inspects (API keys,
   tokens, passwords, database URLs, private keys).
2. The integrity of the local filesystem GhostState runs on (no path
   traversal, no arbitrary file read/write outside its own store).
3. The integrity of GhostState's conclusions (no fabricated evidence, no
   false claim of "confirmed" causality).
4. The system GhostState investigates (no destructive action without
   explicit, per-experiment consent).

## Non-goals

GhostState is not, and will not become, an offensive security tool. It does
not scan networks, does not brute-force anything, does not attempt to access
systems it wasn't pointed at, and does not perform any action requiring
elevated privileges by default.

## Attack surface and mitigations

### 1. Secret leakage via collected snapshots

**Threat:** An environment variable, once collected, ends up readable in a
snapshot file, in `ghoststate export` output, or in a bug report someone
pastes into an issue tracker.

**Mitigation:** `ghoststate/redaction.py` is the single choke point every
environment variable passes through. `redact_env()` returns only
`PRESENT`/`ABSENT` per variable — the raw value is never assigned to any
variable that could reach the returned structure, regardless of whether a
secret pattern matches. Pattern matching (`is_sensitive_name`,
`is_sensitive_value`) exists only to compute an internal `sensitive` flag;
even a variable that matches no known secret pattern still never has its
*value* surface, because the policy is "collect metadata," full stop — not
"collect values except known-bad ones."

**Verified by:** `tests/security/test_secret_leakage.py` — asserts realistic
secret values (Stripe keys, AWS keys, GitHub tokens, JWTs, an SSH private
key, and a secret-shaped value under a deliberately innocuous variable name)
never appear in the collector output or in a full `Snapshot.to_json()`
export. Also verified live against this project's own real VPS environment
during development (`ghoststate export` against a live session correctly
redacted a real `AWS_SECRET_ACCESS_KEY` down to `"PRESENT"`).

### 2. Path traversal via execution id

**Threat:** `ghoststate export --id ../../../../etc/passwd` (or a similar
payload passed to `compare`/`investigate`/`experiment`) is used to read or
write outside the snapshot store.

**Mitigation:** `SnapshotStore._path_for()` validates every execution id
against `^[a-f0-9]{4,64}$` before building any path, and raises
`InvalidExecutionId` otherwise. Ids are generated internally via
`secrets.token_hex()`, so a legitimate id can never fail this check; only an
attacker-supplied id can.

**Verified by:** `tests/security/test_path_traversal.py`, parametrized over
`../../../../etc/passwd`, Windows-style traversal, absolute paths, null-ish
edge cases, and a shell-injection-shaped payload (`a;rm -rf /`) — the last of
these matters because ids are never interpolated into a shell string
anywhere in the codebase (see #3).

### 3. Command injection / unsafe subprocess execution

**Threat:** GhostState's `runtime`/`git` probes, or the experiment engine,
execute a command in a way that lets attacker-controlled data escape into a
shell.

**Mitigation:** Every `subprocess.run()` call in the codebase passes an
**argv list**, never `shell=True` with a concatenated string. The one place
GhostState runs a command an operator supplies (`ghoststate experiment
--command "..."`) parses it with `shlex.split()` (not `str.split()`, which
was an early bug — see "Bugs found by the internal red team" below) and
still passes a list to `subprocess.run`, never a shell string.

**Verified by:** `tests/security/test_experiment_safety.py`,
`tests/security/test_malformed_input.py`.

### 4. Unauthorized/unsafe experiment execution

**Threat:** GhostState mutates a real system without the operator's
knowledge or consent.

**Mitigation:** `experiment.run_experiment()` takes an `approved: bool`
parameter; the CLI only ever passes `True` when `--yes` was explicitly
given. Without it, the CLI prints the proposal and stops. Env var overrides
used by an experiment are applied to a **copy** of `os.environ` for the
subprocess only — the real process environment is never mutated. GhostState
does not, in v0.1.0, mutate kernel/network/container state directly at all
(see `docs/ARCHITECTURE.md#roadmap`).

**Verified by:** `tests/security/test_experiment_safety.py::test_experiment_does_not_run_without_approval`
and `::test_experiment_env_overrides_do_not_leak_into_the_real_process_env`.

### 5. False causality

**Threat:** GhostState's output is read as proof of a root cause when it is
actually a correlation — worse, an unrelated confounding variable (e.g. a
git commit hash, which necessarily differs across almost any two separate
runs) could be mistaken for "the" cause.

**Mitigation:** see `docs/ARCHITECTURE.md#epistemic-language--false-causality`.
Confidence is capped below 100%, language never asserts certainty from
correlation alone, and "insufficient evidence" is a first-class, tested
outcome rather than something the system tries to paper over.

**Residual risk:** this is fundamentally not eliminable by any tool in this
category, GhostState included. It is documented, not hidden — see the
README's "What GhostState cannot know" section.

### 6. Malformed / corrupted snapshot data

**Threat:** A hand-edited or corrupted snapshot file crashes GhostState with
an unhandled exception (poor UX) or, worse, is silently accepted and produces
a misleading diff.

**Mitigation:** `SnapshotStore.load()` catches JSON decode errors and
schema-shape errors, raising a distinct `SnapshotCorrupted` exception the CLI
turns into a clean `error: ...` message and non-zero exit — never a raw
traceback. `Snapshot.from_dict()` validates the top-level shape is a dict
before proceeding.

**Verified by:** `tests/security/test_malformed_input.py`.

## Bugs found by the internal red team (kept, not hidden)

Per the project's own review discipline, here is what an adversarial pass
over this codebase actually found before release, not just what it was
designed to prevent:

1. **Misleading label:** the demo's console output originally read `"MEDIUM
   relevance candidate: git"` when it meant *confidence*, not the underlying
   property's *relevance* (which was actually `HIGH`) — exactly the kind of
   "dashboard shows a different conclusion than the evidence" failure this
   threat model is meant to prevent. Fixed; the label now reads `"MEDIUM
   confidence candidate"`.
2. **Naive command parsing:** `ghoststate experiment --command "..."` used
   `str.split()`, which breaks quoted arguments (e.g. a command containing a
   quoted string with spaces). Replaced with `shlex.split()`. Regression test
   in `tests/security/test_malformed_input.py`.
3. **Unhandled crash on corrupted snapshot data:** a malformed JSON file, or
   valid JSON with the wrong shape (e.g. a bare string instead of an
   object), crashed with a raw `JSONDecodeError`/`AttributeError` traceback
   instead of a clean CLI error. Fixed via `SnapshotCorrupted` (see #6
   above). Regression tests in `tests/security/test_malformed_input.py`.

## Out of scope for this threat model

- Multi-tenant/remote deployment (no such deployment mode exists in v0.1.0)
- Authentication/authorization (no network service exists in v0.1.0)
- Supply-chain security of GhostState's own dependencies beyond what `pip`
  and the pinned `click>=8.1` runtime dependency provide — tracked as a
  roadmap item once the project has a CI pipeline running a dependency
  scanner
