# VAIXLNS Ω Unified Control Plane V1

**State:** PROPOSAL — controller contract and inventory schema; not a deployed or connected runtime.
**Canonical:** false. This artifact must not replace or modify project.genome or Ω.000.

## Mission
Provide one governed control plane for inventory, health, task dispatch, simulation, evidence review, and recovery across VAIXLNS, VLNS, VX, NEXENT/NEXNET, VAIXLNS-unified, Claude Code, ARC-X, VV, and approved office/MCP providers.

## Authority model
- VAIXLNS owns canonical identity and policy; canonical sources are read-only to automation.
- VX coordinates tasks only within capabilities explicitly admitted by policy.
- Connectors begin read-only. A provider response is not proof of correctness or permission to mutate.
- Claude Code and other model agents are task workers, never policy authorities or self-approvers.
- ARC-X evaluates claim/evidence admissibility; VV independently verifies candidate outputs.
- Human approval is required for merge, deployment, publication, canonical changes, secret rotation, and any live financial or external side effect.
- Financial execution remains disabled by default.

## System registry record
Each system entry must include:
`system_id, display_name, repository, pinned_commit, branch, owner, contract_version, connector_id, connector_revision, capabilities_requested, capabilities_admitted, health_state, last_probe_at, last_success_at, freshness_seconds, evidence_refs, verification_state, risk_class, approval_policy, rollback_ref`.

Unknown values remain UNKNOWN/MISSING. Do not infer connectivity or readiness from repository presence.

## Lifecycle
`DISCOVERED → IDENTIFIED → CONTRACT_CHECKED → QUARANTINED → READ_ONLY_PROBED → SANDBOX_TESTED → SIMULATED → INDEPENDENTLY_VERIFIED → HUMAN_REVIEW → ADMITTED`

Any auth failure, stale evidence, policy conflict, unknown capability, or test failure moves the integration to `BLOCKED` or `DEGRADED`; it must not fail open.

## Task lifecycle
`PROPOSED → PLANNED → AUTHORIZED → RUNNING → TESTING → VERIFYING → AWAITING_HUMAN_REVIEW → ACCEPTED`
Failure states: `BLOCKED, FAILED, CANCELLED, RECOVERY_REQUIRED, UNKNOWN_OUTCOME`.

Every task binds to the exact repository commit, input digest, actor identity, declared capabilities, time/resource limits, test plan, evidence digest, and approval reference.

## Operator actions
The future dashboard should expose:
1. Inventory and search systems.
2. Read-only health probe with timestamp and evidence.
3. Preview task plan and affected resources.
4. Run isolated tests/simulations on a feature branch.
5. Inspect logs, evidence, drift, failed checks, and dependency edges.
6. Request human approval.
7. Recover/replay a failed sandbox task.
8. Produce a non-canonical integration report.

Mutating actions must be separately permissioned, logged, idempotent where applicable, and approval-gated.

## Safety invariants
- Preserve canonical sources and previous accepted state.
- No direct push to protected branches.
- No hidden background execution or unbounded agent loops.
- No automatic installation or invocation of unreviewed MCP servers.
- No secrets in prompts, source files, logs, evidence bundles, or chat.
- No financial transaction or production action from a simulation result.
- No claim of control until a real probe and capability-specific acceptance test pass.
- Stop controls must cancel queued work and signal running workers; uncertain external outcomes require manual review.

## Initial acceptance tests
- Unknown connector is blocked.
- Missing authentication does not downgrade into anonymous write access.
- Read-only probe makes no mutation.
- Stale health evidence becomes UNKNOWN/STALE.
- Requested capability outside allowlist is denied.
- Task cannot start without actor, pinned commit, limits, and test plan.
- Model agent cannot approve its own change.
- Canonical files cannot be changed by automation.
- Replayed task verifies input and output digests.
- Stop request prevents new dispatch and records cancellation outcome.
- Connector timeout is reported as UNKNOWN_OUTCOME, not success.
- Every state transition has an append-only evidence event.

## Deployment sequence
Phase 0: inventory and repository archaeology.
Phase 1: read-only registry and health reporting.
Phase 2: branch-scoped task planning and sandbox tests.
Phase 3: deterministic simulation and replay.
Phase 4: independent verification and approval workflow.
Phase 5: selectively admitted writes, each capability reviewed individually.

No phase is complete without executable tests, CI evidence, and a reviewer-visible artifact.
