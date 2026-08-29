# Contributing to GhostState

Thanks for considering a contribution. This project favors small, well-tested
changes over large speculative ones — see the "Golden rule" in
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the design philosophy that
guides review.

## Getting set up

```bash
git clone <this-repo-url> ghoststate
cd ghoststate
pip install -e ".[dev]"
```

## Before opening a PR

```bash
python -m pytest -q                 # all tests must pass
python -m ruff check .              # lint must be clean
python -m mypy ghoststate           # type check must be clean
python -m ghoststate.cli demo --yes # the demo must still work end to end
```

None of these are optional gates dressed up as suggestions — CI runs exactly
these commands (see `.github/workflows/ci.yml`).

## What we look for in a change

- **Tests.** A bug fix needs a regression test in the matching `tests/unit/`,
  `tests/integration/`, or `tests/security/` directory. A new collector or
  CLI command needs both unit coverage and an integration test exercising it
  through `click.testing.CliRunner`.
- **Determinism where it matters.** Anything in `ghoststate/diff.py`,
  `ghoststate/evidence.py`, or `ghoststate/investigation.py` must stay pure
  and deterministic — no network calls, no LLM calls, no wall-clock-dependent
  behavior in the comparison logic itself.
- **Honest epistemic language.** If you touch `evidence.py` or
  `investigation.py`, keep the confidence formula documented in
  `docs/ARCHITECTURE.md#confidence` in sync with the code, and never add a
  code path that can produce "confirmed" language without a real executed
  experiment behind it.
- **Security-relevant changes** (anything touching `redaction.py`,
  `storage.py`'s id handling, or `experiment.py`'s subprocess execution)
  should come with a test under `tests/security/`, and ideally a note in
  `docs/THREAT_MODEL.md` if you're changing the threat surface.
- **Small diffs.** Prefer several small, reviewable PRs over one large one.

## New collectors

A collector is a function `() -> dict[str, Any]` that never raises (see
`ghoststate/collectors/__init__.py`). If you're adding support for a new
runtime, dependency ecosystem, or platform, follow the pattern in
`ghoststate/collectors/runtime.py`: probe for it explicitly, and report
`"not_detected"` rather than guessing when it isn't present.

## Reporting bugs / requesting features

Open a GitHub issue. For anything security-sensitive, see
[`SECURITY.md`](SECURITY.md) instead — please don't file those as public
issues.

## Code of conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md).
