# Security Policy

## Supported versions

GhostState is pre-1.0. Security fixes land on the latest `0.x` release only —
there is no long-term support branch yet.

| Version | Supported |
|---|---|
| 0.1.x   | :white_check_mark: |
| < 0.1   | :x: |

## Reporting a vulnerability

Please do **not** open a public GitHub issue for a suspected vulnerability.

Instead, open a private [GitHub Security Advisory](../../security/advisories/new)
on this repository. Include:

- A description of the issue and its potential impact
- Steps to reproduce (a minimal repro is ideal)
- The GhostState version / commit you tested against

We aim to acknowledge reports within 5 business days. Since this is an
early-stage project maintained without a dedicated security team, response
and fix timelines are best-effort, not contractual.

## Scope

In scope: anything in this repository, including the redaction policy
(`ghoststate/redaction.py`), the snapshot store's path handling
(`ghoststate/storage.py`), and the experiment engine's subprocess execution
(`ghoststate/experiment.py`) — see `docs/THREAT_MODEL.md` for the full threat
model these were designed against.

Out of scope: vulnerabilities in third-party dependencies (report those
upstream), and social-engineering / physical-access scenarios.

## Coordinated disclosure

We'll credit reporters (unless you prefer anonymity) in the release notes
once a fix ships. Please give us a reasonable window to ship a fix before any
public disclosure.
