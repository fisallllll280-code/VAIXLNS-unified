# VAIXLNS Ω Agent System — Specialized Agent Taxonomy and VX Integration Contract

**Status:** SPECIFIED (not deployed)  
**Scope:** VAIXLNS, VLNS, VX, NEXNET/NEXENT federation  
**Purpose:** Define the specialized agent system expected to operate through VX without confusing a role definition with a running agent.

## 1. Non-negotiable design rules

1. An agent role is not a running process. Runtime registration, health, model/tool binding, permissions, and task history must be observed before the UI reports an agent as online.
2. A task is not complete because an LLM says it is complete. Completion requires machine-observable results and evidence satisfying explicit acceptance criteria.
3. Execution, verification, and approval are separate capabilities. High-impact tasks require an independent verifier and policy-authorized approver.
4. Every mutation is scoped to a repository, branch, path set, and task contract. No destructive or cross-repository action is implied by agent membership.
5. Preserve canonical `project.genome` and `Ω.000`. Changes to either require an explicit change proposal, before/after hashes, preservation tests, and human approval.
6. Do not promote speculative research or model output to verified fact without provenance and independent checks.
7. All task state transitions are append-only audit events; corrections supersede earlier records rather than erase them.
8. Model/provider adapters are replaceable. Agent identity and task contracts must not depend on a single LLM vendor.

## 2. Agent families and specialist roles

These are role specifications, not a claim that all agents are currently deployed.

### A. Command, planning, and governance
- `AG-SUPERVISOR`: maintains global task state, enforces dependencies and escalations.
- `AG-MISSION-PLANNER`: decomposes goals into bounded tasks and acceptance criteria.
- `AG-ORCHESTRATOR`: schedules eligible tasks and manages retries/concurrency.
- `AG-POLICY-GOVERNOR`: evaluates permissions, risk tier, approvals, and policy decisions.
- `AG-CONFLICT-ARBITER`: detects contradictory plans, evidence, or registry claims; never silently chooses a winner.
- `AG-HUMAN-APPROVAL-GATE`: queues actions requiring explicit human authorization.
- `AG-COST-CAPACITY-PLANNER`: estimates budgets, quotas, latency, and resource constraints.
- `AG-INCIDENT-COMMANDER`: coordinates failure containment and recovery.

### B. Repository, software, and runtime engineering
- `AG-REPO-AUDITOR`: inventories repositories, branches, files, workflows, ownership, and drift.
- `AG-ARCHITECT`: maintains architecture boundaries and system contracts.
- `AG-CODE-ENGINEER`: implements a scoped change on an isolated branch.
- `AG-REFACTOR-SPECIALIST`: proposes minimal, reversible refactors with regression checks.
- `AG-API-CONTRACT`: validates schemas, compatibility, authentication, and versioning.
- `AG-TEST-ENGINEER`: creates and executes unit, integration, regression, and property tests.
- `AG-CI-CD-ENGINEER`: inspects pipelines and verifies build/release evidence.
- `AG-DEPENDENCY-AUDITOR`: checks dependency versions, licenses, vulnerabilities, and lockfiles.
- `AG-PERFORMANCE-ENGINEER`: benchmarks throughput, latency, memory, and bottlenecks.
- `AG-RELIABILITY-ENGINEER`: handles health checks, resilience, retries, timeouts, and failure modes.
- `AG-OBSERVABILITY-ENGINEER`: defines logs, metrics, traces, event IDs, and alert rules.
- `AG-DATABASE-ENGINEER`: validates schemas, migrations, integrity, and recovery.
- `AG-UI-ENGINEER`: builds operational interfaces with real-data/fixture separation.
- `AG-ACCESSIBILITY-REVIEWER`: checks keyboard operation, semantics, contrast, and usability.

### C. Verification, evidence, and security
- `AG-INDEPENDENT-VERIFIER`: re-runs acceptance tests independently of the implementer.
- `AG-EVIDENCE-ADMISSION`: checks provenance, integrity, freshness, scope, and commit binding.
- `AG-CRYPTOGRAPHIC-ATTESTOR`: computes and validates hashes/signatures where configured.
- `AG-IDENTITY-AUTHZ-AUDITOR`: tests identity, least privilege, authorization, and separation of duties.
- `AG-THREAT-MODELER`: identifies trust boundaries, abuse cases, and mitigations.
- `AG-SECURITY-TESTER`: runs authorized security tests within a defined scope.
- `AG-SUPPLY-CHAIN-REVIEWER`: reviews provenance, SBOMs, artifacts, and dependency risk.
- `AG-DRIFT-DETECTOR`: compares actual repository/runtime state against approved baselines.
- `AG-RECOVERY-VALIDATOR`: tests backup, restoration, replay, and state continuity.
- `AG-RED-TEAM-CHALLENGER`: attempts bounded falsification of claims; cannot approve its own findings.
- `AG-PRIVACY-REVIEWER`: checks sensitive-data exposure, retention, and minimization.

### D. VX, federation, and distributed execution
- `AG-VX-KERNEL`: works on state transitions, deterministic semantics, and kernel contracts.
- `AG-VX-RUNTIME`: validates runtime lifecycle, event handling, and health.
- `AG-FEDERATION-ARCHITECT`: defines inter-system contracts and ownership boundaries.
- `AG-FEDERATION-ADAPTER`: implements one explicitly scoped system adapter.
- `AG-MCP-INTEGRATION`: configures and tests MCP server/client interoperability.
- `AG-AGENT-REGISTRY`: maintains agent identity, capabilities, versions, and health observations.
- `AG-TASK-SCHEDULER`: selects tasks only when dependencies, permissions, and capacity permit.
- `AG-WORKER-POOL-MANAGER`: manages worker lifecycle and bounded concurrency.
- `AG-QUEUE-RELIABILITY`: validates idempotency, ordering, retry policy, and dead-letter behavior.
- `AG-STATE-REPLAY`: replays recorded events and compares expected/actual state.
- `AG-SANDBOX-ENGINEER`: validates isolation boundaries for untrusted work.
- `AG-MODEL-ROUTER`: selects configured models using policy, capability, latency, and cost constraints.

### E. Research, mathematics, and innovation
- `AG-SCIENTIFIC-RESEARCHER`: searches primary sources and records bibliographic provenance.
- `AG-LITERATURE-SYNTHESIZER`: compares evidence across papers and marks uncertainty/conflicts.
- `AG-MATHEMATICAL-MODELER`: formalizes assumptions, definitions, lemmas, and proof obligations.
- `AG-FORMAL-METHODS`: specifies invariants and checks them with suitable formal tools.
- `AG-ALGORITHMS-RESEARCHER`: compares algorithmic approaches and complexity.
- `AG-COMPUTATIONAL-PHYSICS`: develops testable computational physics models when in scope.
- `AG-SIMULATION-ENGINEER`: designs simulations, parameters, baselines, and reproducibility.
- `AG-OPTIMIZATION-RESEARCHER`: formulates optimization objectives, constraints, and sensitivity analyses.
- `AG-HYPOTHESIS-CHALLENGER`: seeks counterexamples and falsifiable tests for novel claims.
- `AG-INNOVATION-RECOVERY`: indexes prior ideas and recovers provenance without deleting drafts.
- `AG-KNOWLEDGE-CURATOR`: links claims, concepts, sources, experiments, and registry entries.
- `AG-REPRODUCIBILITY-REVIEWER`: checks whether a result can be reproduced from recorded inputs.

### F. Product, operations, and delivery
- `AG-PRODUCT-ANALYST`: maps user outcomes to measurable acceptance criteria.
- `AG-WORKFLOW-DESIGNER`: models operator journeys and task handoffs.
- `AG-DOCUMENTATION-ENGINEER`: updates operational documentation alongside verified behavior.
- `AG-RELEASE-MANAGER`: prepares release evidence and checks gates; cannot bypass approvals.
- `AG-CHANGE-MANAGER`: tracks change impact, rollback plan, and approval record.
- `AG-REPORTING-ANALYST`: reports measured progress with source links and explicit unknowns.

## 3. Required agent record

Each registered agent should expose the following typed record. Unknown values remain null/UNKNOWN; never synthesize telemetry.

```json
{
  "agent_id": "AG-INDEPENDENT-VERIFIER",
  "role_version": "1.0.0",
  "lifecycle": "SPECIFIED",
  "runtime_instance_id": null,
  "provider": null,
  "model": null,
  "capabilities": ["test.read", "evidence.verify"],
  "permissions": ["repository.read", "test.execute"],
  "forbidden_capabilities": ["evidence.self_approve", "unscoped.write", "deploy"],
  "health": "UNKNOWN",
  "last_seen_at": null,
  "active_task_ids": [],
  "policy_version": "required",
  "provenance_refs": []
}
```

Lifecycle values: `SPECIFIED`, `REGISTERED`, `STARTING`, `READY`, `BUSY`, `DEGRADED`, `OFFLINE`, `QUARANTINED`. A role definition alone must stay `SPECIFIED`.

## 4. Task contract and evidence

Every executable task must contain:
- stable `task_id`, goal, risk tier, owner agent, and optional independent verifier;
- repository/system scope, base commit, allowed path set, and branch;
- dependencies with typed edges: `BLOCKS`, `REQUIRES`, `PRODUCES`, `VERIFIES`, `SUPERSEDES`;
- machine-checkable acceptance criteria and explicit prohibited actions;
- input artifact references and hashes;
- execution start/end timestamps, exit code, environment fingerprint, and log reference;
- test IDs, expected results, actual results, evidence hashes, and verifier identity;
- approval record for sensitive actions and a rollback/recovery plan where applicable.

A task can be `VERIFIED` only when every mandatory criterion passes and the evidence matches the target commit and declared scope. Verification failure, missing evidence, stale evidence, or verifier conflict must block promotion.

## 5. Claude Code ↔ VX integration layers

The existing `VAIXLNS-unified/integrations/mcp_server.py` currently exposes only these read-only tools:
- `vx.health`
- `vx.status`
- `vx.capabilities.list`

The Claude Code MCP configuration must be treated as a connection bootstrap, not as proof of a running agent mesh.

Recommended phased integration:
1. **Read-only handshake:** establish MCP server discovery and successful calls to all three tools.
2. **Inventory:** add read-only endpoints for agents, tasks, dependency graph, and evidence only after their backing data sources and authorization are inspected.
3. **Task planning:** create proposed task plans with schema validation; no execution side effects.
4. **Sandboxed execution:** introduce narrowly scoped task execution with explicit repository/branch/path constraints, audit events, timeouts, and human approval gates.
5. **Independent verification:** separate verifier identity and verify commit-bound evidence.
6. **Federation:** enable each VAIXLNS/VLNS/VX/NEXNET adapter only after its contract, auth, health, failure behavior, and integration tests pass.

Do not expose a generic shell or unrestricted filesystem tool as a shortcut to agent integration.

## 6. Agents & Tasks UI requirements

The interface should show:
- actual registered agents separately from the full catalog of specified roles;
- runtime health and last-seen timestamps from telemetry, not mock counters;
- task queue, owner, verifier, blockers, retry count, elapsed time, and risk tier;
- dependency graph with blocked edges and cycle detection;
- execution logs, commit links, test results, evidence provenance, and verification status;
- explicit labels for `LIVE`, `FIXTURE`, `STALE`, and `UNKNOWN` data;
- policy/approval controls, audit trail, and rollback references.

Never display a fixture as live state. Empty telemetry should be shown as UNKNOWN, not as zero active failures or 100% success.

## 7. Acceptance tests before production claims

- AT-AG-01: specified role is not shown as online without a runtime heartbeat.
- AT-AG-02: unauthorized capability invocation is denied and audited.
- AT-AG-03: blocked task cannot start while required dependencies are incomplete.
- AT-AG-04: implementer cannot self-approve a task requiring independent verification.
- AT-AG-05: evidence for a different commit is rejected.
- AT-AG-06: mutated evidence hash is detected.
- AT-AG-07: duplicate task submission is idempotent or explicitly rejected.
- AT-AG-08: task replay records deterministic comparison results or explains nondeterminism.
- AT-AG-09: `project.genome` and `Ω.000` preservation checks fail closed on unexpected changes.
- AT-AG-10: UI fixture/live labels are tested.
- AT-AG-11: federation adapter failure is isolated and surfaced.
- AT-AG-12: no task is marked `VERIFIED` solely from an LLM narrative.

## 8. Current truth boundary

This document specifies the target architecture. It does not claim that these agents exist as deployed services, that Claude Code has completed an MCP handshake, or that the task scheduler, evidence admission, or federation execution has been implemented. Those claims require runtime and CI evidence attached to the corresponding task.
