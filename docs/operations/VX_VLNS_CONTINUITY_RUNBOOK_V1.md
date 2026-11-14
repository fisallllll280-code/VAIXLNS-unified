# VX / VLNS Continuity Runbook — V1

## Objective

Keep the VX execution surface and VLNS integration boundary discoverable, evidence-labelled, and traceable from the VAIXLNS canonical hub. This runbook is a continuity mechanism; it is not a claim that every external repository, endpoint, or background worker is running.

## Implemented in this change

- A versioned machine-readable federation manifest: `config/vx_vlns_federation.v1.json`.
- A local structural validator: `federation/continuity_manifest.py`.
- Regression tests for required fields, unique repository identities, allowed evidence states, HTTPS GitHub URLs, and a non-empty canonical flow.
- A registry of canonical repository roles, promotion policy, known open gaps, and cross-system invariants.

## How to validate locally

From the repository root:

```bash
python -m unittest tests.test_vx_vlns_continuity_manifest -v
python -m pytest -q tests/test_vx_vlns_continuity_manifest.py
```

These tests validate the manifest structure only. They do not query GitHub, authenticate to VLNS, contact MCP servers, execute a remote workflow, or prove production readiness.

## Canonical system roles

- **VAIXLNS** — canonical architecture, governance, registry, recovery, and innovation hub.
- **VAIXLNS-unified** — executable integration surface; its status must remain evidence-scoped.
- **VX** — governed execution boundary; every operation requires identity, contract, policy/authority, and evidence.
- **VLNS** — external/network activation boundary; endpoint availability and credentials are deployment facts that must be observed, not inferred from a document.
- **NEXENT** — discovery and architecture-research proposal source; proposals are not execution authority.
- **VV** — verification boundary.
- **OIF** — operational integrity/assurance; it is not consensus and does not substitute for replication or leader election.

## No-loss indexing rules

1. Preserve original names, IDs, source URLs, versions, and source artifacts.
2. Never delete a historical entry because another entry appears equivalent.
3. Record merges as explicit relations: `same_as`, `supersedes`, `derived_from`, or `implemented_by`; do not overwrite the source record.
4. Mark each record with one evidence state from the manifest contract. Unknown status is `OPEN`, not `PASS`.
5. A change of canonical identity must include a rationale, source references, and a lineage edge.
6. Do not claim that the historical 0001–2750 index has been fully recovered until each position is reconciled against source evidence.

## Required admission pipeline

```text
DISCOVER
  -> IDENTITY + PROVENANCE
  -> CONTRACT
  -> QUARANTINE / SANDBOX
  -> FUNCTIONAL + SECURITY TESTS
  -> FAILURE / RECOVERY / REPLAY
  -> INDEPENDENT VERIFICATION
  -> FRESH EVIDENCE + PROOF
  -> EXPLICIT AUTHORITY
  -> VX ADMISSION
  -> RUNTIME OBSERVATION
  -> CONTINUOUS REVALIDATION
```

A repository being reachable, a PR being open, or a unit test passing is not sufficient to admit a capability into runtime.

## Operational cycle

For each scheduled engineering cycle:

1. Read the current manifest and the latest integration audit.
2. Detect repository/ref changes using the authenticated GitHub adapter where configured.
3. Record changed, added, and removed paths with source commit and capture time.
4. Reconcile the delta against registry identities and lineage; do not automatically promote unknown files.
5. Run targeted unit, contract, security, and regression tests for affected capabilities.
6. Update evidence state only when the corresponding artifacts exist and can be reproduced.
7. Produce a short report: verified changes, failed checks, unknowns, required authority decisions, and next smallest executable task.
8. If the index source or a required endpoint is unavailable, preserve the last known snapshot and mark the cycle `DEGRADED`; do not fabricate a successful scan.

## Known gaps requiring separate implementation or external configuration

- Full source-by-source reconciliation of all historical master-index positions.
- Authenticated GitHub-wide scan and scheduled execution with durable run history.
- Live VLNS endpoint health and credential provisioning.
- Distributed consensus, leader election, replication, and multi-node failover proof.
- Production deployment evidence and alerting.

## Authority and merge policy

This change is a proposal on a feature branch. Merge only after the repository's required checks pass and the owner authorizes it under the existing authority-driven merge policy. Do not enable a new auto-merge path as part of this runbook.
