# VX–VLNS Continuous Innovation & Repository Assurance

**Status:** operational contract for implementation and review; not a claim that all external adapters are connected.
**Applies to:** VAIXLNS-unified, VX, VLNS, Ω Reality Forge, and registered agent/server adapters.

## 1. One operating loop

Use one governed loop for discovery, adversarial comparison, implementation, evidence, release, and recovery:

```text
Discover → Normalize → Compete → Verify → Sandbox → Review → Release → Observe
   ↑                                                              ↓
   └──────────── new evidence / failure / drift / rollback ────────┘
```

VX is the execution and orchestration surface. VLNS supplies model identity, activation policy, role/capability constraints, and signed activation receipts. The unified entry point must require successful activation plus a recorded evidence event before dispatch. Existing canonical governance remains authoritative.

## 2. Adversarial innovation arena ("confrontations")

Each candidate solution or agent receives the same bounded problem statement, test fixtures, resource budget, and scoring rubric. Competing agents must not share hidden chain-of-thought or untrusted mutable state; compare their observable outputs, test results, evidence, latency, cost, and failure modes.

Required phases:

1. **Problem framing:** objective, non-goals, risk class, acceptance tests, resource/time budget.
2. **Independent proposals:** at least two independently generated approaches when feasible; record provenance and assumptions.
3. **Adversarial challenge:** counterexamples, threat-model review, dependency failure, malformed inputs, and rollback scenario.
4. **Reproducible benchmark:** correctness first; then latency, resource cost, maintainability, and evidence quality. Do not collapse safety and correctness into a single opaque score.
5. **Decision record:** select, revise, or reject with explicit evidence and unresolved unknowns.
6. **Sandboxed prototype:** no production credentials, external side effects, or canonical writes.
7. **Human-reviewed admission:** PR, required checks, owner approval, and rollback plan before release.

Novelty is a hypothesis until supported by prior-art search and reproducible tests. The arena must not describe an idea as globally novel merely because local agents did not find it.

## 3. Deep engineering discovery agents

Register agents by explicit contract rather than by name alone:

- **Research scout:** searches approved repositories, documentation, papers, and user-authorized sources; returns citations, dates, licensing notes, and confidence limits.
- **Architecture mapper:** builds dependency graphs, identifies duplicated capabilities, hidden coupling, and canonical ownership.
- **Counterexample agent:** searches for falsifying cases and uncovered failure modes.
- **Interface forge:** turns accepted contracts into accessible, responsive RTL/LTR interface prototypes; uses mock data by default and labels non-live controls.
- **Runtime/reliability agent:** evaluates health, latency, saturation, error rates, queue depth, and dependency reachability.
- **Repository recovery agent:** inventories refs and uncommitted changes, validates backups, restores only into an isolated recovery branch/worktree, and emits a manifest of every action.
- **Evidence auditor:** checks provenance, freshness, scope, test logs, and whether claims exceed evidence.

Each agent contract defines: owner, version, allowed inputs, output schema, tools, permissions, timeout, budget, retry policy, evidence format, and stop conditions. Agent-to-agent results are untrusted inputs until validated.

## 4. Fast intuition without bypassing verification

Provide a low-latency first-pass route for classification, retrieval, cache hits, and selecting relevant specialists. Treat that route as triage, not proof. Escalate when risk is high, confidence is low, sources conflict, the dependency graph changes, or a proposed action has external side effects.

Suggested decision policy:

- **Low risk + supported evidence:** fast path may produce a reversible recommendation.
- **Medium risk or incomplete evidence:** parallel specialist review and a bounded challenge round.
- **High risk, canonical changes, money, credentials, deployment, or external communication:** mandatory policy gate and human approval.
- **Timeout, disagreement, stale evidence, missing dependency, or failed health check:** HOLD; preserve context and emit a diagnostic report rather than spinning indefinitely.

## 5. Servers, queues, and resilience

Every server or remote adapter needs a health/readiness contract, request timeout, bounded retries with jitter, circuit breaker, idempotency key where applicable, correlation ID, structured logs, and an explicit degraded mode. Retry only transient failures; do not retry authorization failures as if they were outages.

Do not claim a server is connected because its configuration exists. Separate configured, reachable, authenticated, healthy, and end-to-end verified states. Secrets belong in repository/environment secret stores and server-side adapters, never in browser code or committed files.

## 6. Repository restoration and source-of-truth protection

Restoration is a controlled recovery workflow, not an automatic force-push:

1. Discover repositories, default branches, current commit SHAs, working-tree state where available, tags, releases, and known-good CI artifacts.
2. Verify backup provenance and checksums; compare canonical indexes and repository manifests.
3. Create a named recovery branch or isolated worktree from a verified commit.
4. Restore files only after a dry-run diff and ownership/secret scan.
5. Run compilation, JSON/schema checks, unit/integration tests, security/dependency checks, and repository-specific acceptance tests.
6. Upload a recovery manifest with source SHA, target SHA, file list, hashes, test outcomes, and unresolved conflicts.
7. Open a PR. Never overwrite main, rewrite history, or alter project.genome / Ω.000 automatically.

Recovery must be idempotent and restartable. Preserve the failed state and logs before remediation. If a backup cannot be verified or canonical sources disagree, stop with HOLD and request review.

## 7. Continuous assurance and scheduled work

The repository already contains a scheduled VX System Readiness workflow. Reuse and extend that single assurance surface rather than creating competing schedulers. The schedule should produce evidence artifacts; it must not auto-merge or deploy.

Minimum gates:

- Python compilation and JSON validation.
- Unit and integration tests, including the unified VX–VLNS evidence gate.
- Agent contract/schema validation and permission-boundary tests.
- Repository manifest and canonical-index integrity checks.
- Server adapter contract tests using mocks, plus separate explicitly configured integration tests.
- Recovery dry-run and rollback simulation.
- Artifact upload on both success and failure, with commit/run identifiers.

Scheduled jobs must have bounded runtime, concurrency control, least-privilege tokens, deterministic inputs where possible, and a maximum retry count. A failed run opens or updates a diagnostic issue/report; it does not start an unbounded repair loop.

## 8. LinkedIn connector boundary

The available LinkedIn connector supports looking up a named professional by first name or last name and can return profile details. It is not a broad workforce crawler, job scheduler, messaging/outreach executor, or general LinkedIn API. Therefore:

- Talent discovery must begin with a specific name or user-provided target list for this connector.
- Do not claim LinkedIn has been integrated into autonomous research until a supported, authorized API/connector and its permissions are verified.
- Do not scrape profiles or send messages automatically. Keep outreach human-approved and comply with platform rules and applicable privacy requirements.
- Store only role-relevant information needed for the approved workflow, with source and retrieval timestamp.

## 9. Operational status vocabulary

Use explicit state labels: `DISCOVERED`, `QUEUED`, `RUNNING`, `WAITING_FOR_REVIEW`, `VERIFIED`, `RELEASED`, `DEGRADED`, `HOLD`, `RECOVERY_REQUIRED`, `ROLLED_BACK`, `FAILED`.

`VERIFIED` requires evidence from the exact commit and exact checks. `RELEASED` requires a release/deployment record. A green mock test is not proof of live service connectivity. A PR is not a merged change.

## 10. Initial acceptance criteria

1. VX and VLNS are accessed through one governed task entry point.
2. No task handler runs if activation or evidence recording is missing.
3. Agent confrontations are reproducible and include counterexamples, resource bounds, and a decision record.
4. Server states distinguish configuration from real health.
5. Repository restoration is branch-based, checksum-backed, test-gated, and never force-pushes canonical branches.
6. Scheduled assurance is bounded and emits inspectable artifacts.
7. LinkedIn operations remain within the verified capabilities of the connector; no fabricated outreach or autonomous scraping.
8. Every completion claim is tied to a commit SHA and test evidence.
