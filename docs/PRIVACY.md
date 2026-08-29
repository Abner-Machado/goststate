# Privacy

GhostState runs entirely on your own machine. There is no telemetry, no
phone-home, no analytics, and no network call GhostState makes on its own
initiative beyond the local-only probes described below.

## What GhostState collects

- **System:** OS name/release/version, kernel release (Linux), CPU
  architecture and core count, memory/swap totals, root filesystem type and
  size, resource limits (open file descriptors, max processes), Linux distro
  id/version if `/etc/os-release` exists.
- **Runtime:** the Python interpreter's own version/implementation/path, plus
  `--version` output for `node`, `java`, `go`, `dotnet`, `ruby`, `php` *if*
  found on `PATH` (never guessed if absent).
- **Dependencies:** installed Python package names and versions via
  `importlib.metadata` (stdlib, no subprocess, no network). Other ecosystems
  are explicitly reported `not_supported_in_v0.1`.
- **Network:** whether GhostState's own process can bind an IPv4/IPv6
  loopback socket, and whether `localhost` resolves via A/AAAA records —
  all fully local, no packets leave the machine.
- **Containers:** whether `/.dockerenv` exists, `KUBERNETES_SERVICE_HOST` is
  set, or `/proc/1/cgroup` / `/proc/self/cgroup` mention a known container
  runtime, plus a truncated (12-char) container id if derivable.
- **Git:** the current commit hash, branch name, dirty/clean state, and count
  of changed files in whatever `--repo-path` you point it at (default: the
  current directory). **Never** file contents or diffs.
- **Configuration:** the *names* of every environment variable and whether
  each is `PRESENT` or `ABSENT`. See "What GhostState never collects" below —
  this is presence only.

## What GhostState never collects

- Environment variable **values**, under any name, matching any pattern or
  not (see `ghoststate/redaction.py` and `docs/THREAT_MODEL.md#1-secret-leakage-via-collected-snapshots`)
- Secrets, API keys, tokens, passwords, cookies, session ids, private keys
- The contents of `.env` files or any other file
- Source code content, diffs, or commit messages beyond the commit hash/branch name
- Database contents or connection payloads
- Personal data of any kind
- Arbitrary files from your filesystem

## What leaves the machine

Nothing, by default. GhostState v0.1.0 has no network client code that talks
to any GhostState-operated service — there is no such service. The only
network activity anywhere in the codebase is local loopback binds and local
DNS resolution (`ghoststate/collectors/network.py`), used purely as
diagnostic probes of the local machine's own capability.

If you later use `ghoststate export` to send a snapshot to a teammate, a
ticket, or a support channel, that is a deliberate action *you* take on
already-redacted data — GhostState does not do this automatically, and the
export is exactly what `ghoststate export --id <id>` prints, nothing more.

## How to inspect what was collected

Every snapshot is a plain JSON file under `.ghoststate/snapshots/<id>.json`
in whatever directory you ran `ghoststate capture` from. Read it directly, or
run:

```bash
ghoststate export --id <execution_id>
```

## How to delete data

Snapshots are plain files with no external references — delete the
`.ghoststate/` directory (or individual files under
`.ghoststate/snapshots/`) and they are gone. GhostState keeps no other
state anywhere on the machine (no daemon, no system-wide database, no
registry entries).

## How to disable collectors

There is no partial-disable flag in v0.1.0 (tracked as a roadmap item — see
`docs/ARCHITECTURE.md#roadmap`); the honest current answer is: don't run
`ghoststate capture` in a directory/environment you don't want inspected.
Every collector's source is short and readable —
[`ghoststate/collectors/`](../ghoststate/collectors/) — specifically so you
don't have to take this document's word for what it does.
