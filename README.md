# GhostState

**"It worked yesterday."**

GhostState helps you discover what changed.

Git shows how your code changed. Observability shows what happened. Neither tells
you what changed *in the world your software runs in* — the kernel, the network
stack, the container, the dependency versions, the commit that got checked out —
between the run that worked and the run that didn't.

GhostState captures a structured, versioned snapshot of an execution environment,
diffs two of them deterministically, and turns the differences into ranked,
evidence-backed hypotheses — never a guess dressed up as a diagnosis.

```
$ ghoststate demo --yes

Running execution #1 (the world that worked)...
  -> exit code 0: STARTED OK: cache_backend=valid
Running execution #2 (the world that broke)...
  -> exit code 1: STARTUP FAILED: unsupported cache_backend 'missing_backend_v2'

GhostState Investigation
Comparing execution #94be62aa -> #c3ef5e3b
103 properties unchanged. 4 properties changed.

MEDIUM confidence candidate: git
  git changed (git.commit: '614cd573...' -> '0ab10360...')
  correlated with the failure (41% heuristic confidence)

LOW confidence candidate: configuration_metadata
  configuration_metadata changed (CACHE_WARMED: 'PRESENT' -> None)
  consistent with the failure (33% heuristic confidence)

Candidate cause: git
Recommended experiment: Re-run the target command against the earlier git commit.

Running confirming experiment: re-check out execution #1's commit and re-run...
Result: SUPPORTS_HYPOTHESIS
  detail: STARTED OK: cache_backend=valid
```

That entire transcript is real. `ghoststate demo` creates a temporary git
repository, runs a real toy application twice, captures two real snapshots with
GhostState's own collectors, and runs a real confirming experiment — nothing in
it is scripted output. See [`examples/demo/`](examples/demo/) for exactly what
it does, and run it yourself; there's nothing up the sleeve.

## Why this isn't another drift/diff/RCA tool

Before writing a line of code we mapped the ecosystem — driftctl and infra-drift
tools, env/config diff tools, reproducibility packagers (Nix, ReproZip), chaos
engineering tooling, RCA/AI-agent debugging tools, and Honeycomb BubbleUp /
Datadog Watchdog. Every one of them stops at a different layer than GhostState:
IaC-declared resources, declared config files, prospective environment packaging,
injected faults, or application telemetry tags. None of them treat the
**execution environment itself** — OS/kernel, runtime, network/DNS, container,
filesystem, git state — as a structured, comparable, forensic artifact. The full
matrix and reasoning is in [`docs/PRIOR_ART.md`](docs/PRIOR_ART.md).

## How it works

1. **`ghoststate capture`** — a collector observes the current OS, runtime,
   dependencies, network capability, container status, and git state, and
   writes a versioned JSON snapshot. Environment variables are collected as
   `PRESENT`/`ABSENT` only — never their values. See
   [Security & privacy](#security--privacy).
2. **`ghoststate compare`** — a deterministic diff engine (no LLM, no network,
   no randomness) classifies every property as `UNCHANGED` / `CHANGED` /
   `ADDED` / `REMOVED`, and tags each change with a documented relevance tier
   (`LOW` / `MEDIUM` / `HIGH` / `CRITICAL`).
3. **`ghoststate investigate`** — changed properties are grouped into
   hypotheses, each backed by concrete evidence and a heuristic confidence
   score (capped below 100% — correlation is never presented as certainty).
   If nothing reaches `MEDIUM` relevance, GhostState says **"Insufficient
   evidence"** instead of inventing a cause.
4. **`ghoststate experiment`** — propose (and, only with `--yes`, run) a
   minimal, consent-gated experiment that re-runs your command with one
   property reverted. A hypothesis only ever becomes *"confirmed by
   experiment"* after a real experiment records that verdict.

The deterministic core (`ghoststate.diff`, `ghoststate.evidence`,
`ghoststate.investigation`) has **no dependency on any LLM** and works fully
offline. See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Install & quickstart

```bash
git clone <this-repo-url> ghoststate
cd ghoststate
pip install -e .

ghoststate demo --yes         # the reproducible end-to-end demo above
ghoststate doctor             # sanity-check your own environment

ghoststate init
ghoststate capture --label success
# ... your deploy / change happens here ...
ghoststate capture --label failure
ghoststate investigate --before <id1> --after <id2>
```

Requires Python >= 3.9 and `git` on `PATH` for the git collector (optional —
GhostState degrades gracefully without it).

## What GhostState collects — and never collects

**Collects (metadata only):** OS/kernel/architecture, CPU count, memory and
disk totals, filesystem type, resource limits, detected runtime versions
(Python fully; Node/Java/Go/.NET probed via `--version`, never guessed),
installed Python package names+versions, local IPv4/IPv6 loopback bind and
resolution capability, container runtime detection, git commit/branch/dirty
state, and environment variable **presence** (`PRESENT`/`ABSENT`).

**Never collects:** environment variable *values*, secrets, API keys, tokens,
passwords, cookies, `.env` contents, private keys, source code content,
database contents, or arbitrary files. Every environment variable goes
through [`ghoststate/redaction.py`](ghoststate/redaction.py) — see
[`docs/PRIVACY.md`](docs/PRIVACY.md) for the exact policy and how to inspect
or delete anything GhostState has stored.

**Network:** only loopback binds and local resolver calls. GhostState never
scans, never contacts third-party hosts, and is not — and will not become —
an offensive tool.

## What GhostState cannot know

If two snapshots are identical, or the only differences are `LOW` relevance,
GhostState reports **insufficient evidence** rather than manufacturing a
cause. A ranked hypothesis is a documented, capped-confidence *correlation*,
not proof — the only way language escalates to "confirmed" is a real
experiment you explicitly approved. See
[`docs/THREAT_MODEL.md`](docs/THREAT_MODEL.md#false-causality) for how this is
enforced in code and tested.

## Status

**v0.1.0 — MVP.** The deterministic core (snapshot, diff, evidence,
investigation, experiment engine) and CLI are implemented and tested end to
end, including the reproducible demo. Deliberately **not** in this release,
and tracked as roadmap rather than silently missing:

- Dashboard / web UI (CLI + JSON export only for now)
- LLM-assisted narrative explanation (the core works, and is tested to work,
  without any LLM — see [`docs/ARCHITECTURE.md#llm`](docs/ARCHITECTURE.md#the-llms-role))
- Dependency collection beyond Python (Node/Java/Go/.NET report
  `not_supported_in_v0.1`, honestly, instead of guessing)
- Live system mutation for experiments (e.g. actually toggling IPv6) — the
  experiment engine re-runs a command you supply with controlled env
  overrides; it does not mutate kernel/network state

## Security

See [`SECURITY.md`](SECURITY.md) for how to report a vulnerability, and
[`docs/THREAT_MODEL.md`](docs/THREAT_MODEL.md) for the full threat model,
including the internal red-team pass this codebase went through before
release (three real bugs found and fixed — that history is in
`docs/THREAT_MODEL.md`, not swept away).

## License

Apache License 2.0 — see [`LICENSE`](LICENSE). Chosen because it's a standard
permissive OSS license that includes an explicit patent grant, appropriate for
a tool teams will run against their own infrastructure and potentially build
on top of.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md).
