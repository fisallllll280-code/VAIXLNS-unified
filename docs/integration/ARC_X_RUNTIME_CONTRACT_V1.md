# ARC-X Ω Runtime Contract v1

**Status:** IMPLEMENTED CANDIDATE — CI evidence recorded; independent review pending  
**Canonical owner:** VAIXLNS  
**Runtime projection:** VAIXLNS-unified  
**Canonical specification:** [ARC-X Ω v1](https://github.com/fisallllll280-code/VAIXLNS/blob/main/docs/tools/ARC_X_EPISTEMIC_REALITY_COMPILER_V1.md)

This document defines an executable runtime-side contract. It does not replace or fork the canonical ARC-X specification.

## 1. Executable surface

- Package: `arc_x/`
- API: `compile_eir(sources, evidence, claims, proof_obligations)`
- Gate: `evaluate_admission(compilation, action, approval, evidence_verifier, authority_verifier)`
- VX execution bridge: `arc_x/vx_bridge.py`
- Generic server/tool fabric: `vx/tool_fabric.py`
- Conformance tests: `tests/test_arc_x_core.py`, `tests/test_arc_x_vx_bridge.py`, `tests/test_vx_tool_fabric.py`

The implementation uses only the Python standard library. It is deterministic for identical input records and does not fetch network data or run supplied code.

## 2. Input types

- **SourceReceipt:** repository, immutable revision, source path, content SHA-256, retrieval timestamp, parser version, and URI.
- **EvidenceRecord:** source reference, evidence type, statement, optional linked claim, stance, test/proof result, and artifact SHA-256.
- **ClaimRecord:** stable ID, statement, type, and whether it is in the required scope.
- **ProofObligation:** claim link, verification requirement, required/optional flag, and evidence IDs.

Mutable revisions such as `main`, `master`, `HEAD`, `latest`, and `default` are rejected. A SHA-shaped value is not proof that a source is trustworthy; retrieval and hash calculation must be performed by a trusted adapter.

## 3. Compilation invariants

1. Canonical JSON uses sorted keys, compact separators, UTF-8, and rejects non-finite numbers/opaque values.
2. Every evidence item must reference a known source; claim and obligation references must resolve.
3. Contradictory supporting and refuting evidence remains visible and blocks promotion.
4. A claim with support is marked `SUPPORTED_NOT_PROVEN`, not `VERIFIED`.
5. Every required claim must have at least one required proof obligation.
6. Required proof obligations accept only source-linked passing test, runtime-trace, or proof-artifact records whose claim binding matches the obligation and which include artifact hashes.
7. Missing support, invalid references, duplicate IDs, and open proof obligations are explicit findings.
8. Compilation produces an EIR digest; the digest excludes no fields from the EIR payload.

## 4. Admission boundary

`READ` and `RESEARCH` can be marked eligible for review because they do not create external effects. `VERIFY` requires structurally complete proof obligations and an independent trusted evidence verifier. `EXECUTE` and `CANONICAL_COMMIT` require that same evidence attestation plus a scope-matched approval authenticated by a separate trusted authority verifier.

The evidence verifier must independently validate source retrieval, pinned revisions, actual content/artifact hashes, provenance/signatures, result authenticity, and claim-to-proof binding. The authority verifier must authenticate the actor, approval artifact, revocation state, and requested scope. Both are host trust boundaries; passing a lambda that returns true is suitable only for a unit test and grants no real-world authority. This package itself does not authenticate users, sign approvals, execute code, deploy systems, or write to the canonical registry.

## 5. State semantics

- `MISSING`: an invalid/missing reference or required evidence prevents safe continuation.
- `CONFLICT`: the same claim has both supporting and refuting evidence.
- `PARTIAL`: the declared proof scope is incomplete.
- `READY_FOR_REVIEW`: required declared obligations have been assembled without blocking findings; this is not production readiness.
- `VERIFIED` is not assigned by raw compilation. `proof_scope_complete` indicates structural completeness only. The `VERIFY` gate returns `VERIFIED` for the explicitly declared scope only after a trusted evidence verifier approves the evidence bundle; this is not whole-project or production verification.

## 6. Fail-closed rules

Unknown actions, unpinned revisions, EIR hash mutation, contradictory evidence, missing proof, mismatched claim-to-proof links, failed evidence attestation, wrong approval scope, missing verifier, and verifier exceptions must not result in admission. The runtime bridge adds a claim that the VX operation result must carry the same operation ID and EIR digest as the admitted request. The previous canonical state must remain unchanged unless a separate trusted authority layer commits a reviewed change.

## 7. Validation

Run:

```bash
python -m unittest tests.test_arc_x_core -v
python -m pytest -q
```

CI pass on this branch is required before changing this candidate's state from `IMPLEMENTED` to `VERIFIED`.


## 8. VX and federated tools

The candidate execution path uses `arc_x.vx_bridge.ArcXVXBridge` for evidence-carrying candidate execution and `vx.tool_fabric.VXToolFabric` for registered server/tool calls. The latter requires an explicit host-supplied ARC-X policy callback, integration-admission callback, health probe, registered contract fingerprint, and the existing VX supervisor.

See [VX Federated Tool Fabric v1](VX_FEDERATED_TOOL_FABRIC_V1.md). That adapter contract supports tools that have been registered with an exact `ToolSpec`; it is not a claim that arbitrary unregistered servers have been automatically connected. EIR digest, exact tool-contract digest, server protocol/version, health result, VX authority, gateway audit event, and VX verifier result remain distinct evidence fields.
