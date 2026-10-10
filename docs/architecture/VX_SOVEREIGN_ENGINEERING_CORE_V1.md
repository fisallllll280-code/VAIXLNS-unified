# VX Sovereign Engineering Core v1

Status: IMPLEMENTED ON FEATURE BRANCH; CI VERIFICATION PENDING.

## Purpose
A small coordination core layered over existing VX runtime and ARC-X contracts. It does not replace `VXSupervisor`, `SCCKKernel`, `ArcXVXBridge`, or the existing tool fabric.

## Pipeline
`UNDERSTAND -> DISCOVER -> SYNTHESIZE -> PROVE -> FEDERATE -> EVOLVE`

- **Understand:** normalize a declared system inventory with revision, capabilities, dependencies, conflicts, status and evidence references.
- **Discover:** report missing dependencies, capability overlaps and declared conflicts. Findings are candidates, not automatic remediation.
- **Synthesize:** produce deterministic, digest-bound review tasks. No shell commands or destructive changes are generated.
- **Prove:** require simulation/test receipt references and injected verifier/authorizer callbacks. A positive result remains eligible for a separate execution gate; it never executes.
- **Federate:** resolve requested capabilities against declared records without network access or connector invocation.
- **Evolve:** create an evidence-bound proposal that requires approval and cannot mutate canonical state.

## Evidence semantics
`SPECIFIED`, `IMPLEMENTED`, `CI_VERIFIED`, `RUNNING`, and `PROVEN` are deliberately distinct. The core accepts only these labels and treats them as declared inventory state, not independently verified truth. A CI_VERIFIED label must be backed by an external receipt before promotion in a production registry.

## Safety boundaries
No credentials, network calls, model calls, tool execution, canonical writes, deployments, financial transfers, self-promotion, or deletion occur here. Callback success is a trusted-host boundary and is not a cryptographic signature. Receipts are hashed for stable reference, not authenticated. Human review and the existing VX authorization/execution path remain required.

## Tests
`tests/test_vx_sovereign_engineering_core.py` covers deterministic inventory, duplicate identities, invalid state labels, dependency/overlap/conflict discovery, stale digest rejection, non-executing synthesis, proof/authorization gates, federation gaps and evidence-bound evolution.

## Next integration steps
1. Wire normalized repository snapshots from the existing repository federation into `understand`.
2. Bind ARC-X evidence envelopes and independent receipt verification to `prove_candidate`.
3. Route approved plans through `ArcXVXBridge` and `VXSupervisor`, not a new executor.
4. Add durable event receipts and idempotency for distributed operation.
5. Verify CI on the branch and review against the SCCK commit boundary before merge.
