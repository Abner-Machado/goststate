# Architecture

## Layering

```
collectors/   -> capture.py -> Snapshot (schema.py)
                                    |
                          diff.py (deterministic)
                                    |
                        evidence.py (deterministic)
                                    |
                     investigation.py (deterministic)
                                    |
                      experiment.py (consent-gated subprocess)
                                    |
                   cli.py  /  demo_runner.py  (presentation)
```

Every layer up to and including `investigation.py` is pure, deterministic
Python with **no network access and no dependency on any LLM**. This is not
an implementation detail — it's the property that makes GhostState's outputs
testable and trustworthy: `tests/unit/` exercises the whole pipeline (diff →
evidence → investigation) without a subprocess, a file, or a network call in
sight, and the results are exactly reproducible.

## Why local-only in v0.1.0

The initial design sketch considered a distributed `agent/` + `api/` +
`storage/` (database-backed) architecture. It was cut for the MVP:
GhostState's core value — comparing two snapshots — does not require a
running daemon, a database, or a network protocol. A local collector writing
JSON files under `.ghoststate/` is the simplest thing that supports the full
CLI surface (`capture`, `compare`, `investigate`, `experiment`, `explain`,
`export`, `doctor`, `demo`) and is trivial to audit: `ghoststate/storage.py`
is ~70 lines, no ORM, no schema migrations, no network attack surface. A
remote agent/API is a legitimate future milestone (e.g. capturing from CI
runners into a shared store) but would roughly triple the auditable surface
for zero v0.1.0 user value — cut per the brief's own rule: "se um componente
não for necessário, não implemente."

## Schema versioning

`Snapshot.schema_version` (currently `"1.0"`) is checked by
`is_schema_compatible()` before any diff runs. Snapshots differing in major
version refuse to compare (`investigation.py` returns
`sufficient_evidence=False` with an explicit note) rather than silently
producing a diff between two structurally incompatible documents. Minor
version bumps must stay purely additive (existing fields never change
meaning) so v1.x snapshots always remain mutually comparable.

## The relevance model

`ghoststate/diff.py` classifies every property path against
`_RELEVANCE_RULES`, an ordered, first-match-wins table mapping path patterns
to `LOW`/`MEDIUM`/`HIGH`/`CRITICAL`. This table is the entire "why does this
matter" model. It is deliberately data, not a hidden heuristic or a model
inference — anyone auditing GhostState's conclusions can read the exact rule
that assigned a given property its relevance, and extend it.

## Confidence

`ghoststate/evidence.py::_score_group` computes a weighted sum over a
hypothesis's supporting facts (`LOW=1, MEDIUM=3, HIGH=7, CRITICAL=12`, plus a
+5 correlation bonus when 2+ HIGH-or-above facts co-occur), then
`_score_to_percent` maps that score through a saturating curve
(`100 * score / (score + 10)`, capped at 96%) so:

- a single LOW fact scores low
- a handful of correlated HIGH/CRITICAL facts can approach, but never reach,
  certainty

This is a **documented heuristic**, not a statistical estimate — the CLI and
JSON output both carry a `confidence_basis` string saying exactly that. The
brief this project follows is explicit that inventing an unfounded percentage
is worse than not giving one; the formula above is the "foundation," in plain
sight, specifically so it can't be accused of being invented after the fact.

## Epistemic language / false causality

A `Hypothesis.language` defaults to `suggests` / `consistent with` /
`correlated with` / `strongly correlated with`, scaled by the evidence's
relevance tier — never `confirmed`, `caused by`, or `proves`. The only
function that can change a hypothesis's language to `"confirmed by
experiment"` is `evidence.mark_experiment_result(hypothesis, supports=True)`,
and the only caller of that function is a real, executed
`experiment.run_experiment(...)` result. There is no code path from
diff/evidence data alone to "confirmed" language — see
`tests/unit/test_evidence.py::test_language_defaults_to_proposed_never_confirmed`
and `::test_mark_experiment_result_refuted_never_says_confirmed`.

This does not eliminate the risk of a **confounding variable**: e.g. a git
commit hash differs between any two runs that aren't on the exact same
commit, even when the meaningful change is elsewhere (a dependency, an env
var) and the commit is a red herring. GhostState mitigates this by (a) never
asserting more than "correlated," (b) capping confidence below 100%, and (c)
explicitly telling the user, via `ghoststate explain`, "What GhostState
cannot know: whether this is the only contributing factor." It does not
eliminate the risk, because no automated tool honestly can — see
`docs/THREAT_MODEL.md`.

## The LLM's role

There isn't one in v0.1.0's core, and the CLI runs and is fully tested
without any API key or network access — see every test in `tests/` (all 70
pass offline). This is a deliberate MVP cut, not an oversight: an
LLM-generated narrative on top of the deterministic investigation report
(`ghoststate explain --llm`, roadmap) is additive UX, not something the
diff/evidence/investigation core should ever depend on for correctness. If
it's added later, it must (a) receive only the already-redacted,
already-computed `InvestigationReport`, never raw environment values, and
(b) never be allowed to alter the underlying confidence score or evidence
list — only narrate it.

## Roadmap (explicitly out of scope for v0.1.0)

- Dashboard / web UI
- Remote/distributed collector + API + shared storage
- Dependency collection for Node/Java/Go/.NET (currently `not_supported_in_v0.1`)
- Cross-section correlation in the evidence engine (today: one hypothesis per
  top-level snapshot section, by design — see `evidence.py::build_hypotheses`)
- Live system-level experiment execution (actually toggling kernel/network
  state) — today's experiment engine re-runs a supplied command with
  controlled env var overrides only
- `ghoststate explain --llm`
