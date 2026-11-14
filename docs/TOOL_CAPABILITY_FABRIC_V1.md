# VAIXLNS Tool Capability Fabric — v1

**Status:** Proposed implementation contract  
**Scope:** Discover, register, wrap, govern, verify, and operate tools and engineering capabilities under VAIXLNS.  
**Canonical owner:** VAIXLNS governance boundary  
**Related components:** NEXENT, VX, Canonical Nexus, Evidence/Proof, Event Ledger, Replay, OIF

## 1. Objective

Make VAIXLNS the canonical control plane for the tools it is authorized to use. The system must be able to discover available capabilities, describe them with stable contracts, route work to approved adapters, observe outcomes, and revoke access without surrendering canonical authority to a provider or connector.

This fabric does **not** claim ownership of third-party software, grant access that has not been authorized, or remove external terms and technical constraints. It provides a consistent VAIXLNS-controlled integration boundary.

## 2. Non-negotiable invariants

1. **Canonical authority stays inside VAIXLNS.** External tools may return data or perform explicitly authorized actions; they cannot amend the Constitution, promote themselves to canonical status, or approve their own admission.
2. **Discovery is not admission.** A reachable endpoint or installed connector is only a candidate.
3. **Least privilege by default.** Each adapter receives only the capabilities, scopes, data, and time window required for its declared task.
4. **No secrets in manifests or logs.** Store secret references in an approved secret manager; redact credentials and sensitive payloads from telemetry.
5. **No unverified side effects.** Writes, deployments, financial actions, destructive operations, and canonical commits require explicit scope-matched authority and fresh evidence.
6. **Preserve provenance.** Every capability retains source, owner, license/terms review, version, contract, adapter version, environment fingerprint, and lineage.
7. **Evidence is not authority.** A successful test or proof can inform a decision but cannot itself grant permission to execute or adopt.
8. **Fail closed on critical uncertainty.** Missing identity, contract, permission, verifier, or required evidence means quarantine or denial—not silent fallback.
9. **No silent substitution.** Replacing a provider, model, endpoint, or adapter requires compatibility checks and a new evidence record.
10. **Human/canonical governance controls promotion.** NEXENT may discover and propose; VX may execute within a granted scope; neither may self-ratify a new canonical capability.

## 3. Capability lifecycle

```text
DISCOVER
  -> IDENTIFY SOURCE / OWNER / LICENSE / VERSION
  -> DECLARE CONTRACT + DATA CLASSIFICATION + SCOPES
  -> QUARANTINE
  -> STATIC / SECURITY REVIEW
  -> SANDBOX FUNCTIONAL TEST
  -> FAILURE, TIMEOUT, RETRY & RECOVERY TEST
  -> REPLAY / DETERMINISM CHECK (where applicable)
  -> INDEPENDENT EVIDENCE VERIFICATION
  -> EXPLICIT GOVERNANCE ADMISSION
  -> LIMITED RUNTIME ENABLEMENT
  -> CONTINUOUS OBSERVATION / REVALIDATION
  -> REVOKE OR QUARANTINE ON DRIFT
```

A stage may be marked NOT_APPLICABLE only with a recorded rationale. A skipped stage must never be represented as passed.

## 4. Canonical Tool Manifest

Each discovered tool, API, model, repository, server, MCP endpoint, local executable, or data source receives a manifest with at least:

- `capability_id`, `canonical_name`, `aliases`, `category`
- `source_uri`, `source_owner`, `license_or_terms_status`
- `provider`, `product`, `version`, `adapter_version`
- `contract_ref`, `input_schema`, `output_schema`, `error_model`
- `auth_method`, `required_scopes`, `data_classes`, `egress_destinations`
- `side_effect_class`: READ | RESEARCH | WRITE | EXECUTE | DEPLOY | FINANCIAL | CANONICAL_COMMIT
- `sandbox_profile`, `resource_budget`, `timeout_budget`, `retry_policy`
- `verification_plan`, `evidence_refs`, `policy_ref`, `authority_ref`
- `environment_fingerprint`, `health_status`, `admission_state`
- `created_at`, `last_verified_at`, `expiry_or_review_at`, `lineage_refs`

Unknown fields remain explicitly UNKNOWN. Do not infer a license, permission, endpoint, or successful live connection.

## 5. Adapter contract

All providers are accessed through a narrow adapter interface:

- `discover()` — enumerate metadata only; no side effects.
- `describe()` — return the versioned manifest and contract.
- `validate(input)` — schema and scope validation before invocation.
- `invoke(input, grant)` — execute only within an explicit, expiring grant.
- `health()` — report health without exposing secrets.
- `verify(result, evidence)` — verify output/receipt independently where feasible.
- `revoke(grant)` — disable the grant and invalidate local credentials/tokens where supported.
- `export_evidence()` — return redacted, provenance-bound evidence.

An adapter must not widen scopes, change destinations, or perform undeclared side effects. Every invocation carries correlation ID, capability ID, manifest version, policy version, authority grant, budget, and expected postconditions.

## 6. Authority tiers

| Tier | Examples | Default permission |
|---|---|---|
| T0 — Inspect | Read-only docs, repository metadata, health checks | Read-only, bounded |
| T1 — Analyze | Search, code analysis, model inference without external writes | Bounded read/research |
| T2 — Propose | Generate patch, workflow, migration, or deployment plan | Produce candidate only |
| T3 — Mutate sandbox | Write to disposable branch/container/test tenant | Isolated and reversible |
| T4 — External mutation | Push branch, create PR, modify tenant or cloud resource | Explicit, scoped approval |
| T5 — Critical action | Production deploy, destructive operation, financial or canonical commit | Separate authority verification and fresh evidence; default denied |

Promotion between tiers is explicit and is never inherited from a provider's default permissions.

## 7. Initial integration domains

Start with inventory and read-only adapters; do not enable every connector at once.

1. **Source control:** GitHub repositories, branches, pull requests, issues, CI status.
2. **Development environments:** isolated build/test runners and repository sandboxes.
3. **AI/model providers:** provider-neutral inference contract, model/version tracking, budget limits, data-egress controls.
4. **MCP and APIs:** server identity, declared tools, schema pinning, per-tool allowlist and revocation.
5. **Cloud/runtime:** Azure and other cloud APIs through narrowly scoped identities and sandbox subscriptions.
6. **Observability:** logs, metrics, traces, health and audit export with redaction.
7. **Knowledge/archive:** source-preserving ingestion, deduplication suggestions, immutable provenance, lineage links.

Use a provider-neutral interface where practical, but preserve provider-specific features in adapter extensions rather than pretending all providers are equivalent.

## 8. Required events

Emit append-only, correlated events for:

- `CapabilityDiscovered`
- `ManifestCreated` / `ManifestChanged`
- `ContractValidated` / `ContractRejected`
- `CapabilityQuarantined`
- `SandboxTestPassed` / `SandboxTestFailed`
- `EvidenceVerified` / `EvidenceRejected`
- `AdmissionGranted` / `AdmissionDenied`
- `InvocationStarted` / `InvocationCompleted` / `InvocationFailed`
- `AuthorityGranted` / `AuthorityRevoked`
- `DriftDetected` / `CapabilityDisabled`

Events must include provenance and integrity metadata, but never raw secrets. Replay must not repeat external side effects; use dry-run/simulation or idempotency keys and explicit replay modes.

## 9. Acceptance gates

A capability is not `ADMITTED` until all applicable checks pass:

- Identity and source are verified.
- Contract is complete and schema-validated.
- License/terms and data handling are reviewed.
- Scopes and destinations are allowlisted.
- Sandbox functional and negative tests pass.
- Timeout, rate-limit, dependency-failure, and recovery behavior is tested.
- Output provenance and evidence are recorded.
- An independent verifier checks required evidence.
- A separate authority grants the requested tier.
- Revocation and drift handling are tested.

Use explicit states: `DISCOVERED`, `QUARANTINED`, `READY_FOR_REVIEW`, `VERIFIED_FOR_SCOPE`, `ADMITTED_LIMITED`, `DISABLED`, `REVOKED`, `REJECTED`. Do not use a single ambiguous `PASS` state.

## 10. Rollout plan

**Phase A — Inventory:** enumerate connected and repository-visible tools; classify source, owner, permission, data flow, and status. No new write permissions.

**Phase B — Registry and contracts:** implement manifest schema, contract validation, capability IDs, provenance, and change detection.

**Phase C — Read-only adapters:** start with repository search/inspection, documentation retrieval, CI status, and observability reads.

**Phase D — Isolated mutation:** enable branch/PR and sandbox operations only after negative tests, rollback, and evidence capture work.

**Phase E — Controlled runtime:** enable selected write/deploy capabilities per explicit grants, with independent verification, rate/resource budgets, and revocation drills.

**Phase F — Continuous assurance:** monitor provider/adapter drift, revalidate on version or policy changes, and quarantine when evidence becomes stale.

## 11. First implementation slice

The first code change should add:

1. JSON Schema for the manifest and admission states.
2. A registry backed by version-controlled manifests.
3. Contract and policy validation tests.
4. A read-only GitHub adapter as the reference implementation.
5. A fake adapter for deterministic failure/replay tests.
6. CI checks that reject missing identity, undeclared scopes, missing provenance, and critical actions without authority.

Do not wire production credentials, grant broad OAuth scopes, or enable autonomous production mutations in this slice.

## 12. Implementation status discipline

This document is a proposed contract, not evidence that all adapters are built. Track each item as `PROPOSED`, `IMPLEMENTED`, `TESTED`, `VERIFIED_FOR_SCOPE`, or `ADMITTED` with links to code and test evidence. A repository commit alone does not prove runtime connectivity or production readiness.
