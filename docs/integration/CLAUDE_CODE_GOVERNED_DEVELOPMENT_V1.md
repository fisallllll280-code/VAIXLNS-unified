# Claude Code Governed Development Bridge V1

**State:** PROPOSAL — repository instructions exist; live Claude Code/MCP connectivity is not verified by this document.
**Owner boundary:** VAIXLNS governance → VX orchestration → VV verification.
**Scope:** development-only integration across VAIXLNS, VLNS, VX, NEXNET/NEXENT, and VAIXLNS-unified.

## Objective

Use Claude Code as a repository-scoped engineering operator in the VAIXLNS workflow, not as an authority source. Claude Code may inspect, propose, edit an isolated branch, and run approved tests. It must not self-admit tools, rewrite canonical sources, merge, deploy, publish, move money, or change production state.

## Shared work contract

1. **Discover first:** record repository URL, branch, commit SHA, working-tree state, relevant contracts, tests, and dependency manifests before editing.
2. **Classify every claim:** VERIFIED only with reproducible execution evidence; otherwise SPECIFIED, PARTIAL, MISSING, CONFLICT, or PROPOSAL.
3. **Plan before patch:** state objective, affected paths, invariants, risk, and test plan in the task record.
4. **Branch isolation:** edits occur on a task-specific feature branch. Never push directly to protected/default branches.
5. **Narrow patch:** preserve existing interfaces and drafts; no broad refactors, deletions, or canonical-source modifications without explicit review.
6. **Run deterministic checks:** syntax/schema checks, focused tests, then applicable full suite; capture command, exit code, commit SHA, run URL, and artifact digest.
7. **Independent verification:** a different verifier or CI job checks invariants and evidence; the authoring agent cannot approve its own change.
8. **Human gate:** merge, release, production deployment, public posting, secrets rotation, and any financial action require separate explicit human authorization.
9. **Fail closed:** absent credentials, unclear authority, stale evidence, provider errors, policy conflicts, or failed tests block admission.
10. **No secret propagation:** credentials stay in approved secret stores; never include secret values in prompts, diffs, logs, artifacts, issue text, or commits.

## Integration topology

- **Claude Code:** coding/review operator using CLAUDE.md; optional skills/hooks/MCP are disabled until individually reviewed.
- **GitHub:** source-control and CI evidence provider. Read operations are distinct from write, merge, workflow-rerun, and release permissions.
- **VX:** creates a task plan and enforces lifecycle/authority transitions; a successful tool call is not a proof of correctness.
- **VLNS:** operational contract and development requirements; contract conformance must be evidenced, not assumed.
- **NEXENT/NEXNET:** discovery and proposal/federation inputs; cannot grant canonical authority.
- **ARC-X / Reality Forge:** claim/evidence admission and deterministic adversarial simulation; cannot override policy or authorize production.
- **VV:** independent verification, replay, and evidence admission.
- **Ω.000 / project.genome:** canonical identity/index sources; protected from automated writes by default.

## Task envelope

Every cross-agent task should carry:
- task_id, parent_task_id, intent, scope, repository, base_commit, branch
- requested_capabilities, denied_capabilities, risk_class
- preconditions, invariants, simulation_profile, test_plan
- evidence_refs, evidence_digest, verification_status
- human_approval_ref (empty until approval exists), final_disposition

The envelope is data, not authority. The runtime must validate the actor and policy independently.

## Admission lifecycle

DISCOVER → IDENTIFY → CONTRACT → QUARANTINE → SANDBOX → TEST → SIMULATE → REPLAY → INDEPENDENT_VERIFY → FRESH_PROOF → HUMAN_AUTHORITY → ADMIT

A provider connection or model response only proves connectivity/response, not security, correctness, or admission.

## MCP and hook policy

Before enabling any MCP server, record its source/revision, command and arguments, environment-variable names (never values), filesystem/network reach, tool list, write effects, dependency/license status, timeout, output limits, and kill/rollback path. Start read-only. Add write scopes only through reviewed policy changes and a sandboxed acceptance test. Hooks must be local, deterministic, narrowly scoped, and non-secret-bearing. Do not install or execute unknown extensions automatically.

## Definition of done

- Change is on an isolated branch and linked to a commit.
- Existing tests and new targeted tests have actual recorded results.
- Simulation and replay results are tied to the same candidate commit and input digests.
- Independent verification has not been performed by the authoring identity.
- No canonical write, merge, deployment, publication, or financial transaction occurred without the corresponding approval.
- Remaining external setup and unverified claims are explicitly listed.
