# Prior art

Written before any implementation code, per the project's own rule: don't claim
novelty without checking. Sources are cited inline; this is a synthesis of
public documentation and READMEs, not a code-level comparison.

| Project | Problem it solves | How it solves it | Limitation | Overlap with GhostState |
|---|---|---|---|---|
| driftctl, cloud-concierge, Terragrunt | Declared IaC (Terraform) diverges from live cloud resources | Diffs Terraform state against cloud provider APIs | Domain is *declared cloud resources*, not a running process's execution environment | Low — different data layer entirely |
| env-diff, confdiff, config-diff-tool, prodConfigChecker | Config files / env vars diverge between environments | Structural diff of declared config files (JSON/YAML/.env) | Only ever compares *declared files*, never live runtime state (kernel, DNS, filesystem, actually-installed dependency versions); no hypothesis/causality layer | Partial — "env var presence" framing is close, but scope and depth are much smaller |
| ReproZip, Nix, Pixi, CWL/Nextflow | Package an execution environment so it can be reproduced later | Freeze dependencies/environment *before* running | Prospective — requires instrumenting ahead of time; can't do forensics on an incident that already happened on an uninstrumented machine | Philosophical only |
| Chaos Toolkit, LitmusChaos, Gremlin | Test resilience via controlled fault injection | Define a steady-state hypothesis up front, inject a fault, observe | Opposite direction: starts from a *planned, hypothetical* failure, not an *already-observed* one | Vocabulary (hypothesis/experiment/rollback) is close; direction is inverted |
| Delta Debugging (Zeller, 1999) | Isolate the minimal cause of a failure via binary-search bisection | Re-run the program repeatedly, varying inputs/env vars, against a test oracle | Closest academic ancestor — the original paper's flagship example isolates env vars breaking GDB — but requires a repeatable test oracle, has no structured snapshot format, no evidence/confidence language, and never shipped as a usable product | High in principle, ~zero as a usable tool |
| TraceRoot, Deductive AI, Montimage RCA, UpTrain | RCA by correlating logs/traces/code/git history | Correlate application telemetry and commit history | Substrate is *telemetry and code*, not the execution environment (OS/kernel/network/runtime) | Medium in goal ("find root cause"), low in data substrate |
| Honeycomb BubbleUp, Datadog Watchdog | Find which telemetry dimension explains an anomaly | Compare tag distribution of an anomalous data subset vs. the rest of the population, inside a paid SaaS platform | Only sees what the app already emits as telemetry/tags; doesn't capture OS/kernel/DNS/filesystem/container image as native comparison dimensions; requires ongoing paid ingestion | Philosophically closest ("compare the world that worked vs. the world that broke"), but at a completely different layer and distribution model |

## Where the gap actually is

Nothing above treats the **execution-environment layer** — OS/kernel, runtime,
network/DNS, container, filesystem, git state — as a structured, versioned,
comparable artifact, captured forensically (after the fact, without prior
instrumentation), locally, with explicit epistemic discipline about
correlation vs. causation. Each category stops exactly where GhostState
starts:

- **driftctl** stops at "declared cloud resource"
- **env-diff/confdiff** stop at "declared config file"
- **ReproZip/Nix** require instrumentation *before* the failure happens
- **Chaos Toolkit** injects a failure; it doesn't investigate one that already occurred
- **Delta debugging** is the right technique but never became a usable product, and needs a re-runnable oracle — it doesn't work for "this happened in production yesterday and I can't re-run it 200 times"
- **BubbleUp/Watchdog** do exactly this comparison, but only over application telemetry inside a paid SaaS

**GhostState's thesis:** apply the "compare the world that worked to the world
that broke" idea (BubbleUp/Watchdog) plus delta debugging's bisection
discipline to the **execution-environment layer** (not declared config, not
cloud resources, not app telemetry), with a deterministic core independent of
any LLM, strict epistemic language, and a single-hypothesis,
consent-gated experiment engine — as a local-first, redaction-by-default CLI,
not a SaaS. That combination, not any single ingredient, is the differentiation.

## Sources consulted

- env0, "8 Terraform Drift Detection Tools Enterprise Teams Actually Use in 2026"
- InfoQ, "Infrastructure Drift: driftctl"
- jacebrowning/env-diff and esperanza-volkov/confdiff (GitHub)
- ReproZip (reprozip.org), Pixi (SciPy Proceedings)
- Chaos Toolkit (chaostoolkit.org), LitmusChaos (litmuschaos.io)
- Wikipedia, "Delta debugging"
- traceroot-ai/traceroot (GitHub), Montimage/rca (GitHub)
- Honeycomb, "Identify Outliers With BubbleUp"; Datadog, "Automated root cause analysis with Watchdog RCA"
